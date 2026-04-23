import os
import io
import json
import pandas as pd

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Count
from crm_api.models import Lead, Meeting, Quotation, QuotationItem, QuotationSection, FollowUp, SiteVisit, ActivityTimeline, Project, MissedLead, LeadImport
from crm_api.services.google_calendar_service import upsert_meeting_event, upsert_site_visit_event
from crm_api.services.lead_reminder_service import schedule_callback_followup
from accounts.models import User
from quotation.models import Quotation as DynamicQuotation
from .forms import UserRegistrationForm, UserLoginForm

@login_required
def dashboard(request):
    # Redirect admins to admin panel (unless they explicitly want CRM dashboard)
    if request.user.is_admin_role and not request.GET.get('force'):
        return redirect('admin_dashboard')
    # Filters
    location = request.GET.get('location')
    property_type = request.GET.get('property_type')
    assigned_to = request.GET.get('assigned_to')
    
    # Base Lead Query for filtered stats
    leads_qs = Lead.objects.all()
    if location:
        leads_qs = leads_qs.filter(location__icontains=location)
    if property_type:
        leads_qs = leads_qs.filter(property_type__icontains=property_type)
    if assigned_to:
        leads_qs = leads_qs.filter(assigned_to_id=assigned_to)

    # Aggregations for cards (affected by filters)
    total_leads = leads_qs.count()
    closed_deals = leads_qs.filter(status='CLOSED').count()
    missed_call_count = leads_qs.filter(status='MISSED_CALL').count()
    
    # Non-lead filtered stats
    total_meetings = Meeting.objects.count() # Meetings usually global
    total_fetched = LeadImport.objects.count()
    
    # Conversion Rate calculation (Leads / Fetched Data)
    data_conversion_rate = 0
    if total_fetched > 0:
        data_conversion_rate = round((total_leads / total_fetched) * 100, 1)
    
    # Chart 1: Status distribution (Filtered)
    status_counts = leads_qs.values('status').annotate(count=Count('status'))
    status_data = {item['status']: item['count'] for item in status_counts}
    all_statuses = ['NEW', 'CONTACTED', 'MISSED_CALL', 'MEETING', 'QUOTATION', 'DISCUSSION', 'CLOSED', 'LOST']
    status_summary = {s: status_data.get(s, 0) for s in all_statuses}
    
    # Chart 2: Source Distribution (Filtered)
    source_counts = leads_qs.values('source').annotate(count=Count('source'))
    source_summary = {item['source']: item['count'] for item in source_counts}
    
    # Chart 3: Property Type Analysis (Filtered, Top 8)
    prop_counts = leads_qs.values('property_type').annotate(count=Count('property_type')).order_by('-count')[:8]
    prop_summary = {item['property_type'] or "Unspecified": item['count'] for item in prop_counts}

    # Chart 4: 7-Day Trend (Filtered)
    from django.db.models.functions import TruncDate
    trend_raw = leads_qs.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).annotate(date=TruncDate('created_at')).values('date').annotate(count=Count('id')).order_by('date')
    
    # Ensure current 7 days are represented
    trend_data = []
    trend_labels = []
    for i in range(6, -1, -1):
        d = timezone.localdate() - timezone.timedelta(days=i)
        trend_labels.append(d.strftime('%b %d'))
        count = next((item['count'] for item in trend_raw if item['date'] == d), 0)
        trend_data.append(count)

    # Filter Options
    locations = Lead.objects.values_list('location', flat=True).distinct()
    property_types = Lead.objects.values_list('property_type', flat=True).distinct()
    salespeople = User.objects.filter(role__in=['ADMIN', 'SALES'])

    # Recent Activities (Longer list for the offcanvas)
    recent_activities = ActivityTimeline.objects.all().order_by('-timestamp')[:50]
    
    callback_reminders = FollowUp.objects.filter(date__gte=timezone.now()).order_by('date')[:5]
    today_callback_count = FollowUp.objects.filter(date__date=timezone.localdate()).count()
    upcoming_meetings = Meeting.objects.filter(date__gte=timezone.now()).order_by('date')[:5]
    
    context = {
        'total_leads': total_leads,
        'total_meetings': total_meetings,
        'closed_deals': closed_deals,
        'total_fetched': total_fetched,
        'data_conversion_rate': data_conversion_rate,
        'status_summary': status_summary,
        'source_summary': source_summary,
        'prop_summary': prop_summary,
        'trend_labels': trend_labels,
        'trend_data': trend_data,
        'recent_activities': recent_activities,
        'missed_call_count': missed_call_count,
        'callback_reminders': callback_reminders,
        'today_callback_count': today_callback_count,
        'upcoming_meetings': upcoming_meetings,
        'filter_locations': locations,
        'filter_property_types': property_types,
        'filter_salespeople': salespeople,
        'active_filters': {
            'location': location,
            'property_type': property_type,
            'assigned_to': int(assigned_to) if assigned_to else None
        }
    }
    return render(request, 'crm_ui/dashboard.html', context)

