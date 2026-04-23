from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm_api.models import ActivityTimeline, FollowUp, Lead, Meeting, MissedLead
from crm_api.services.google_calendar_service import upsert_meeting_event
from crm_api.services.lead_reminder_service import schedule_callback_followup


class Command(BaseCommand):
    help = (
        "Run MyNest CRM automation tasks: missed-call detection, callback reminders, "
        "and Google Calendar meeting sync."
    )

    def handle(self, *args, **options):
        now = timezone.now()
        missed_threshold = now - timedelta(hours=24)

        self.stdout.write("Starting MyNest CRM automation run...")

        auto_missed = 0
        candidates = Lead.objects.filter(status__in=["NEW", "CONTACTED"], created_at__lte=missed_threshold)
        for lead in candidates:
            has_future_followup = FollowUp.objects.filter(lead=lead, date__gte=now).exists()
            activity_count = ActivityTimeline.objects.filter(lead=lead).count()
            if activity_count > 1 or has_future_followup:
                continue

            lead.status = "MISSED_CALL"
            lead.save(update_fields=["status"])
            MissedLead.objects.create(
                name=lead.name,
                phone=lead.phone,
                source=lead.source,
                call_status="Missed",
            )
            ActivityTimeline.objects.create(
                lead=lead,
                action="Missed Call Detected",
                notes="Lead did not receive interaction within 24 hours.",
                performed_by=None,
            )
            auto_missed += 1

        self.stdout.write(self.style.SUCCESS(f"Missed call automation marked {auto_missed} lead(s)."))

        callback_created = 0
        leads = Lead.objects.filter(status__in=["NEW", "CONTACTED", "MEETING", "QUOTATION", "DISCUSSION"])
        for lead in leads:
            initial_notes = ActivityTimeline.objects.filter(lead=lead, action="Lead Created").order_by("-timestamp").first()
            if not initial_notes or not initial_notes.notes:
                continue

            followup = schedule_callback_followup(lead, initial_notes.notes)
            if followup is not None:
                callback_created += 1

        self.stdout.write(self.style.SUCCESS(f"Callback reminders created: {callback_created}"))

        synced = 0
        meetings = Meeting.objects.filter(date__gte=now)
        for meeting in meetings:
            try:
                event_id = upsert_meeting_event(meeting)
                if event_id and meeting.google_calendar_event_id != event_id:
                    meeting.google_calendar_event_id = event_id
                    meeting.save(update_fields=["google_calendar_event_id"])
                synced += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Failed to sync meeting {meeting.id}: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"Meeting Google Calendar sync completed for {synced} future meeting(s)."))
        self.stdout.write(self.style.SUCCESS("MyNest CRM automation run finished."))
