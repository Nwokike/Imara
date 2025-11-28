from django.db import models


class DispatchLog(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ]
    
    incident = models.ForeignKey('cases.IncidentReport', on_delete=models.CASCADE, related_name='dispatch_logs')
    authority = models.ForeignKey('directory.AuthorityContact', on_delete=models.SET_NULL, null=True, related_name='dispatch_logs')
    
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=500)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    brevo_message_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Dispatch Log'
        verbose_name_plural = 'Dispatch Logs'
        
    def __str__(self):
        return f"Dispatch to {self.recipient_email} - {self.status}"