@login_required
def lead_list(request):
    status_filter = request.GET.get('status', '')
    leads = Lead.objects.all().order_by('-created_at')
    if status_filter:
        leads = leads.filter(status=status_filter)
    return render(request, 'crm_ui/leads/list.html', {
        'leads': leads,
        'preselected_status': status_filter,
    })

@login_required
def lead_detail(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    timeline = lead.timeline.all().order_by('-timestamp')
    return render(request, 'crm_ui/leads/detail.html', {'lead': lead, 'timeline': timeline})

@login_required
def delete_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        lead.delete()
        messages.success(request, f"Lead '{lead.name}' deleted successfully.")
    return redirect('lead_list')

@login_required
def meetings(request):
    meeting_list = Meeting.objects.filter(date__gte=timezone.now()).order_by('date')
    leads = Lead.objects.all().order_by('name')
    return render(request, 'crm_ui/meetings/index.html', {
        'meetings': meeting_list,
        'leads': leads
    })

@login_required
def add_meeting(request):
    if request.method == 'POST':
        lead_id = request.POST.get('lead')
        meeting_type = request.POST.get('type')
        date = request.POST.get('date')
        time = request.POST.get('time')
        notes = request.POST.get('notes')
        
        try:
            lead = get_object_or_404(Lead, id=lead_id)
            # Combine date and time
            from django.utils import timezone
            import datetime
            dt_str = f"{date} {time}"
            meeting_date = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
            if timezone.is_naive(meeting_date):
                meeting_date = timezone.make_aware(meeting_date)
            
            meeting = Meeting.objects.create(
                lead=lead,
                type=meeting_type,
                date=meeting_date,
                meeting_title=f"{meeting_type.title()} Meeting",
                client_name=lead.name,
                assigned_user=request.user,
                created_by=request.user,
                notes=notes
            )
            try:
                event_id = upsert_meeting_event(meeting)
                if event_id:
                    meeting.google_calendar_event_id = event_id
                    meeting.save(update_fields=['google_calendar_event_id'])
            except Exception as calendar_error:
                messages.warning(
                    request,
                    f"Meeting created but Google Calendar sync failed: {calendar_error}"
                )

            # Update lead status
            if lead.status in ['NEW', 'CONTACTED']:
                lead.status = 'MEETING'
                lead.save()
            
            ActivityTimeline.objects.create(
                lead=lead,
                action=f"Meeting Scheduled: {meeting_type}",
                notes=f"Scheduled for {date} at {time}. Notes: {notes}",
                performed_by=request.user
            )
            
            messages.success(request, f"Meeting with {lead.name} scheduled successfully!")
        except Exception as e:
            messages.error(request, f"Error scheduling meeting: {str(e)}")
            
    return redirect(request.META.get('HTTP_REFERER', 'meetings'))

@login_required
def delete_meeting(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    if request.method == 'POST':
        meeting.delete()
        messages.success(request, f"Meeting for '{meeting.lead.name}' deleted successfully.")
    return redirect('meetings')

@login_required
def reschedule_meeting(request, pk):
    if request.method == 'POST':
        meeting = get_object_or_404(Meeting, id=pk)
        date = request.POST.get('date')
        time = request.POST.get('time')
        
        try:
            dt_str = f"{date} {time}"
            new_date = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
            if timezone.is_naive(new_date):
                new_date = timezone.make_aware(new_date)
            
            meeting.date = new_date
            meeting.save()
            try:
                event_id = upsert_meeting_event(meeting)
                if event_id and meeting.google_calendar_event_id != event_id:
                    meeting.google_calendar_event_id = event_id
                    meeting.save(update_fields=['google_calendar_event_id'])
            except Exception as calendar_error:
                messages.warning(
                    request,
                    f"Meeting rescheduled but Google Calendar update failed: {calendar_error}"
                )

            ActivityTimeline.objects.create(
                lead=meeting.lead,
                action="Meeting Rescheduled",
                notes=f"Rescheduled to {date} at {time}",
                performed_by=request.user
            )
            
            messages.success(request, "Meeting rescheduled successfully!")
        except Exception as e:
            messages.error(request, f"Error rescheduling meeting: {str(e)}")
            
    return redirect('meetings')

@login_required
def quotations(request):
    quotation_list = Quotation.objects.select_related('lead', 'prepared_by').all().order_by('-created_at')
    dynamic_quotation_list = DynamicQuotation.objects.select_related('lead', 'created_by').all().order_by('-created_at')
    leads = Lead.objects.all().order_by('name')
    salespeople = User.objects.all().order_by('username')
    return render(request, 'crm_ui/quotations/index.html', {
        'quotations': quotation_list,
        'dynamic_quotations': dynamic_quotation_list,
        'leads': leads,
        'salespeople': salespeople,
    })

@login_required
def add_quotation(request):
    if request.method == 'POST':
        lead_id = request.POST.get('lead')
        total_amount = request.POST.get('total_amount')
        
        # Service item lists from form
        service_names = request.POST.getlist('service_name[]')
        quantities = request.POST.getlist('quantity[]')
        rates = request.POST.getlist('rate[]')
        item_totals = request.POST.getlist('item_total[]')
        section_titles = request.POST.getlist('section_title[]')
        section_contents = request.POST.getlist('section_content[]')
        prepared_by_id = request.POST.get('prepared_by')
        
        try:
            lead = get_object_or_404(Lead, id=lead_id)
            
            # Create Quotation
            quotation = Quotation.objects.create(
                lead=lead,
                amount=total_amount,
                prepared_by_id=prepared_by_id or None,
                status='PENDING'
            )
            
            # Create Quotation Items
            for i in range(len(service_names)):
                if service_names[i]: # Only if name is provided
                    QuotationItem.objects.create(
                        quotation=quotation,
                        service_name=service_names[i],
                        quantity=quantities[i],
                        rate=rates[i],
                        total=item_totals[i]
                    )

            # Save structured sections (as in final customer-facing quotations).
            for index, title in enumerate(section_titles):
                content = section_contents[index] if index < len(section_contents) else ""
                clean_title = (title or "").strip()
                clean_content = (content or "").strip()
                if not clean_title and not clean_content:
                    continue
                QuotationSection.objects.create(
                    quotation=quotation,
                    title=clean_title or f"Section {index + 1}",
                    content=clean_content,
                    sort_order=index + 1,
                )
            
            # Update lead status
            if lead.status in ['NEW', 'CONTACTED', 'MEETING']:
                lead.status = 'QUOTATION'
                lead.save()
            
            ActivityTimeline.objects.create(
                lead=lead,
                action="Quotation Generated",
                notes=f"Quote generated for ₹{total_amount}. Status: Pending Approval.",
                performed_by=request.user
            )
            
            messages.success(request, f"Quotation for {lead.name} generated successfully!")
        except Exception as e:
            messages.error(request, f"Error generating quotation: {str(e)}")
            
    return redirect(request.META.get('HTTP_REFERER', 'quotations'))


@login_required
def quotation_detail(request, pk):
    quotation = get_object_or_404(
        Quotation.objects.select_related('lead', 'prepared_by').prefetch_related('items', 'sections'),
        pk=pk,
    )
    return render(request, 'crm_ui/quotations/detail.html', {'quotation': quotation})

@login_required
def approve_quotation(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    try:
        quotation.status = 'APPROVED'
        quotation.save()

        pdf_generated = False
        try:
            from .utils import generate_quotation_pdf
            pdf_path = generate_quotation_pdf(quotation)
            quotation.pdf_file = pdf_path
            quotation.save(update_fields=['pdf_file'])
            pdf_generated = True
        except ImportError:
            messages.warning(
                request,
                "Quotation approved, but PDF generation is unavailable. Install 'reportlab' to enable PDFs."
            )
        except Exception as pdf_error:
            messages.warning(
                request,
                f"Quotation approved, but PDF generation failed: {pdf_error}"
            )
        
        ActivityTimeline.objects.create(
            lead=quotation.lead,
            action="Quotation Approved",
            notes=(
                f"Quotation QTN-{quotation.created_at.year}-{quotation.id:03d} approved"
                + (" and PDF generated." if pdf_generated else ".")
            ),
            performed_by=request.user
        )
        
        if pdf_generated:
            messages.success(request, "Quotation approved and PDF generated!")
        else:
            messages.success(request, "Quotation approved successfully!")
    except Exception as e:
        messages.error(request, f"Error approving quotation: {str(e)}")
        
    return redirect('quotations')

@login_required
def reject_quotation(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    quotation.status = 'REJECTED'
    quotation.save()
    
    ActivityTimeline.objects.create(
        lead=quotation.lead,
        action="Quotation Rejected",
        notes=f"Quotation for ₹{quotation.amount} was rejected.",
        performed_by=request.user
    )
    
    messages.warning(request, "Quotation has been rejected.")
    return redirect('quotations')


@login_required
def download_quotation_pdf(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)

    try:
        # If PDF is missing, generate it on-demand to avoid "not available yet" state.
        if not quotation.pdf_file or not quotation.pdf_file.name:
            from .utils import generate_quotation_pdf
            quotation.pdf_file = generate_quotation_pdf(quotation)
            quotation.save(update_fields=['pdf_file'])
        elif not quotation.pdf_file.storage.exists(quotation.pdf_file.name):
            from .utils import generate_quotation_pdf
            quotation.pdf_file = generate_quotation_pdf(quotation)
            quotation.save(update_fields=['pdf_file'])

        file_path = quotation.pdf_file.path
        if not os.path.exists(file_path):
            raise Http404("Generated PDF file could not be found.")

        return FileResponse(
            open(file_path, "rb"),
            as_attachment=True,
            filename=os.path.basename(file_path),
            content_type="application/pdf",
        )
    except Exception as e:
        messages.error(request, f"Unable to download quotation PDF: {e}")
        return redirect('quotations')

@login_required
def site_visits(request):
    visit_list = SiteVisit.objects.all().order_by('-date')
    leads = Lead.objects.all().order_by('name')
    return render(request, 'crm_ui/site_visits/index.html', {
        'site_visits': visit_list,
        'leads': leads
    })

@login_required
def add_site_visit(request):
    if request.method == 'POST':
        lead_id = request.POST.get('lead')
        date = request.POST.get('date')
        time = request.POST.get('time')
        address = request.POST.get('address')
        notes = request.POST.get('notes')
        
        try:
            lead = get_object_or_404(Lead, id=lead_id)
            import datetime
            dt_str = f"{date} {time}"
            visit_date = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
            
            visit = SiteVisit.objects.create(
                lead=lead,
                date=visit_date,
                feedback=f"Address: {address}\nNotes: {notes}"
            )

            try:
                event_id = upsert_site_visit_event(visit)
                if event_id:
                    visit.google_calendar_event_id = event_id
                    visit.save(update_fields=['google_calendar_event_id'])
            except Exception as calendar_error:
                messages.warning(
                    request,
                    f"Site visit scheduled but Google Calendar sync failed: {calendar_error}"
                )
            
            # Update lead status if not already advanced
            if lead.status in ['NEW', 'CONTACTED', 'MEETING']:
                lead.status = 'MEETING' # Site visit is a type of meeting/engagement
                lead.save()
            
            ActivityTimeline.objects.create(
                lead=lead,
                action="Site Visit Scheduled",
                notes=f"Scheduled for {date} at {time}. Address: {address}. Sync: {'Success' if visit.google_calendar_event_id else 'Failed'}",
                performed_by=request.user
            )
            
            messages.success(request, f"Site visit for {lead.name} scheduled successfully!")
        except Exception as e:
            messages.error(request, f"Error scheduling site visit: {str(e)}")
            
    return redirect(request.META.get('HTTP_REFERER', 'site_visits'))

@login_required
def delete_site_visit(request, pk):
    visit = get_object_or_404(SiteVisit, pk=pk)
    if request.method == 'POST':
        visit.delete()
        messages.success(request, f"Site visit for '{visit.lead.name}' deleted successfully.")
    return redirect('site_visits')

@login_required
def add_site_visit_feedback(request):
    if request.method == 'POST':
        visit_id = request.POST.get('visit_id')
        overall_impression = request.POST.get('overall_impression', '').strip()
        detailed_feedback = request.POST.get('detailed_feedback', '').strip()
        next_action = request.POST.get('next_action', '').strip()

        try:
            visit = get_object_or_404(SiteVisit, pk=visit_id)
            existing_feedback = visit.feedback or ''
            new_feedback = (
                f"Overall Impression: {overall_impression}\n"
                f"Detailed Feedback: {detailed_feedback}\n"
                f"Next Action Step: {next_action or 'None'}\n"
                f"Submitted by: {request.user.username}"
            )
            visit.feedback = f"{existing_feedback}\n\n---\n{new_feedback}".strip()
            visit.save(update_fields=['feedback'])

            ActivityTimeline.objects.create(
                lead=visit.lead,
                action="Site Visit Feedback Submitted",
                notes=f"{overall_impression} / {next_action or 'No next action specified'}",
                performed_by=request.user
            )

            messages.success(request, "Site visit feedback submitted successfully!")
        except Exception as e:
            messages.error(request, f"Error submitting feedback: {str(e)}")

    return redirect('site_visits')


def _get_post_login_redirect(user):
    """Determine where to send a user after successful login."""
    if not user.is_approved:
        return 'pending_approval'
    if user.is_admin_role:
        return 'admin_dashboard'
    return 'dashboard'


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_get_post_login_redirect(request.user))
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(_get_post_login_redirect(user))
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = UserLoginForm()
        
    return render(request, 'crm_ui/registration/login.html', {'form': form})

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_approved = False
            user.save()
            messages.success(request, "Account created! Your account is pending admin approval.")
            return redirect('login')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = UserRegistrationForm()
        
    return render(request, 'crm_ui/registration/signup.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


def google_login_view(request):
    """Handle Google Sign-In callback. Receives credential via hidden form POST."""
    if request.method != 'POST':
        return redirect('login')
    
    # Get credential from form POST (hidden form) or JSON body
    credential = request.POST.get('credential', '')
    if not credential:
        try:
            body = json.loads(request.body)
            credential = body.get('credential', '')
        except (json.JSONDecodeError, AttributeError):
            pass

    if not credential:
        messages.error(request, 'Google sign-in failed. No credential received.')
        return redirect('login')

    from accounts.google_auth import verify_google_token
    id_info = verify_google_token(credential)
    if id_info is None:
        messages.error(request, 'Google sign-in failed. Invalid token.')
        return redirect('login')

    google_id = id_info.get('sub')
    email = id_info.get('email', '')
    first_name = id_info.get('given_name', '')
    last_name = id_info.get('family_name', '')
    full_name = id_info.get('name', '')

    # Try to find existing user by google_id or email
    user = User.objects.filter(google_id=google_id).first()
    if not user and email:
        user = User.objects.filter(email=email).first()
        if user:
            user.google_id = google_id
            user.save(update_fields=['google_id'])

    if not user:
        # Create new user — requires admin approval
        username = email.split('@')[0] if email else f'google_{google_id[:8]}'
        # Ensure unique username
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            google_id=google_id,
            role='SALES',
            is_approved=False,
        )
        user.set_unusable_password()
        user.save()
        messages.success(request, f"Account created for {full_name}! Awaiting admin approval.")
        login(request, user)
        return redirect('pending_approval')

    login(request, user)
    messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
    return redirect(_get_post_login_redirect(user))


@login_required
def pending_approval_view(request):
    """Show a 'pending approval' page for unapproved users."""
    if request.user.is_approved:
        return redirect(_get_post_login_redirect(request.user))
    return render(request, 'crm_ui/registration/pending.html')


# ──────────────────────────────────────────────
#  ADMIN PANEL VIEWS
# ──────────────────────────────────────────────
from functools import wraps

def admin_required(view_func):
    """Decorator: login required + must be ADMIN role."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_admin_role:
            messages.error(request, 'You do not have permission to access the admin panel.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


@admin_required
def admin_dashboard(request):
    """Admin panel landing — redirect to approvals."""
    return redirect('admin_user_approvals')


@admin_required
def admin_user_approvals(request):
    """List all users for approval management."""
    users = User.objects.all().order_by('-date_joined')
    pending_count = users.filter(is_approved=False).count()
    return render(request, 'crm_ui/admin/approvals.html', {
        'users': users,
        'pending_count': pending_count,
    })


@admin_required
def admin_approve_user(request, pk, action):
    """Approve or reject a user."""
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=pk)
        if action == 'approve':
            target_user.is_approved = True
            target_user.save(update_fields=['is_approved'])
            messages.success(request, f"User '{target_user.username}' has been approved.")
        elif action == 'reject':
            target_user.is_approved = False
            target_user.is_active = False
            target_user.save(update_fields=['is_approved', 'is_active'])
            messages.warning(request, f"User '{target_user.username}' has been rejected.")
    return redirect('admin_user_approvals')

@admin_required
def admin_update_user_role(request, pk):
    """Update a user's role from the admin panel."""
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=pk)
        new_role = request.POST.get('role')
        if new_role in [User.ADMIN, User.MANAGER, User.SALES]:
            target_user.role = new_role
            target_user.save(update_fields=['role'])
            messages.success(request, f"Updated {target_user.username}'s role to {new_role}.")
    return redirect('admin_user_approvals')


@admin_required
def admin_stats(request):
    """System-wide statistics for the admin panel."""
    from django.db.models import Sum
    from django.db.models.functions import TruncDate
    from quotation.models import Quotation as DynQuotation

    total_users = User.objects.count()
    pending_users = User.objects.filter(is_approved=False).count()
    approved_users = User.objects.filter(is_approved=True).count()
    total_leads = Lead.objects.count()
    total_meetings = Meeting.objects.count()
    total_quotations = Quotation.objects.count() + DynQuotation.objects.count()
    closed_deals = Lead.objects.filter(status='CLOSED').count()
    lost_deals = Lead.objects.filter(status='LOST').count()
    conversion_rate = round((closed_deals / total_leads) * 100, 1) if total_leads > 0 else 0

    # Status breakdown
    status_counts = Lead.objects.values('status').annotate(count=Count('status'))
    status_data = {item['status']: item['count'] for item in status_counts}
    all_statuses = ['NEW', 'CONTACTED', 'MISSED_CALL', 'MEETING', 'QUOTATION', 'DISCUSSION', 'CLOSED', 'LOST']
    status_summary = {s: status_data.get(s, 0) for s in all_statuses}

    # 30-day lead trend
    trend_raw = Lead.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).annotate(date=TruncDate('created_at')).values('date').annotate(count=Count('id')).order_by('date')
    trend_labels = []
    trend_data = []
    for i in range(29, -1, -1):
        d = timezone.localdate() - timezone.timedelta(days=i)
        trend_labels.append(d.strftime('%b %d'))
        count = next((item['count'] for item in trend_raw if item['date'] == d), 0)
        trend_data.append(count)

    # User registrations last 30 days
    user_reg_raw = User.objects.filter(
        date_joined__gte=timezone.now() - timezone.timedelta(days=30)
    ).annotate(date=TruncDate('date_joined')).values('date').annotate(count=Count('id')).order_by('date')
    user_reg_data = []
    for i in range(29, -1, -1):
        d = timezone.localdate() - timezone.timedelta(days=i)
        count = next((item['count'] for item in user_reg_raw if item['date'] == d), 0)
        user_reg_data.append(count)

    # Source distribution
    source_counts = Lead.objects.values('source').annotate(count=Count('source'))
    source_summary = {item['source']: item['count'] for item in source_counts}

    context = {
        'total_users': total_users,
        'pending_users': pending_users,
        'approved_users': approved_users,
        'total_leads': total_leads,
        'total_meetings': total_meetings,
        'total_quotations': total_quotations,
        'closed_deals': closed_deals,
        'lost_deals': lost_deals,
        'conversion_rate': conversion_rate,
        'status_summary': status_summary,
        'trend_labels': trend_labels,
        'trend_data': trend_data,
        'user_reg_data': user_reg_data,
        'source_summary': source_summary,
    }
    return render(request, 'crm_ui/admin/stats.html', context)

@login_required
def add_lead(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = (request.POST.get('phone') or '').strip()
        email = request.POST.get('email')
        source = request.POST.get('source')
        property_type = request.POST.get('property_type')
        budget = request.POST.get('budget') or 0
        execution_timeline = request.POST.get('execution_timeline')
        location = request.POST.get('location')
        assigned_to_id = request.POST.get('assigned_to')
        notes = request.POST.get('notes')

        # Friendly validation before DB write to avoid raw constraint errors in UI.
        if phone and Lead.objects.filter(phone=phone).exists():
            messages.error(request, f"A lead with phone '{phone}' already exists.")
            return redirect('lead_list')

        try:
            lead = Lead.objects.create(
                name=name,
                phone=phone,
                email=email,
                property_type=property_type,
                budget=budget,
                execution_timeline=execution_timeline,
                source=source,
                location=location,
                assigned_to_id=assigned_to_id,
                status='NEW'
            )
            
            # Mark imported lead as converted if applicable
            import_id = request.POST.get('import_id')
            if import_id:
                LeadImport.objects.filter(id=import_id).update(is_converted=True)
            
            # Create initial activity
            ActivityTimeline.objects.create(
                lead=lead,
                action="Lead Created",
                notes=f"Initial contact details saved. Notes: {notes}",
                performed_by=request.user
            )

            followup = schedule_callback_followup(lead, notes)
            if followup is not None:
                messages.success(
                    request,
                    f"Lead '{name}' created successfully! Callback reminder scheduled for {followup.date.strftime('%b %d, %I:%M %p')}"
                )
            else:
                messages.success(request, f"Lead '{name}' created successfully!")
        except IntegrityError:
            messages.error(request, "Lead could not be created. Phone number must be unique.")
        except Exception as e:
            messages.error(request, f"Error creating lead: {str(e)}")
            
        return redirect('lead_list')
    
    return redirect('dashboard')

@login_required
def edit_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        location = request.POST.get('location')
        property_type = request.POST.get('property_type')
        budget = request.POST.get('budget')
        execution_timeline = request.POST.get('execution_timeline')
        assigned_to_id = request.POST.get('assigned_to')
        status = request.POST.get('status')
        
        try:
            old_status = lead.status
            lead.name = name
            lead.phone = phone
            lead.email = email
            lead.location = location
            lead.property_type = property_type
            lead.budget = budget or 0
            lead.execution_timeline = execution_timeline
            lead.assigned_to_id = assigned_to_id
            lead.status = status
            lead.save()
            
            # Log the change
            note_parts = []
            if old_status != status:
                note_parts.append(f"Status changed from {old_status} to {status}.")
            
            ActivityTimeline.objects.create(
                lead=lead,
                action="Lead Details Updated",
                notes=f"Updated lead information. {' '.join(note_parts)}",
                performed_by=request.user
            )
            
            messages.success(request, f"Lead '{name}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating lead: {str(e)}")
            
    return redirect('lead_detail', pk=pk)

@login_required
def upload_requirements(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        floor_plan_2d = request.FILES.get('floor_plan_2d')
        floor_plan_3d = request.FILES.get('floor_plan_3d')
        
        try:
            if floor_plan_2d:
                lead.floor_plan_2d = floor_plan_2d
            if floor_plan_3d:
                lead.floor_plan_3d = floor_plan_3d
            
            if floor_plan_2d or floor_plan_3d:
                lead.save()
                
                # Log activity
                files_str = []
                if floor_plan_2d: files_str.append("2D Plan")
                if floor_plan_3d: files_str.append("3D Plan")
                
                ActivityTimeline.objects.create(
                    lead=lead,
                    action="Requirements Uploaded",
                    notes=f"Uploaded technical files: {', '.join(files_str)}",
                    performed_by=request.user
                )
                messages.success(request, "Technical requirements uploaded successfully!")
            else:
                messages.warning(request, "No files were selected for upload.")
                
        except Exception as e:
            messages.error(request, f"Error uploading files: {str(e)}")
            
    return redirect('lead_detail', pk=pk)
@login_required
def missed_leads(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        source = request.POST.get('source')
        
        MissedLead.objects.create(
            name=name,
            phone=phone,
            source=source,
            call_status='Missed'
        )
        messages.success(request, f"Missed call from {phone} logged successfully.")
        return redirect('missed_leads')
        
    missed_leads_list = MissedLead.objects.all().order_by('-timestamp')
    return render(request, 'crm_ui/leads/missed.html', {'missed_leads': missed_leads_list})

