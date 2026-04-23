import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tele_crm.settings')
django.setup()

from accounts.models import User

def seed_users():
    users_to_create = [
        {
            'username': 'jay_solanki',
            'first_name': 'Jay',
            'last_name': 'Solanki',
            'email': 'jay@mynest.me',
            'role': 'ADMIN',
            'password': 'AdminPassword123!'
        },
        {
            'username': 'om_pandya',
            'first_name': 'Om',
            'last_name': 'Pandya',
            'email': 'om@mynest.me',
            'role': 'SALES',
            'password': 'OmPassword123!'
        },
        {
            'username': 'montu_chavda',
            'first_name': 'Montu',
            'last_name': 'Chavda',
            'email': 'montu@mynest.me',
            'role': 'ADMIN',
            'password': 'MontuPassword123!'
        }
    ]

    for user_data in users_to_create:
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'email': user_data['email'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'role': user_data['role']
            }
        )
        if created:
            user.set_password(user_data['password'])
            user.save()
            print(f"User {user.username} created successfully.")
        else:
            print(f"User {user.username} already exists.")

if __name__ == "__main__":
    seed_users()
