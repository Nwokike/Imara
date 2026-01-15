from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import PartnerOrganization, PartnerUser, PartnerApplication, PartnerInvite


@admin.register(PartnerOrganization)
class PartnerOrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'org_type', 'jurisdiction', 'seats_display', 'is_active', 'is_verified', 'created_at']
    list_filter = ['org_type', 'jurisdiction', 'is_active', 'is_verified']
    search_fields = ['name', 'jurisdiction', 'contact_email']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']
    
    def seats_display(self, obj):
        return f"{obj.seats_used}/{obj.max_seats}"
    seats_display.short_description = 'Seats'


@admin.register(PartnerUser)
class PartnerUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'organization']
    search_fields = ['user__username', 'organization__name']
    raw_id_fields = ['user']


@admin.register(PartnerApplication)
class PartnerApplicationAdmin(admin.ModelAdmin):
    list_display = ['org_name', 'org_type', 'jurisdiction', 'status', 'submitted_at']
    list_filter = ['status', 'org_type', 'jurisdiction']
    search_fields = ['org_name', 'contact_name', 'contact_email']
    readonly_fields = ['submitted_at']
    
    fieldsets = (
        ('Organization Details', {
            'fields': ('org_name', 'org_type', 'jurisdiction', 'website', 'description')
        }),
        ('Contact Information', {
            'fields': ('contact_name', 'contact_email', 'contact_phone')
        }),
        ('Review', {
            'fields': ('status', 'admin_notes', 'reviewed_at', 'reviewed_by')
        }),
        ('Metadata', {
            'fields': ('submitted_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PartnerInvite)
class PartnerInviteAdmin(admin.ModelAdmin):
    list_display = ['email', 'organization', 'role', 'invite_status', 'created_at', 'expires_at']
    list_filter = ['organization', 'role', 'is_accepted']
    search_fields = ['email', 'organization__name']
    readonly_fields = ['token', 'created_at', 'accepted_at', 'invite_link']
    raw_id_fields = ['invited_by']
    
    fieldsets = (
        ('Invite Details', {
            'fields': ('email', 'organization', 'role')
        }),
        ('Status', {
            'fields': ('is_accepted', 'accepted_at', 'invite_link')
        }),
        ('Metadata', {
            'fields': ('token', 'invited_by', 'created_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    def invite_status(self, obj):
        if obj.is_accepted:
            return '✅ Accepted'
        elif obj.is_expired:
            return '⏰ Expired'
        return '⏳ Pending'
    invite_status.short_description = 'Status'
    
    def invite_link(self, obj):
        from django.utils.html import format_html
        if obj.is_valid:
            url = f"/partners/invite/{obj.token}/"
            return format_html('<a href="{}" target="_blank">{}</a>', url, url)
        return 'N/A'
    invite_link.short_description = 'Invite Link'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New invite
            obj.invited_by = request.user
        super().save_model(request, obj, form, change)

