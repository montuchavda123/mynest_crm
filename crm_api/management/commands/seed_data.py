from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from crm_api.models import Lead, Meeting, Quotation, FollowUp, ActivityTimeline, Project
from django.utils import timezone
import random
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with sample CRM data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')
        
        # 1. Ensure Admin User
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
        )
        if created:
            admin.set_password('adminpassword')
            admin.save()
            self.stdout.write('Created superuser: admin/adminpassword')

        # 2. Create Sales User
        sales_user, _ = User.objects.get_or_create(
            username='anita',
            defaults={'role': 'SALES', 'first_name': 'Anita', 'last_name': 'Roy'}
        )
        
        # 3. Create Sample Leads
        leads_data = [
            {'name': 'Rahul Sharma', 'phone': '9876543210', 'budget': 500000, 'location': 'Mumbai', 'source': 'WEBSITE', 'status': 'NEW'},
            {'name': 'Vikram Bajaj', 'phone': '9876543211', 'budget': 850000, 'location': 'Delhi', 'source': 'SOCIAL_MEDIA', 'status': 'MEETING'},
            {'name': 'Sunita Gupta', 'phone': '9876543212', 'budget': 1200000, 'location': 'Pune', 'source': 'REFERRAL', 'status': 'QUOTATION'},
            {'name': 'Amit Kumar', 'phone': '9876543213', 'budget': 300000, 'location': 'Mumbai', 'source': 'WALK_IN', 'status': 'CLOSED'},
            {'name': 'Priya Singh', 'phone': '9876543214', 'budget': 600000, 'location': 'Bangalore', 'source': 'WEBSITE', 'status': 'CONTACTED'},
        ]

        for data in leads_data:
            lead, created = Lead.objects.update_or_create(
                phone=data['phone'],
                defaults={
                    'name': data['name'],
                    'budget': Decimal(data['budget']),
                    'location': data['location'],
                    'source': data['source'],
                    'status': data['status'],
                    'assigned_to': sales_user
                }
            )
            
            # Create a Timeline entry for each
            ActivityTimeline.objects.get_or_create(
                lead=lead,
                action="Lead Seeding",
                notes=f"Initial seed data for {lead.name}",
                performed_by=admin
            )

        # 4. Create Sample Meetings
        meeting_lead = Lead.objects.get(phone='9876543211')
        Meeting.objects.get_or_create(
            lead=meeting_lead,
            type='SITE',
            date=timezone.now() + timezone.timedelta(days=2),
            defaults={'notes': 'Detailed site measurement and requirement gathering.'}
        )

        # 5. Create Sample Quotation
        quote_lead = Lead.objects.get(phone='9876543212')
        Quotation.objects.get_or_create(
            lead=quote_lead,
            amount=Decimal('450000.00'),
            defaults={'description': 'Full 2BHK Interior Design Quote', 'status': 'PENDING'}
        )
        
        # 6. Create Sample Followup
        FollowUp.objects.get_or_create(
            lead=Lead.objects.first(),
            date=timezone.now() + timezone.timedelta(hours=5),
            defaults={'notes': 'Call back to confirm budget expectations.'}
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded CRM data!'))
