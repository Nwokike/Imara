import logging
import requests
from django.conf import settings
from typing import Tuple

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

def validate_turnstile(token: str, ip_address: str = None) -> Tuple[bool, str]:
    """
    Validates a Cloudflare Turnstile token.
    Returns (is_valid, error_message).
    """
    secret_key = getattr(settings, 'TURNSTILE_SECRET_KEY', None)
    
    if not secret_key:
        logger.warning("TURNSTILE_SECRET_KEY not set. Skipping validation (OPEN MODE).")
        return True, ""

    if not token:
        return False, "CAPTCHA verification failed. Please refresh and try again."

    payload = {
        'secret': secret_key,
        'response': token,
        'remoteip': ip_address
    }

    try:
        response = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=5)
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            return True, ""
        else:
            error_codes = result.get('error-codes', [])
            logger.warning(f"Turnstile validation failed: {error_codes}")
            return False, "Security check failed. Please try again."
            
    except requests.RequestException as e:
        logger.error(f"Turnstile API connection error: {e}")
        # Fail open or closed depending on security posture? 
        # For a safety app, we often fail open if the security service is down, but log heavily.
        # User said "maximizing free options", suggesting robust handling is needed.
        return False, "Security service unreachable. Please try again later."
