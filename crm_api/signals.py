import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from .models import Meeting, Quotation, Lead
from .services.google_calendar_service import delete_meeting_event, upsert_meeting_event
from .services.odoo_service import OdooIntegrationError, OdooService

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Meeting)
def update_lead_status_on_meeting(sender, instance, created, **kwargs):
    if created:
        lead = instance.lead
        if lead.status in ['NEW', 'CONTACTED']:
            lead.status = 'MEETING'
            lead.save()
    try:
        event_id = upsert_meeting_event(instance)
        if event_id and event_id != instance.google_calendar_event_id:
            Meeting.objects.filter(pk=instance.pk).update(google_calendar_event_id=event_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Google Calendar sync failed for meeting %s: %s", instance.pk, exc)


@receiver(post_delete, sender=Meeting)
def remove_google_calendar_event_on_delete(sender, instance, **kwargs):
    try:
        if instance.google_calendar_event_id:
            delete_meeting_event(event_id=instance.google_calendar_event_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Google Calendar delete failed for meeting %s: %s", instance.pk, exc)

@receiver(post_save, sender=Quotation)
def update_lead_status_on_quotation(sender, instance, created, **kwargs):
    lead = instance.lead
    
    # If a quotation is created, set status to QUOTATION
    if created:
        lead.status = 'QUOTATION'
        lead.save()
    
    # Logic for approval/rejection
    if instance.status == 'APPROVED':
        lead.status = 'CLOSED'
        lead.save()

        # Trigger Odoo sync only when moving into APPROVED state.
        should_sync = created or getattr(instance, "_previous_status", None) != "APPROVED"
        # Allow explicit caller paths (quotation_approve view) to handle sync once.
        if should_sync and not getattr(instance, "_skip_odoo_sync_signal", False):
            transaction.on_commit(lambda: sync_approved_quotation_to_odoo(instance.id))
    elif instance.status == 'REJECTED':
        lead.status = 'LOST'
        lead.save()


@receiver(pre_save, sender=Quotation)
def track_previous_quotation_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        previous = Quotation.objects.only("status").get(pk=instance.pk)
        instance._previous_status = previous.status
    except Quotation.DoesNotExist:
        instance._previous_status = None


def sync_approved_quotation_to_odoo(quotation_id: int) -> None:
    try:
        result = OdooService().sync_approved_quotation(quotation_id=quotation_id)
        logger.info("Quotation %s synced to Odoo successfully: %s", quotation_id, result)
    except OdooIntegrationError as exc:
        logger.error("Odoo integration failed for quotation %s: %s", quotation_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected Odoo sync failure for quotation %s: %s", quotation_id, exc)
