from django.conf import settings
from django.db import models

from crm_api.models import Lead


class Quotation(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_PENDING = "PENDING_APPROVAL"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING, "Pending Approval"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    PROJECT_TYPE_RESIDENTIAL = "RESIDENTIAL"
    PROJECT_TYPE_COMMERCIAL = "COMMERCIAL"
    PROJECT_TYPE_CHOICES = (
        (PROJECT_TYPE_RESIDENTIAL, "Residential"),
        (PROJECT_TYPE_COMMERCIAL, "Commercial"),
    )

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="dynamic_quotations")
    quotation_number = models.CharField(max_length=80)
    client_name = models.CharField(max_length=255)
    client_phone = models.CharField(max_length=20, blank=True)
    client_email = models.EmailField(blank=True)
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES, default=PROJECT_TYPE_RESIDENTIAL)
    project_location = models.CharField(max_length=255, blank=True)
    quotation_date = models.DateField()
    expected_completion_date = models.DateField(null=True, blank=True)
    project_area_sqft = models.CharField(max_length=50, blank=True)
    design_theme = models.CharField(max_length=120, blank=True)
    execution_timeline = models.CharField(max_length=120, blank=True)
    scope_of_work = models.TextField(blank=True)
    exclusions = models.TextField(blank=True)
    payment_terms = models.TextField(blank=True)
    warranty_terms = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    PACKAGE_BASIC = "BASIC"
    PACKAGE_SEMI = "SEMI"
    PACKAGE_FULL = "FULL"
    PACKAGE_CHOICES = (
        (PACKAGE_BASIC, "LAMINATED (BASIC-ECO)"),
        (PACKAGE_SEMI, "DUCO/VENEER/LAMINATE (Semi-Luxury Interior)"),
        (PACKAGE_FULL, "PU-DUCO/VENEER/ACRYLIC/H.LAM (Full-Luxury Interior)"),
    )
    selected_package = models.CharField(max_length=10, choices=PACKAGE_CHOICES, default=PACKAGE_BASIC)
    base_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    package_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    pdf_file = models.FileField(upload_to="quotations/", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="quotations_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotations_approved")
    approved_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lead", "quotation_number"], name="uniq_lead_quotation_number")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.quotation_number} - {self.client_name}"


class QuotationSection(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="sections")
    section_name = models.CharField(max_length=120)
    display_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self) -> str:
        return f"{self.section_name} ({self.quotation.quotation_number})"


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="items")
    section = models.ForeignKey(QuotationSection, on_delete=models.CASCADE, related_name="items")
    item_number = models.PositiveIntegerField(default=1)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item_number", "id"]


class PaymentPlan(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="payment_plans")
    payment_stage = models.CharField(max_length=120)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)



class CompanyDetails(models.Model):
    company_name = models.CharField(max_length=255) # Trade Name
    legal_name = models.CharField(max_length=255, blank=True, null=True)
    gst_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=120, blank=True)
    ifsc_code = models.CharField(max_length=40, blank=True)
    business_address = models.TextField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="company/", null=True, blank=True)

    def __str__(self) -> str:
        return self.company_name
