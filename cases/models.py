import uuid
import hashlib
from django.db import models
from django.utils import timezone


class IncidentReport(models.Model):
    SOURCE_CHOICES = [
        ('telegram', 'Telegram Bot'),
        ('web', 'Web Form'),
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
    ]
    
    ACTION_CHOICES = [
        ('pending', 'Pending Analysis'),
        ('advise', 'Advice Given'),
        ('report', 'Reported to Partner'),
    ]
    
    case_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, db_index=True)
    reporter_handle = models.CharField(max_length=255, blank=True, null=True)
    reporter_email = models.EmailField(blank=True, null=True)
    reporter_name = models.CharField(max_length=255, blank=True, null=True)
    contact_preference = models.CharField(max_length=255, blank=True, null=True)
    perpetrator_info = models.TextField(blank=True, null=True)
    
    original_text = models.TextField(blank=True, null=True)
    transcribed_text = models.TextField(blank=True, null=True)
    extracted_text = models.TextField(blank=True, null=True)
    
    ai_analysis = models.JSONField(blank=True, null=True)
    risk_score = models.IntegerField(default=0, db_index=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='pending', db_index=True)
    detected_location = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # Jurisdiction Pool System
    jurisdiction = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        db_index=True,
        help_text="Country/Region for partner visibility (auto-set from detected_location)"
    )
    assigned_partner = models.ForeignKey(
        'partners.PartnerOrganization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cases',
        help_text="Partner organization handling this case"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('OPEN', 'Open'),
            ('CLAIMED', 'Claimed'),
            ('IN_PROGRESS', 'In Progress'),
            ('RESOLVED', 'Resolved'),
            ('CLOSED', 'Closed'),
        ],
        default='OPEN',
        db_index=True
    )
    
    chain_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    
    dispatched_at = models.DateTimeField(blank=True, null=True)
    dispatched_to = models.EmailField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'action']),
            models.Index(fields=['risk_score', 'created_at']),
        ]
        
    def __str__(self):
        return f"Case {self.case_id} - {self.get_source_display()} - {self.get_action_display()}"
    
    def generate_chain_hash(self):
        """
        Generates a forensic-grade SHA-256 hash representing the immutable state
        of this report and all its attached evidence assets.
        """
        # Collect digests of all evidence assets
        asset_digests = "".join(
            self.evidence_assets.order_by('created_at').values_list('sha256_digest', flat=True)
        )
        
        # Salt with unique ID and core metadata
        content = (
            f"{self.case_id}"
            f"{asset_digests}"
            f"{self.original_text or ''}"
            f"{self.transcribed_text or ''}"
            f"{self.extracted_text or ''}"
            f"{self.created_at.isoformat() if self.created_at else ''}"
        )
        
        self.chain_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.chain_hash
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class EvidenceAsset(models.Model):
    TYPE_CHOICES = [
        ('text', 'Text Message'),
        ('image', 'Screenshot/Image'),
        ('audio', 'Voice Note'),
        ('video', 'Video'),
    ]
    
    incident = models.ForeignKey(IncidentReport, on_delete=models.CASCADE, related_name='evidence_assets')
    asset_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    file = models.FileField(upload_to='evidence/%Y/%m/%d/', blank=True, null=True)
    derived_text = models.TextField(blank=True, null=True)
    sha256_digest = models.CharField(max_length=64, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Evidence {self.id} - {self.get_asset_type_display()} for Case {self.incident.case_id}"
    
    def generate_hash(self):
        if self.file:
            file_hash = hashlib.sha256()
            for chunk in self.file.chunks():
                file_hash.update(chunk)
            self.sha256_digest = file_hash.hexdigest()
        elif self.derived_text:
            self.sha256_digest = hashlib.sha256(self.derived_text.encode()).hexdigest()
        return self.sha256_digest
    
    def save(self, *args, **kwargs):
        # Auto-generate hash if not set
        if not self.sha256_digest:
            self.generate_hash()
        super().save(*args, **kwargs)
