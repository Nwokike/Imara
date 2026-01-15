from django.contrib import admin
from .models import ChatSession, ChatMessage, UserFeedback


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['chat_id', 'username', 'platform', 'last_detected_location', 'created_at']
    list_filter = ['platform', 'awaiting_location']
    search_fields = ['chat_id', 'username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'message_type', 'created_at']
    list_filter = ['role', 'message_type']
    search_fields = ['content']
    readonly_fields = ['created_at']


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display = ['chat_id', 'rating', 'case_id', 'created_at']
    list_filter = ['rating']
    search_fields = ['chat_id', 'case_id']
    readonly_fields = ['created_at']
