import os
import django
import sys

# Set up Django environment to access settings
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tele_crm.settings')
django.setup()

from django.conf import settings
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main():
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', None)
    
    if not client_id or not client_secret:
        print("Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in your .env file.")
        return

    # Construct the client config from settings
    # We use 'web' type as per your JSON, but we'll use a local redirect for the script
    client_config = {
        "installed": { # Use 'installed' app type for script-based auth
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        
        print("\n" + "="*60)
        print("GOOGLE CALENDAR AUTHENTICATION")
        print("="*60)
        print("\n1. A browser window will open shortly.")
        print("2. Log in with your Google Account.")
        print("3. Click 'Continue' or 'Allow' to grant TeleCRM access to your calendar.")
        print("\nStarting local authentication server...")
        
        # We use a fixed port that is likely to be free
        creds = flow.run_local_server(port=0, success_message="Authentication successful! You can close this window.")
        
        if creds and creds.refresh_token:
            print("\n" + "="*60)
            print("SUCCESS! COPY THE REFRESH TOKEN BELOW:")
            print("-" * 60)
            print(f"\n{creds.refresh_token}\n")
            print("-" * 60)
            print("\nACTION REQUIRED:")
            print("Copy the long token above and paste it into your .env file:")
            print("GOOGLE_REFRESH_TOKEN=your_token_here")
            print("="*60 + "\n")
        else:
            print("\nERROR: Authentication successful, but no Refresh Token was returned.")
            print("NOTE: This can happen if you already authorized this app. ")
            print("Try removing 'TeleCRM' from your Google Account security settings and run this again.")
            
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
