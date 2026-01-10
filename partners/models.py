from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class PartnerOrganization(models.Model):
    """
    Represents a partner organization (NGO, Law Enforcement, etc.)
    that can receive and respond to incident cases.
    """
    
    class OrgType(models.TextChoices):
        NGO = 'NGO', 'Non-Governmental Organization'
        LEA = 'LEA', 'Law Enforcement Agency'
        GOV = 'GOV', 'Government Body'
        LEGAL = 'LEGAL', 'Legal Aid Provider'
        HEALTH = 'HEALTH', 'Healthcare Provider'
        OTHER = 'OTHER', 'Other'
    
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    org_type = models.CharField(
        max_length=20, 
        choices=OrgType.choices, 
        default=OrgType.NGO
    )
    
    # Jurisdiction: Country-level for now (can be expanded to regions)
    jurisdiction = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Country or region this partner covers (e.g., 'Kenya', 'Nigeria')"
    )
    
    contact_email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='partner_logos/', blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False, help_text="Admin-verified partner")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Partner Organization'
        verbose_name_plural = 'Partner Organizations'
    
    def __str__(self):
        return f"{self.name} ({self.jurisdiction})"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class PartnerUser(models.Model):
    """
    Links a Django User to a Partner Organization.
    Enables role-based access within the partner portal.
    """
    
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Organization Admin'
        RESPONDER = 'RESPONDER', 'Case Responder'
        VIEWER = 'VIEWER', 'Read-Only Viewer'
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='partner_profile'
    )
    organization = models.ForeignKey(
        PartnerOrganization,
        on_delete=models.CASCADE,
        related_name='members'
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RESPONDER
    )
    
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Partner User'
        verbose_name_plural = 'Partner Users'
    
    def __str__(self):
        return f"{self.user.username} @ {self.organization.name}"
    
    @property
    def jurisdiction(self):
        """Shortcut to access user's jurisdiction via their org."""
        return self.organization.jurisdiction


class PartnerApplication(models.Model):
    """
    Tracks applications from organizations wanting to become partners.
    Admin reviews and approves -> creates PartnerOrganization.
    """
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
    
    org_name = models.CharField(max_length=255)
    org_type = models.CharField(max_length=20, choices=PartnerOrganization.OrgType.choices)
    jurisdiction = models.CharField(max_length=100)
    contact_name = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(help_text="Describe your organization and interest in partnering")
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    admin_notes = models.TextField(blank=True, help_text="Internal notes from review")
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications'
    )
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.org_name} - {self.get_status_display()}"
