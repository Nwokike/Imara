"""
Custom Authentication Backend for Project Imara

Allows users to log in with either their email address or username.
This provides flexibility for partner users who may prefer using their email.
"""

import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows login with email or username.
    
    This backend:
    1. First attempts to find user by username
    2. If not found, attempts to find user by email
    3. Validates password and returns user if successful
    
    Works seamlessly with Django's built-in auth system.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user with username OR email.
        
        Args:
            request: The HTTP request
            username: Can be either username or email
            password: The user's password
            
        Returns:
            User object if authentication succeeds, None otherwise
        """
        if username is None or password is None:
            return None
        
        # Normalize to lowercase for email comparison
        username_lower = username.lower().strip()
        
        user = None
        
        # Try to find by username first (exact match)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            pass
        
        # If not found, try to find by email
        if user is None:
            try:
                user = User.objects.get(email__iexact=username_lower)
            except User.DoesNotExist:
                pass
            except User.MultipleObjectsReturned:
                # If multiple users have the same email (shouldn't happen but defensive)
                logger.warning(f"Multiple users found with email: {username_lower}")
                return None
        
        # If user found, check password
        if user is not None:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        
        return None
    
    def get_user(self, user_id):
        """
        Get user by ID for session authentication.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
