from django.contrib import admin
from .models import PartnerOrganization, PartnerUser, PartnerApplication


@admin.register(PartnerOrganization)
class PartnerOrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'org_type', 'jurisdiction', 'is_active', 'is_verified', 'created_at']
    list_filter = ['org_type', 'jurisdiction', 'is_active', 'is_verified']
    search_fields = ['name', 'jurisdiction', 'contact_email']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']


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
