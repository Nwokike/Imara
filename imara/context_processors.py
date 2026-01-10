"""
Context processors for Project Imara.
Provides global template variables.
"""
from django.conf import settings


def turnstile_context(request):
    """
    Makes Turnstile site key available to all templates.
    """
    return {
        'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', ''),
    }
