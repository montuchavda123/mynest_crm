import re
from django.db import models
from django.conf import settings
from django.utils import timezone
from tele_crm.utils import SecureFileUpload, validate_file_size, validate_file_extension

class Lead(models.Model):
    STATUS_CHOICES = (
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted'),
        ('MISSED_CALL', 'Missed Call'),
        ('MEETING', 'Meeting'),
        ('QUOTATION', 'Quotation'),
        ('DISCUSSION', 'Final Discussion'),
        ('CLOSED', 'Deal Closed'),
        ('LOST', 'Deal Lost'),
    )
    
    SOURCE_CHOICES = (
        ('SOCIAL_MEDIA', 'Social Media'),
        ('WEBSITE', 'Website'),
        ('REFERRAL', 'Referral'),
        ('WALK_IN', 'Walk-in'),
    )
    
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)
    property_type = models.CharField(max_length=100, blank=True, null=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    execution_timeline = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_leads'
    )
    # Technical Requirements
    floor_plan_2d = models.FileField(
        upload_to=SecureFileUpload('requirements/2d/'), 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    floor_plan_3d = models.FileField(
        upload_to=SecureFileUpload('requirements/3d/'), 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.phone:
            # Keep only digits
            cleaned = re.sub(r'\D', '', str(self.phone))
            # Remove '91' prefix only if length > 10
            if len(cleaned) > 10 and cleaned.startswith('91'):
                self.phone = cleaned[2:]
            else:
                self.phone = cleaned
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.status}"


class Meeting(models.Model):
    TYPE_CHOICES = (
        ('SITE', 'Site Visit'),
        ('OFFICE', 'Office Meeting'),
        ('PHONE', 'Phone Consultation'),
    )
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='meetings')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    meeting_title = models.CharField(max_length=255, blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField()
    reminder_datetime = models.DateTimeField(null=True, blank=True, db_index=True)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meetings_assigned'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meetings_created'
    )
    google_calendar_event_id = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.date and timezone.is_naive(self.date):
            self.date = timezone.make_aware(self.date)
        if not self.client_name and self.lead_id:
            self.client_name = self.lead.name
        if not self.meeting_title:
            self.meeting_title = f"{self.get_type_display()} Meeting"
        if self.reminder_datetime is None and self.date:
            self.reminder_datetime = self.date - timezone.timedelta(minutes=30)
        if self.reminder_datetime and timezone.is_naive(self.reminder_datetime):
            self.reminder_datetime = timezone.make_aware(self.reminder_datetime)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.type} with {self.lead.name} on {self.date}"


class Quotation(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='quotations')
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prepared_quotations'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    pdf_file = models.FileField(upload_to='quotations/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quote for {self.lead.name} - ₹{self.amount} ({self.status})"


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    service_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.service_name} - {self.quotation.lead.name}"


class QuotationSection(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=255)
    content = models.TextField()
    sort_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.title} - {self.quotation}"


class FollowUp(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='followups')
    date = models.DateTimeField()
    notes = models.TextField()
    reminder_flag = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Follow-up for {self.lead.name} on {self.date}"

    @property
    def is_overdue(self):
        return self.date < timezone.now()


class SiteVisit(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='site_visits')
    date = models.DateTimeField()
    feedback = models.TextField()
    google_calendar_event_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Site visit to {self.lead.name} on {self.date}"


class Project(models.Model):
    STATUS_CHOICES = (
        ('planning', 'Planning'),
        ('design', 'Design'),
        ('execution', 'Execution'),
        ('quality_check', 'Quality Check'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    )
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='projects')
    project_name = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project_name} ({self.status})"


class ProjectLog(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='logs')
    status = models.CharField(max_length=50)
    note = models.TextField()
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log for {self.project.project_name} at {self.timestamp}"


class ActivityTimeline(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='timeline')
    action = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']


class MissedLead(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=15)
    call_status = models.CharField(max_length=50, default='Missed')
    source = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']


class LeadImport(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    property_type = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    execution_timeline = models.CharField(max_length=255, blank=True, null=True)
    is_converted = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Imported: {self.name} ({self.phone})"
