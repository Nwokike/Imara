from django.contrib import admin
from .models import AuthorityContact


@admin.register(AuthorityContact)
class AuthorityContactAdmin(admin.ModelAdmin):
    list_display = ['agency_name', 'email', 'jurisdiction_level', 'jurisdiction_name', 'priority', 'is_active']
    list_filter = ['jurisdiction_level', 'is_active', 'priority']
    search_fields = ['agency_name', 'email', 'jurisdiction_name', 'tags']
    list_editable = ['priority', 'is_active']
    ordering = ['-priority', 'jurisdiction_name']
    
    fieldsets = (
        ('Agency Information', {
            'fields': ('agency_name', 'email', 'phone')
        }),
        ('Jurisdiction', {
            'fields': ('jurisdiction_level', 'jurisdiction_name')
        }),
        ('Classification', {
            'fields': ('tags', 'priority', 'is_active')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
