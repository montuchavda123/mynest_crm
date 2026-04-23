import os
import re
import logging
from typing import List, Dict, Any, Optional

from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.contrib.auth import get_user_model
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from crm_api.models import Lead, LeadImport, ActivityTimeline
from crm_api.services.lead_reminder_service import schedule_callback_followup

logger = logging.getLogger(__name__)

# Scopes for Google Sheets API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

class GoogleSheetsService:
    """
    Service to handle fetching and processing leads from Google Sheets.
    """
    
    def __init__(self):
        self.creds = self._load_credentials()
        self.service = build("sheets", "v4", credentials=self.creds, cache_discovery=False)
        self.user_model = get_user_model()
        
    def _load_credentials(self):
        creds = None
        
        # 1. Try Service Account FIRST for background sync tasks
        if getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", None):
            sa_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
            if os.path.exists(sa_path):
                try:
                    import json
                    with open(sa_path, 'r') as f:
                        data = json.load(f)
                        if data.get('type') == 'service_account':
                            creds = service_account.Credentials.from_service_account_file(
                                sa_path, scopes=SCOPES
                            )
                            logger.info("Using Service Account for Google Sheets.")
                        else:
                            logger.info("Provided credentials file is not a Service Account JSON.")
                except Exception as e:
                    logger.error(f"Service Account Loading Failed: {str(e)}")
            else:
                # If path is relative, try joining with BASE_DIR
                alt_path = os.path.join(getattr(settings, 'BASE_DIR', ''), sa_path)
                if os.path.exists(alt_path):
                    try:
                        creds = service_account.Credentials.from_service_account_file(
                            alt_path, scopes=SCOPES
                        )
                        logger.info("Using Service Account for Google Sheets (via BASE_DIR).")
                    except Exception as e:
                        logger.error(f"Service Account Loading Failed (alt path): {str(e)}")
        
        # 2. Try OAuth2 Refresh Token ONLY if SA failed
        if not creds and getattr(settings, "GOOGLE_REFRESH_TOKEN", None):
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=settings.GOOGLE_REFRESH_TOKEN,
                    client_id=settings.GOOGLE_CLIENT_ID,
                    client_secret=settings.GOOGLE_CLIENT_SECRET,
                    token_uri="https://oauth2.googleapis.com/token",
                    scopes=SCOPES
                )
                if creds and creds.refresh_token:
                    if creds.expired:
                        creds.refresh(Request())
                else:
                    creds = None
            except Exception as e:
                logger.error(f"Google Sheets OAuth2 Initialization Failed: {str(e)}")
                creds = None

        if not creds:
            raise Exception("No valid Google credentials found (Service Account or Refresh Token).")
            
        return creds

    def fetch_sheet_data(self, sheet_id: str, range_name: str) -> List[List[Any]]:
        """
        Fetches raw data from the specified Google Sheet.
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=range_name
            ).execute()
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Error fetching Google Sheet data: {str(e)}")
            return []

    def normalize_header(self, header: str) -> str:
        """
        Normalizes header name: lowercase, strip, remove special characters.
        """
        if not header:
            return ""
        # Replace underscores with spaces, lowercase, and remove special characters
        header = str(header).replace('_', ' ').lower()
        header = re.sub(r'[^a-z0-9\s]', '', header)
        return ' '.join(header.split())

    def get_column_mapping(self, headers: List[str]) -> Dict[str, int]:
        """
        Dynamically maps normalized headers to Lead model fields using aliases.
        """
        field_aliases = {
            "name": ["name", "full name", "customer name", "client name", "lead name", "fullname"],
            "phone": ["phone", "mobile", "contact", "phone number", "mobile number", "contact number", "phonenumber"],
            "email": ["email", "email address", "mail id"],
            "location": ["city", "location", "address", "area", "residence"],
            "budget": ["budget", "amount", "price", "est budget", "estimated budget", "what is approximate interior budget", "client budget", "what is your approximate interior budget"],
            "source": ["source", "lead source", "channel"],
            "property_type": ["choose ur property type", "choose your property type", "home type", "property type", "bhk"],
            "execution_timeline": ["when do you plan to start your interior execution", "timeline", "start date", "execution"],
        }
        
        mapping = {}
        normalized_headers = [self.normalize_header(h) for h in headers]
        
        for field, aliases in field_aliases.items():
            for idx, h_norm in enumerate(normalized_headers):
                if h_norm in aliases:
                    mapping[field] = idx
                    break
        
        return mapping

    def normalize_phone(self, phone: str) -> str:
        """
        Cleans phone number: keeps only digits and removes '91' country code if present
        on numbers longer than 10 digits.
        """
        if not phone:
            return ""
        # Keep only digits
        cleaned = re.sub(r'\D', '', str(phone))
        
        # If length > 10 and starts with 91, remove it (assumed country code)
        # If length <= 10, keep it (could be a local number starting with 91)
        if len(cleaned) > 10 and cleaned.startswith('91'):
            return cleaned[2:]
            
        return cleaned

    def normalize_email(self, email: str) -> str:
        """
        Normalizes email: lowercase and strip.
        """
        if not email:
            return ""
        return str(email).strip().lower()

    def process_rows(self, data: List[List[Any]]) -> Dict[str, int]:
        """
        Processes sheet data and inserts leads.
        Returns stats: total, created, duplicates, errors.
        """
        if not data or len(data) < 2:
            return {"total": 0, "created": 0, "duplicates": 0, "errors": 0}
            
        headers = data[0]
        rows = data[1:]
        mapping = self.get_column_mapping(headers)
        
        # We need at least phone or name to identify a lead
        if "phone" not in mapping and "email" not in mapping:
            logger.error("Mapping failed: Neither 'phone' nor 'email' column found.")
            return {"total": len(rows), "created": 0, "duplicates": 0, "errors": 1}

        stats = {"total": len(rows), "created": 0, "duplicates": 0, "errors": 0}
        
        # Get default assignee (Admin)
        default_assignee = self.user_model.objects.filter(role="ADMIN").first()
        
        for row in rows:
            try:
                # Extract data based on mapping
                name = row[mapping["name"]] if "name" in mapping and mapping["name"] < len(row) else ""
                phone_raw = row[mapping["phone"]] if "phone" in mapping and mapping["phone"] < len(row) else ""
                email_raw = row[mapping["email"]] if "email" in mapping and mapping["email"] < len(row) else ""
                location = row[mapping["location"]] if "location" in mapping and mapping["location"] < len(row) else ""
                budget_raw = row[mapping["budget"]] if "budget" in mapping and mapping["budget"] < len(row) else 0
                source_raw = row[mapping["source"]] if "source" in mapping and mapping["source"] < len(row) else "Google Sheet"
                property_type = row[mapping["property_type"]] if "property_type" in mapping and mapping["property_type"] < len(row) else ""
                execution_timeline = row[mapping["execution_timeline"]] if "execution_timeline" in mapping and mapping["execution_timeline"] < len(row) else ""
                
                phone = self.normalize_phone(phone_raw)
                email = self.normalize_email(email_raw)
                
                # Skip if basic info is missing
                if not phone and not email:
                    continue
                
                # Duplicate check: Phone OR Email
                exists = False
                if phone and Lead.objects.filter(phone=phone).exists():
                    exists = True
                elif email and Lead.objects.filter(email=email).exists():
                    exists = True
                
                # Clean budget
                try:
                    if isinstance(budget_raw, str):
                        budget = float(re.sub(r'[^\d.]', '', budget_raw)) if budget_raw else 0
                    else:
                        budget = float(budget_raw) if budget_raw else 0
                except (ValueError, TypeError):
                    budget = 0

                # Create/Update LeadImport Record (for search/conversion purposes)
                _, created = LeadImport.objects.update_or_create(
                    phone=phone,
                    defaults={
                        'name': name,
                        'email': email,
                        'location': location,
                        'budget': budget,
                        'property_type': property_type,
                        'execution_timeline': execution_timeline,
                        'is_converted': exists
                    }
                )

                if created:
                    stats["created"] += 1
                else:
                    stats["duplicates"] += 1
                
            except Exception as e:
                logger.error(f"Error processing row {row}: {str(e)}")
                stats["errors"] += 1
                
        return stats
