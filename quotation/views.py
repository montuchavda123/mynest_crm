import os
import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from crm_api.models import Lead, ActivityTimeline
from crm_api.services.odoo_service import OdooService, OdooIntegrationError
from .forms import QuotationForm
from .models import PaymentPlan, Quotation, QuotationItem, QuotationSection
from .pdf import generate_quotation_pdf


@login_required
def create_quotation(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    if request.method == "POST":
        form = QuotationForm(request.POST)
        if form.is_valid():
            quotation = form.save(commit=False)
            quotation.lead = lead
            quotation.created_by = request.user
            if Quotation.objects.filter(lead=lead, quotation_number=quotation.quotation_number).exists():
                quotation.quotation_number = _next_quotation_number(lead)
                messages.info(request, f"Quotation number already existed. Auto-updated to {quotation.quotation_number}.")
            action = request.POST.get("action")
            quotation.status = Quotation.STATUS_PENDING if action == "submit_for_approval" else Quotation.STATUS_DRAFT
            try:
                quotation.save()
            except IntegrityError:
                quotation.quotation_number = _next_quotation_number(lead)
                quotation.save()


            _save_sections_and_items(request, quotation)
            _save_payments(request, quotation)

            if action == "generate_pdf":
                quotation.pdf_file = generate_quotation_pdf(quotation)
                quotation.save(update_fields=["pdf_file"])
            messages.success(request, "Quotation saved successfully.")
            return redirect("dynamic_quotation:quotation_detail", pk=quotation.pk)
    else:
        initial = {
            "quotation_number": _next_quotation_number(lead),
            "client_name": lead.name,
            "client_phone": lead.phone,
            "client_email": lead.email,
            "project_type": "RESIDENTIAL" if not lead.property_type else ("COMMERCIAL" if "commercial" in lead.property_type.lower() else "RESIDENTIAL"),
            "project_location": lead.location,
            "execution_timeline": lead.execution_timeline,
            "quotation_date": timezone.now().date(),
            "selected_package": Quotation.PACKAGE_BASIC,
        }
        form = QuotationForm(initial=initial)
    return render(request, "quotation/create.html", {"lead": lead, "form": form})


def _next_quotation_number(lead):
    base = f"QTN-{timezone.now().year}-{lead.id:04d}"
    existing = list(
        Quotation.objects.filter(lead=lead, quotation_number__startswith=base).values_list("quotation_number", flat=True)
    )
    if base not in existing:
        return base
    max_suffix = 1
    pattern = re.compile(rf"^{re.escape(base)}-(\d+)$")
    for number in existing:
        match = pattern.match(number)
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))
    return f"{base}-{max_suffix + 1:02d}"


def _save_sections_and_items(request, quotation):
    quotation.sections.all().delete()
    quotation.items.all().delete()
    section_names = request.POST.getlist("section_name[]")
    section_indices = request.POST.getlist("section_idx[]")

    for loop_idx, s_idx in enumerate(section_indices):
        name = section_names[loop_idx]
        if not name.strip():
            continue
        section = QuotationSection.objects.create(quotation=quotation, section_name=name.strip(), display_order=loop_idx + 1)
        
        item_numbers = request.POST.getlist(f"item_number_{s_idx}[]")
        descriptions = request.POST.getlist(f"description_{s_idx}[]")
        quantities = request.POST.getlist(f"quantity_{s_idx}[]")
        unit_prices = request.POST.getlist(f"unit_price_{s_idx}[]")
        remarks = request.POST.getlist(f"remarks_{s_idx}[]")
        
        for row_index, description in enumerate(descriptions):
            if not description.strip():
                continue
            qty = Decimal(quantities[row_index] if row_index < len(quantities) else "1")
            unit = Decimal(unit_prices[row_index] if row_index < len(unit_prices) else "0")
            QuotationItem.objects.create(
                quotation=quotation,
                section=section,
                item_number=int(item_numbers[row_index] if row_index < len(item_numbers) else row_index + 1),
                description=description.strip(),
                quantity=qty,
                unit_price=unit,
                total_price=qty * unit,
                remarks=remarks[row_index] if row_index < len(remarks) else "",
            )


