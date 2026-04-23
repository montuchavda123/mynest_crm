"""
Google ID Token verification utility.
Uses the `google-auth` library to verify tokens issued by Google Identity Services.
"""
import logging
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_google_token(token):
    """
    Verify a Google ID token and return the user info dict.
    Returns None on failure.

    Returned dict keys (on success):
      - sub: unique Google user ID
      - email: user email
      - email_verified: bool
      - name: full name
      - given_name: first name
      - family_name: last name
      - picture: profile picture URL
    """
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        # Verify issuer
        if id_info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            logger.warning("Google token has invalid issuer: %s", id_info.get("iss"))
            return None

        return id_info

    except ValueError as e:
        logger.warning("Google token verification failed: %s", e)
        return None
