from django import template
from django.core.exceptions import ObjectDoesNotExist

register = template.Library()

@register.filter
def has_partner_profile(user):
    """
    Safely checks if the user has a partner_profile.
    Returns False for AnonymousUser or User without profile.
    """
    if not user.is_authenticated:
        return False
    
    try:
        return hasattr(user, 'partner_profile') and user.partner_profile is not None
    except (ObjectDoesNotExist, AttributeError):
        return False