def _save_payments(request, quotation):
    quotation.payment_plans.all().delete()
    stages = request.POST.getlist("payment_stage[]")
    percentages = request.POST.getlist("payment_percentage[]")
    amounts = request.POST.getlist("payment_amount[]")
    descriptions = request.POST.getlist("payment_description[]")
    for idx, stage in enumerate(stages):
        if not stage.strip():
            continue
        PaymentPlan.objects.create(
            quotation=quotation,
            payment_stage=stage.strip(),
            percentage=Decimal(percentages[idx] or "0"),
            amount=Decimal(amounts[idx] or "0"),
            description=descriptions[idx] if idx < len(descriptions) else "",
        )





@login_required
def quotation_detail(request, pk):
    quotation = get_object_or_404(
        Quotation.objects.select_related("lead", "created_by", "approved_by").prefetch_related(
            "sections__items", "payment_plans"
        ),
        pk=pk,
    )
    return render(request, "quotation/detail.html", {"quotation": quotation})


@login_required
def quotation_download_pdf(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    if not quotation.pdf_file:
        quotation.pdf_file = generate_quotation_pdf(quotation)
        quotation.save(update_fields=["pdf_file"])
    return FileResponse(open(quotation.pdf_file.path, "rb"), as_attachment=True, filename=os.path.basename(quotation.pdf_file.path))


@login_required
def quotation_approve(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    if request.user.role != "ADMIN":
        messages.error(request, "Only admin can approve quotations.")
        return redirect("dynamic_quotation:quotation_detail", pk=quotation.pk)

    if quotation.status == Quotation.STATUS_APPROVED:
        messages.info(request, "Quotation is already approved.")
        return redirect("dynamic_quotation:quotation_detail", pk=quotation.pk)

    quotation.status = Quotation.STATUS_APPROVED
    quotation.approved_by = request.user
    quotation.approved_date = timezone.now()
    if not quotation.pdf_file:
        quotation.pdf_file = generate_quotation_pdf(quotation)
    # Avoid duplicate Odoo sync from crm_api post_save signal.
    quotation._skip_odoo_sync_signal = True
    quotation.save()
    
    # Sync approved quotation to Odoo using the new service
    try:
        odoo_service = OdooService()
        result = odoo_service.sync_approved_quotation(quotation.pk)
        messages.success(
            request, 
            f"Quotation approved and synced to Odoo. Project ID: {result['project_id']}"
        )
    except OdooIntegrationError as e:
        messages.warning(request, f"Quotation approved, but Odoo sync failed: {str(e)}")
    except Exception as e:
        messages.warning(request, f"Quotation approved, but sync encountered an error: {str(e)}")
    
    # Update lead status to CLOSED and record in timeline
    lead = quotation.lead
    if lead.status != 'CLOSED':
        lead.status = 'CLOSED'
        lead.save(update_fields=['status'])
        
        ActivityTimeline.objects.create(
            lead=lead,
            action="Quotation Approved",
            notes=f"Quotation {quotation.quotation_number} approved. Lead status updated to CLOSED.",
            performed_by=request.user
        )
    
    return redirect("dynamic_quotation:quotation_detail", pk=quotation.pk)





@login_required
def quotation_reject(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    if request.user.role != "ADMIN":
        messages.error(request, "Only admin can reject quotations.")
        return redirect("dynamic_quotation:quotation_detail", pk=quotation.pk)
    quotation.status = Quotation.STATUS_REJECTED
    quotation.approved_by = request.user
    quotation.approved_date = timezone.now()
    quotation.save(update_fields=["status", "approved_by", "approved_date"])
    messages.warning(request, "Quotation rejected.")
    return redirect("dynamic_quotation:quotation_detail", pk=quotation.pk)

