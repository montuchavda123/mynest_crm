from django import forms

from .models import Quotation


class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            "quotation_number",
            "client_name",
            "client_phone",
            "client_email",
            "project_type",
            "project_location",
            "quotation_date",
            "expected_completion_date",
            "project_area_sqft",
            "design_theme",
            "execution_timeline",
            "scope_of_work",
            "exclusions",
            "payment_terms",
            "warranty_terms",
            "selected_package",
            "base_amount",
            "package_amount",
            "notes",
        ]
        widgets = {
            "quotation_number": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Enter Quotation Number"}),
            "client_name": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Enter Client Name"}),
            "client_phone": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Enter Phone Number"}),
            "client_email": forms.EmailInput(attrs={"class": "form-control form-control-sm", "placeholder": "Enter Email Address"}),
            "project_location": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Enter Project Location"}),
            "quotation_date": forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
            "expected_completion_date": forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
            "notes": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 3, "placeholder": "Additional notes and requirements..."}),
            "scope_of_work": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 3, "placeholder": "Describe the scope of work..."}),
            "exclusions": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 3, "placeholder": "Items not included in this quotation..."}),
            "payment_terms": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 3, "placeholder": "Payment stage details..."}),
            "warranty_terms": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 3, "placeholder": "Product and service warranty terms..."}),
            "base_amount": forms.HiddenInput(),
            "package_amount": forms.HiddenInput(),
            "selected_package": forms.HiddenInput(),
        }
