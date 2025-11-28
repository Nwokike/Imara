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
        ('report', 'Reported to Authority'),
    ]
    
    case_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    reporter_handle = models.CharField(max_length=255, blank=True, null=True)
    reporter_email = models.EmailField(blank=True, null=True)
    
    original_text = models.TextField(blank=True, null=True)
    transcribed_text = models.TextField(blank=True, null=True)
    extracted_text = models.TextField(blank=True, null=True)
    
    ai_analysis = models.JSONField(blank=True, null=True)
    risk_score = models.IntegerField(default=0)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='pending')
    detected_location = models.CharField(max_length=255, blank=True, null=True)
    
    chain_hash = models.CharField(max_length=64, blank=True, null=True)
    
    dispatched_at = models.DateTimeField(blank=True, null=True)
    dispatched_to = models.EmailField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Case {self.case_id} - {self.get_source_display()} - {self.get_action_display()}"
    
    def generate_chain_hash(self):
        content = f"{self.case_id}{self.original_text or ''}{self.transcribed_text or ''}{self.extracted_text or ''}{self.created_at.isoformat()}"
        self.chain_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.chain_hash
    
    def save(self, *args, **kwargs):
        if not self.chain_hash and self.pk:
            self.generate_chain_hash()
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
