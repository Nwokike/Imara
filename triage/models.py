from django.db import models
from django.utils import timezone
from datetime import timedelta


class ChatSession(models.Model):
    chat_id = models.CharField(max_length=100, unique=True, db_index=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    platform = models.CharField(max_length=20, default='telegram')
    last_detected_location = models.CharField(max_length=255, blank=True, null=True)
    language_preference = models.CharField(max_length=10, blank=True, null=True)
    awaiting_location = models.BooleanField(default=False)
    pending_report_data = models.JSONField(blank=True, null=True)
    cancelled_until = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        
    def __str__(self):
        return f"Session {self.chat_id} - {self.username or 'Anonymous'}"
    
    def get_recent_messages(self, limit=10):
        return list(self.messages.order_by('-created_at')[:limit])[::-1]
    
    def get_conversation_context(self, limit=10):
        messages = self.get_recent_messages(limit)
        context = []
        for msg in messages:
            role = "User" if msg.role == 'user' else "Assistant"
            context.append(f"{role}: {msg.content[:500]}")
        return context
    
    def clear_pending_state(self):
        self.awaiting_location = False
        self.pending_report_data = None
        self.save()
    
    def is_cancelled(self):
        if self.cancelled_until and self.cancelled_until > timezone.now():
            return True
        return False
    
    def set_cancelled(self, seconds=30):
        self.cancelled_until = timezone.now() + timedelta(seconds=seconds)
        self.awaiting_location = False
        self.pending_report_data = None
        self.save()
    
    def clear_cancelled(self):
        self.cancelled_until = None
        self.save()


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    message_type = models.CharField(max_length=20, default='text')
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', '-created_at']),
        ]
        
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class UserFeedback(models.Model):
    RATING_CHOICES = [
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
    ]
    
    chat_id = models.CharField(max_length=100, db_index=True)
    message_id = models.CharField(max_length=100, blank=True, null=True)
    case_id = models.CharField(max_length=100, blank=True, null=True)
    rating = models.CharField(max_length=20, choices=RATING_CHOICES)
    context = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Feedback {self.chat_id} - {self.rating}"
