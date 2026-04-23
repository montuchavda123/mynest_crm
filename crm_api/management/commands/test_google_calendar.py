from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm_api.services.google_calendar_service import _calendar_id, _calendar_client


class Command(BaseCommand):
    help = "Test Google Calendar API connectivity by creating a test event."

    def handle(self, *args, **options):
        service = _calendar_client()
        now = timezone.now() + timedelta(minutes=5)
        event_payload = {
            "summary": "TeleCRM Calendar Integration Test",
            "description": "Created by test_google_calendar command.",
            "start": {"dateTime": now.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": (now + timedelta(minutes=30)).isoformat(), "timeZone": "Asia/Kolkata"},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 30}]},
        }
        event = service.events().insert(calendarId=_calendar_id(), body=event_payload).execute()
        self.stdout.write(self.style.SUCCESS(f"Google Calendar test event created. Event ID: {event.get('id')}"))
