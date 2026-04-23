from rest_framework import permissions
from accounts.models import User

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.ADMIN

class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [User.ADMIN, User.MANAGER]

class IsTelecaller(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.TELECALLER

class IsViewer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.VIEWER

class IsAssignedSalesOrManager(permissions.BasePermission):
    """
    Allows Managers/Admins full access.
    Telecallers only have access if the lead is assigned to them.
    """
    def has_object_permission(self, request, view, obj):
        # Admins and Managers can see everything
        if request.user.role in [User.ADMIN, User.MANAGER]:
            return True
        
        # Lead object permission
        if hasattr(obj, 'assigned_to'):
            return obj.assigned_to == request.user
            
        # Related objects (Meeting, Quotation etc) permission
        if hasattr(obj, 'lead'):
            return obj.lead.assigned_to == request.user
            
        return False
