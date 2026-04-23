from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/add/', views.add_lead, name='add_lead'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('leads/<int:pk>/edit/', views.edit_lead, name='edit_lead'),
    path('leads/<int:pk>/delete/', views.delete_lead, name='delete_lead'),
    path('leads/<int:pk>/upload/', views.upload_requirements, name='upload_requirements'),
    path('meetings/', views.meetings, name='meetings'),
    path('meetings/add/', views.add_meeting, name='add_meeting'),
    path('meetings/<int:pk>/reschedule/', views.reschedule_meeting, name='reschedule_meeting'),
    path('meetings/<int:pk>/delete/', views.delete_meeting, name='delete_meeting'),
    path('quotations/', views.quotations, name='quotations'),
    path('quotations/add/', views.add_quotation, name='add_quotation'),
    path('quotations/<int:pk>/', views.quotation_detail, name='quotation_detail'),
    path('quotations/approve/<int:pk>/', views.approve_quotation, name='approve_quotation'),
    path('quotations/reject/<int:pk>/', views.reject_quotation, name='reject_quotation'),
    path('quotations/<int:pk>/download-pdf/', views.download_quotation_pdf, name='download_quotation_pdf'),
    path('site-visits/', views.site_visits, name='site_visits'),
    path('site-visits/add/', views.add_site_visit, name='add_site_visit'),
    path('site-visits/<int:pk>/delete/', views.delete_site_visit, name='delete_site_visit'),
    path('site-visits/feedback/', views.add_site_visit_feedback, name='add_site_visit_feedback'),
    path('leads/missed/', views.missed_leads, name='missed_leads'),
    path('signup/', views.signup_view, name='signup'),
    path('google-login/', views.google_login_view, name='google_login'),
    path('pending/', views.pending_approval_view, name='pending_approval'),

    # Admin Panel
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/approvals/', views.admin_user_approvals, name='admin_user_approvals'),
    path('admin-panel/approvals/<int:pk>/<str:action>/', views.admin_approve_user, name='admin_approve_user'),
    path('admin-panel/user/<int:pk>/update-role/', views.admin_update_user_role, name='admin_update_user_role'),
    path('admin-panel/stats/', views.admin_stats, name='admin_stats'),
]
