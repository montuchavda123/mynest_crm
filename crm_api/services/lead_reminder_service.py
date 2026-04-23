import re
from datetime import datetime, time, timedelta

from django.utils import timezone

from crm_api.models import FollowUp

CALLBACK_PATTERNS = [
    r"\btomorrow call\b",
    r"\bcall tomorrow\b",
    r"\bcall back tomorrow\b",
    r"\bcallback tomorrow\b",
    r"\bremind tomorrow\b",
    r"\bcall back\b.*\btomorrow\b",
    r"\btomorrow\b.*\bcall\b",
]


def parse_callback_reminder(notes: str):
    if not notes:
        return None

    normalized = notes.lower()
    
    # Basic keyword check to avoid unnecessary regex
    keywords = ['callback', 'call back', 'remind', 'tomorrow', 'today']
    if not any(kw in normalized for kw in keywords):
        return None

    now = timezone.localtime()
    target_date = now.date()
    
    # Date detection
    if 'tomorrow' in normalized:
        target_date = now.date() + timedelta(days=1)
    elif 'today' in normalized:
        target_date = now.date()
    else:
        # Default to tomorrow if not specified but callback mentioned
        if 'callback' in normalized or 'call back' in normalized or 'remind' in normalized:
            target_date = now.date() + timedelta(days=1)
        else:
            return None

    # Time detection (e.g., "01:00 PM", "1pm", "13:00")
    # This regex looks for: HH or HH:MM followed optionally by AM/PM
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", normalized)
    target_time = time(hour=10, minute=0) # Default to 10 AM
    
    if time_match:
        try:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            meridiem = time_match.group(3)
            
            if meridiem:
                if meridiem == 'pm' and hour < 12:
                    hour += 12
                elif meridiem == 'am' and hour == 12:
                    hour = 0
            elif hour > 0 and hour < 8: 
                # Heuristic: if hour is 1-7 and no AM/PM, assume PM (1 PM - 7 PM)
                hour += 12
                
            target_time = time(hour=hour, minute=minute)
        except (ValueError, TypeError):
            pass # Fallback to default time if parsing fails

    reminder_dt = datetime.combine(target_date, target_time)
    reminder_dt = timezone.make_aware(reminder_dt, timezone.get_current_timezone())
    
    # Safety check: if today and time is already past, move to tomorrow or +1 hour
    if reminder_dt <= now:
        if 'today' in normalized:
            reminder_dt = now + timedelta(hours=1)
        else:
            reminder_dt += timedelta(days=1)

    return reminder_dt


def schedule_callback_followup(lead, notes: str):
    reminder_dt = parse_callback_reminder(notes)
    if reminder_dt is None:
        return None

    existing_followup = FollowUp.objects.filter(
        lead=lead,
        date__date=reminder_dt.date(),
        notes__icontains="callback reminder"
    ).first()
    if existing_followup:
        return existing_followup

    followup = FollowUp.objects.create(
        lead=lead,
        date=reminder_dt,
        notes=f"Callback reminder generated from notes: {notes}",
        reminder_flag=True,
    )
    return followup
