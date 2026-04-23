from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Lead, Meeting, Quotation, FollowUp, SiteVisit,
    ActivityTimeline, Project, ProjectLog
)
from .serializers import (
    LeadSerializer, MeetingSerializer, QuotationSerializer, 
    FollowUpSerializer, SiteVisitSerializer, ActivityTimelineSerializer,
    ProjectSerializer, ProjectLogSerializer
)
from .permissions import IsAssignedSalesOrManager, IsManager

class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'source', 'assigned_to']
    search_fields = ['name', 'phone', 'email']
    ordering_fields = ['created_at', 'budget']
    permission_classes = [permissions.IsAuthenticated, IsAssignedSalesOrManager]

    def get_queryset(self):
        user = self.request.user
        # Admin and Managers see all leads
        if user.role in ['ADMIN', 'MANAGER']:
            return Lead.objects.all()
        # Sales Executives only see assigned leads
        return Lead.objects.filter(assigned_to=user)

    def perform_create(self, serializer):
        # Default assignment to the person creating the lead if they are SALES
        if self.request.user.role == 'SALES':
            serializer.save(assigned_to=self.request.user)
        else:
            serializer.save()


class MeetingViewSet(viewsets.ModelViewSet):
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = [permissions.IsAuthenticated, IsAssignedSalesOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return Meeting.objects.all()
        return Meeting.objects.filter(lead__assigned_to=user)

    def perform_create(self, serializer):
        assigned_user = serializer.validated_data.get("assigned_user") or self.request.user
        serializer.save(assigned_user=assigned_user, created_by=self.request.user)


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.all()
    serializer_class = QuotationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAssignedSalesOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return Quotation.objects.all()
        return Quotation.objects.filter(lead__assigned_to=user)


class FollowUpViewSet(viewsets.ModelViewSet):
    queryset = FollowUp.objects.all()
    serializer_class = FollowUpSerializer
    permission_classes = [permissions.IsAuthenticated, IsAssignedSalesOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return FollowUp.objects.all()
        return FollowUp.objects.filter(lead__assigned_to=user)


class SiteVisitViewSet(viewsets.ModelViewSet):
    queryset = SiteVisit.objects.all()
    serializer_class = SiteVisitSerializer
    permission_classes = [permissions.IsAuthenticated, IsAssignedSalesOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return SiteVisit.objects.all()
        return SiteVisit.objects.filter(lead__assigned_to=user)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'lead']
    search_fields = ['project_name']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Admins and Managers see all projects
        if user.role in ['ADMIN', 'MANAGER']:
            return Project.objects.all()
        # Sales Executives see projects for their assigned leads
        return Project.objects.filter(lead__assigned_to=user)


class ProjectLogViewSet(viewsets.ModelViewSet):
    queryset = ProjectLog.objects.all()
    serializer_class = ProjectLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return ProjectLog.objects.all()
        return ProjectLog.objects.filter(project__lead__assigned_to=user)

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)


class ActivityTimelineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityTimeline.objects.all()
    serializer_class = ActivityTimelineSerializer
    permission_classes = [permissions.IsAuthenticated, IsAssignedSalesOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return ActivityTimeline.objects.all()
        return ActivityTimeline.objects.filter(lead__assigned_to=user)
