"""
Lightweight Rate Limiting for Project Imara (2026).
Uses Django's native cache to implement a simple and efficient 
rate limiter without extra dependencies.
"""
import time
import logging
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')

def rate_limit(rate="10/m", key_prefix="rl"):
    """
    Custom decorator for rate limiting using Django cache.
    Format: 'number/period' (e.g., '5/m', '100/h', '1000/d')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if settings.DEBUG:
                return view_func(request, *args, **kwargs)

            # Parse rate
            num_requests, period = rate.split('/')
            num_requests = int(num_requests)
            
            # Map period to seconds
            seconds = 60
            if period == 's': seconds = 1
            elif period == 'm': seconds = 60
            elif period == 'h': seconds = 3600
            elif period == 'd': seconds = 86400

            # Generate key
            ip = get_client_ip(request)
            cache_key = f"{key_prefix}:{ip}:{int(time.time() / seconds)}"
            
            # Count requests
            request_count = cache.get(cache_key, 0)
            
            if request_count >= num_requests:
                logger.warning(f"Rate limit exceeded for IP: {ip}")
                return JsonResponse({
                    'error': 'Rate limit exceeded. Please try again later.',
                    'retry_after': seconds
                }, status=429)
            
            cache.set(cache_key, request_count + 1, seconds)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# Pre-configured decorators
def login_ratelimit(view_func):
    return rate_limit(rate='5/m', key_prefix='login')(view_func)

def form_ratelimit(view_func):
    return rate_limit(rate='10/m', key_prefix='form')(view_func)

def api_ratelimit(view_func):
    return rate_limit(rate='30/m', key_prefix='api')(view_func)

def telegram_webhook_ratelimit(view_func):
    # Telegram webhooks can be frequent, so 60/m is reasonable
    return rate_limit(rate='60/m', key_prefix='telegram')(view_func)

def handle_ratelimit_error(request, exception):
    """Fallback handler for generic rate limit errors."""
    return JsonResponse({
        'error': 'Rate limit exceeded. Please try again later.',
        'retry_after': 60
    }, status=429)
