from django.core.exceptions import PermissionDenied
from django.conf import settings

class AdminIPWhitelistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            allowed_ips = getattr(settings, 'ADMIN_ALLOWED_IPS', [])
            if allowed_ips:
                ip = request.META.get('REMOTE_ADDR')
                # Check for X-Forwarded-For if behind a proxy
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0]
                
                if ip not in allowed_ips:
                    raise PermissionDenied
        
        return self.get_response(request)
