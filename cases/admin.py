from django.contrib import admin
from .models import IncidentReport, EvidenceAsset


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ['case_id', 'source', 'action', 'risk_score', 'detected_location', 'created_at']
    list_filter = ['source', 'action', 'risk_score', 'created_at']
    search_fields = ['case_id', 'reporter_handle', 'reporter_email', 'original_text']
    readonly_fields = ['case_id', 'chain_hash', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Case Information', {
            'fields': ('case_id', 'source', 'reporter_handle', 'reporter_email')
        }),
        ('Evidence Content', {
            'fields': ('original_text', 'transcribed_text', 'extracted_text')
        }),
        ('AI Analysis', {
            'fields': ('ai_analysis', 'risk_score', 'action', 'detected_location')
        }),
        ('Chain of Custody', {
            'fields': ('chain_hash',)
        }),
        ('Dispatch Information', {
            'fields': ('dispatched_at', 'dispatched_to')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(EvidenceAsset)
class EvidenceAssetAdmin(admin.ModelAdmin):
    list_display = ['id', 'incident', 'asset_type', 'sha256_digest', 'created_at']
    list_filter = ['asset_type', 'created_at']
    search_fields = ['incident__case_id', 'derived_text']
    readonly_fields = ['sha256_digest', 'created_at']
