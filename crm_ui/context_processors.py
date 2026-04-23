from django.contrib.auth import get_user_model
from django.conf import settings
from crm_api.models import Lead, LeadImport

User = get_user_model()

def global_context(request):
    """
    Provides global data to all templates, such as the list of salespeople and imported leads.
    """
    context = {
        'GOOGLE_CLIENT_ID': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
    }

    if request.user.is_authenticated:
        # Fetching all users who can be assigned leads
        salespeople = User.objects.all() 
        # Fetching latest 100 imports for the selector (all statuses)
        recent_imports = LeadImport.objects.all().order_by('-timestamp')[:100]
        
        context.update({
            'global_salespeople': salespeople,
            'global_recent_imports': recent_imports,
        })

    return context
