from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class AuthorityContact(models.Model):
    JURISDICTION_CHOICES = [
        ('city', 'City'),
        ('state', 'State/Province'),
        ('country', 'Country'),
        ('regional', 'Regional'),
    ]
    
    agency_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, null=True)
    
    jurisdiction_level = models.CharField(max_length=20, choices=JURISDICTION_CHOICES, default='city')
    jurisdiction_name = models.CharField(max_length=255, db_index=True)
    
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags like 'Cybercrime', 'Domestic Violence', 'Women Safety'"
    )
    
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Higher priority contacts are preferred (1-10)"
    )
    
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'jurisdiction_name']
        verbose_name = 'Authority Contact'
        verbose_name_plural = 'Authority Contacts'
        indexes = [
            models.Index(fields=['is_active', 'jurisdiction_name']),
            models.Index(fields=['is_active', '-priority']),
        ]
        
    def __str__(self):
        return f"{self.agency_name} - {self.jurisdiction_name}"
    
    @classmethod
    def find_by_location(cls, location):
        """Find authority contact by location - optimized single query"""
        if not location:
            return cls.objects.filter(is_active=True).order_by('-priority').first()
        
        # Single optimized query - no redundant exists() check
        contact = cls.objects.filter(
            is_active=True,
            jurisdiction_name__icontains=location.lower()
        ).order_by('-priority').first()
        
        # Fallback to highest priority active contact
        return contact or cls.objects.filter(is_active=True).order_by('-priority').first()

