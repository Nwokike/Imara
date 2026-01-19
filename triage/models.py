from django.db import models
from django.utils import timezone
from datetime import timedelta


class ChatSession(models.Model):
    """
    Represents a conversation session with a user.
    Platform-agnostic design for Telegram, WhatsApp, Discord, Instagram, etc.
    """
    
    class State(models.TextChoices):
        IDLE = 'IDLE', 'Waiting for input'
        GATHERING = 'GATHERING', 'Gathering information'
        ASKING_LOCATION = 'ASKING_LOCATION', 'Waiting for location'
        CONFIRMING = 'CONFIRMING', 'Asking for confirmation'
        PROCESSING = 'PROCESSING', 'Processing report'
    
    class Platform(models.TextChoices):
        TELEGRAM = 'telegram', 'Telegram'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        INSTAGRAM = 'instagram', 'Instagram'
        MESSENGER = 'messenger', 'Facebook Messenger'
        DISCORD = 'discord', 'Discord'
        WEB = 'web', 'Web Portal'
    
    # Unique identifier per platform (chat_id for Telegram, phone for WhatsApp, etc.)
    chat_id = models.CharField(max_length=100, db_index=True)
    platform = models.CharField(
        max_length=20, 
        choices=Platform.choices, 
        default=Platform.TELEGRAM
    )
    username = models.CharField(max_length=255, blank=True, null=True)
    
    # Conversation state machine
    conversation_state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.IDLE
    )
    
    # Collected information during conversation (persisted across messages)
    gathered_evidence = models.JSONField(default=dict, blank=True)
    
    # User preferences
    last_detected_location = models.CharField(max_length=255, blank=True, null=True)
    language_preference = models.CharField(max_length=10, blank=True, null=True)
    
    # Legacy fields (maintained for backward compatibility)
    awaiting_location = models.BooleanField(default=False)
    pending_report_data = models.JSONField(blank=True, null=True)
    cancelled_until = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        # Unique per platform - same user can have sessions on multiple platforms
        unique_together = ['chat_id', 'platform']
        indexes = [
            models.Index(fields=['chat_id', 'platform']),
        ]
        
    def __str__(self):
        return f"Session {self.chat_id} ({self.platform}) - {self.username or 'Anonymous'}"
    
    # === Conversation State Management ===
    
    def transition_to(self, new_state: str, evidence_update: dict = None):
        """Transition to a new conversation state with optional evidence update."""
        self.conversation_state = new_state
        if evidence_update:
            self.gathered_evidence = {**self.gathered_evidence, **evidence_update}
        self.save()
    
    def reset_conversation(self):
        """Reset to idle state, clearing all gathered evidence."""
        self.conversation_state = self.State.IDLE
        self.gathered_evidence = {}
        self.awaiting_location = False
        self.pending_report_data = None
        self.save()
    
    def is_in_conversation(self) -> bool:
        """Check if user is in an active conversation flow."""
        return self.conversation_state not in [self.State.IDLE]
    
    def get_gathered_location(self) -> str:
        """Get location from gathered evidence or last known location."""
        return (
            self.gathered_evidence.get('location') or 
            self.last_detected_location or 
            'Unknown'
        )
    
    # === Message History ===
    
    def get_recent_messages(self, limit=10):
        return list(self.messages.order_by('-created_at')[:limit])[::-1]
    
    def get_conversation_context(self, limit=10):
        """Get conversation context formatted for LLM."""
        messages = self.get_recent_messages(limit)
        context = []
        for msg in messages:
            role = "User" if msg.role == 'user' else "Assistant"
            context.append(f"{role}: {msg.content[:500]}")
        return context
    
    def get_messages_for_llm(self, limit=15):
        """Get messages in OpenAI-compatible format for LLM with timestamps."""
        messages = self.get_recent_messages(limit)
        llm_messages = []
        for msg in messages:
            role = 'user' if msg.role == 'user' else 'assistant'
            # Include timestamp for context
            timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M')
            llm_messages.append({
                'role': role,
                'content': f"[{timestamp}] {msg.content}"
            })
        return llm_messages
    
    def get_conversation_history_summary(self) -> str:
        """
        Get a summary of past conversations with this user for AI context.
        Returns last 10 messages with timestamps to show conversation history.
        """
        messages = self.messages.order_by('-created_at')[:10]
        if not messages:
            return "No previous conversation history with this user."
        
        history_lines = []
        history_lines.append(f"=== CONVERSATION HISTORY (Last {len(messages)} messages) ===")
        history_lines.append(f"User: {self.username or 'Anonymous'}")
        history_lines.append(f"Platform: {self.platform}")
        if self.last_detected_location:
            history_lines.append(f"Known Location: {self.last_detected_location}")
        if self.language_preference:
            history_lines.append(f"Language: {self.language_preference}")
        history_lines.append("")
        
        # Reverse to show oldest first
        for msg in reversed(list(messages)):
            role = "USER" if msg.role == 'user' else "IMARA"
            timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M')
            content_preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            history_lines.append(f"[{timestamp}] {role}: {content_preview}")
        
        history_lines.append("=== END HISTORY ===")
        return "\n".join(history_lines)
    
    # === Legacy helpers (backward compatibility) ===
    
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
        self.conversation_state = self.State.IDLE
        self.gathered_evidence = {}
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
