from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LeadViewSet, MeetingViewSet, QuotationViewSet, 
    FollowUpViewSet, SiteVisitViewSet, ActivityTimelineViewSet,
    ProjectViewSet, ProjectLogViewSet
)

router = DefaultRouter()
router.register(r'leads', LeadViewSet, basename='lead')
router.register(r'meetings', MeetingViewSet, basename='meeting')
router.register(r'quotations', QuotationViewSet, basename='quotation')
router.register(r'followups', FollowUpViewSet, basename='followup')
router.register(r'site-visits', SiteVisitViewSet, basename='site-visit')
router.register(r'timeline', ActivityTimelineViewSet, basename='timeline')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'project-logs', ProjectLogViewSet, basename='project-log')

urlpatterns = [
    path('', include(router.urls)),
]
