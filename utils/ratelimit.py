"""
Rate limiting utilities for Project Imara.
Uses django-ratelimit for protecting high-risk endpoints.
"""
from functools import wraps
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited


def get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def ratelimit_key(group, request):
    """Rate limit by IP address."""
    return get_client_ip(request)


# Pre-configured rate limit decorators for common use cases
def login_ratelimit(view_func):
    """Rate limit login attempts: 5 per minute per IP."""
    return ratelimit(key='ip', rate='5/m', method='POST', block=True)(view_func)


def form_ratelimit(view_func):
    """Rate limit form submissions: 10 per minute per IP."""
    return ratelimit(key='ip', rate='10/m', method='POST', block=True)(view_func)


def api_ratelimit(view_func):
    """Rate limit API calls: 30 per minute per IP."""
    return ratelimit(key='ip', rate='30/m', block=True)(view_func)


def telegram_webhook_ratelimit(view_func):
    """Rate limit Telegram webhooks: 60 per minute (Telegram sends frequent updates)."""
    return ratelimit(key='ip', rate='60/m', method='POST', block=True)(view_func)


def handle_ratelimit_error(request, exception):
    """Handle rate limit exceeded - return 429 response."""
    return JsonResponse({
        'error': 'Rate limit exceeded. Please try again later.',
        'retry_after': 60
    }, status=429)
