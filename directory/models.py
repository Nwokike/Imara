from django.db import models
from django.contrib.postgres.fields import ArrayField


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
    jurisdiction_name = models.CharField(max_length=255)
    
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Tags like 'Cybercrime', 'Domestic Violence', 'Women Safety'"
    )
    
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=1, help_text="Higher priority contacts are preferred (1-10)")
    
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'jurisdiction_name']
        verbose_name = 'Authority Contact'
        verbose_name_plural = 'Authority Contacts'
        
    def __str__(self):
        return f"{self.agency_name} - {self.jurisdiction_name}"
    
    @classmethod
    def find_by_location(cls, location):
        if not location:
            return cls.objects.filter(is_active=True).order_by('-priority').first()
        
        location_lower = location.lower()
        contacts = cls.objects.filter(
            is_active=True,
            jurisdiction_name__icontains=location_lower
        ).order_by('-priority')
        
        if contacts.exists():
            return contacts.first()
        
        return cls.objects.filter(is_active=True).order_by('-priority').first()
