from rest_framework import serializers
from .models import (
    Lead, Meeting, Quotation, FollowUp, SiteVisit,
    ActivityTimeline, Project, ProjectLog
)
from django.contrib.auth import get_user_model

User = get_user_model()

class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'role')


class ActivityTimelineSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    
    class Meta:
        model = ActivityTimeline
        fields = '__all__'


class MeetingSerializer(serializers.ModelSerializer):
    meeting_time = serializers.DateTimeField(source='date', read_only=True)

    class Meta:
        model = Meeting
        fields = '__all__'


class QuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = '__all__'


class FollowUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUp
        fields = '__all__'


class SiteVisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteVisit
        fields = '__all__'


class ProjectLogSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = ProjectLog
        fields = '__all__'


class ProjectSerializer(serializers.ModelSerializer):
    logs = ProjectLogSerializer(many=True, read_only=True)
    lead_name = serializers.CharField(source='lead.name', read_only=True)
    
    class Meta:
        model = Project
        fields = '__all__'


class LeadSerializer(serializers.ModelSerializer):
    timeline = ActivityTimelineSerializer(many=True, read_only=True)
    assigned_to_details = UserMinimalSerializer(source='assigned_to', read_only=True)
    
    class Meta:
        model = Lead
        fields = '__all__'

    def validate_phone(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Phone number must contain only digits.")
        return value
