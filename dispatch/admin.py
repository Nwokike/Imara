from django.contrib import admin
from .models import DispatchLog


@admin.register(DispatchLog)
class DispatchLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'incident', 'recipient_email', 'status', 'sent_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['recipient_email', 'incident__case_id', 'brevo_message_id']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
