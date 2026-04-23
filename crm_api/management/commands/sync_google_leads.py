import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from crm_api.services.google_sheets_service import GoogleSheetsService

logger = logging.getLogger("crm_api")

class Command(BaseCommand):
    help = "Pulls leads from Google Sheets and syncs them to the Lead model."

    def handle(self, *args, **options):
        # 1. Check if sync is enabled
        enabled = getattr(settings, "GOOGLE_SHEET_SYNC_ENABLED", "false")
        if str(enabled).lower() != "true":
            self.stdout.write(self.style.WARNING("Google Sheet sync is disabled in settings (.env)."))
            return

        # 2. Check configuration
        sheet_id = getattr(settings, "GOOGLE_SHEET_ID", None)
        sheet_range = getattr(settings, "GOOGLE_SHEET_RANGE", "Sheet1!A:Z")
        
        if not sheet_id:
            self.stdout.write(self.style.ERROR("GOOGLE_SHEET_ID is not configured in .env."))
            return

        self.stdout.write(f"Starting Google Sheets sync for Sheet ID: {sheet_id}...")

        try:
            # 3. Initialize Service
            service = GoogleSheetsService()
            
            # 4. Fetch Data
            data = service.fetch_sheet_data(sheet_id, sheet_range)
            
            if not data:
                self.stdout.write(self.style.WARNING("No data found in the sheet or range."))
                return
            
            # 5. Process Rows
            self.stdout.write(f"Found {len(data) - 1} data rows. Processing...")
            stats = service.process_rows(data)
            
            # 6. Report Results
            self.stdout.write(self.style.SUCCESS("-" * 40))
            self.stdout.write(self.style.SUCCESS(f"Sync Completed Successfully!"))
            self.stdout.write(self.style.SUCCESS(f"Total Rows:     {stats['total']}"))
            self.stdout.write(self.style.SUCCESS(f"New Leads:      {stats['created']}"))
            self.stdout.write(self.style.SUCCESS(f"Duplicates:     {stats['duplicates']}"))
            self.stdout.write(self.style.SUCCESS(f"Errors:         {stats['errors']}"))
            self.stdout.write(self.style.SUCCESS("-" * 40))
            
            logger.info(f"Google Sheet Sync Results: Created={stats['created']}, Duplicates={stats['duplicates']}, Errors={stats['errors']}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Sync failed with error: {str(e)}"))
            logger.exception("Google Sheet Sync Error")
