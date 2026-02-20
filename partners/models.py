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
    
    # Seat-based team limits
    max_seats = models.PositiveIntegerField(
        default=5,
        help_text="Maximum team members allowed in this organization"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Partner Organization'
        verbose_name_plural = 'Partner Organizations'
    
    def __str__(self):
        return f"{self.name} ({self.jurisdiction})"
    
    @property
    def seats_used(self):
        """Count of active team members."""
        return self.members.filter(is_active=True).count()
    
    @property
    def seats_available(self):
        """Remaining seats available."""
        return max(0, self.max_seats - self.seats_used)
    
    @property
    def is_at_capacity(self):
        """Check if organization has reached seat limit."""
        return self.seats_used >= self.max_seats
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while PartnerOrganization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    
    @classmethod
    def find_by_location(cls, location):
        """Find partner organization by jurisdiction/location - cached for 5 minutes"""
        from django.core.cache import cache
        from .utils import normalize_location
        
        country = normalize_location(location)
        if country == "Unknown":
            return None
        
        cache_key = f'partner_org_{country.lower().replace(" ", "_")}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        
        partner = cls.objects.filter(
            is_active=True,
            is_verified=True,
            jurisdiction__iexact=country
        ).order_by('name').first()
        
        if partner:
            cache.set(cache_key, partner, 300)
        return partner


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


class PartnerInvite(models.Model):
    """
    Secure invitation for partner users.
    Admin sends invite -> User clicks link -> Sets password on first login.
    """
    
    email = models.EmailField()
    organization = models.ForeignKey(
        PartnerOrganization,
        on_delete=models.CASCADE,
        related_name='invites'
    )
    role = models.CharField(
        max_length=20,
        choices=PartnerUser.Role.choices,
        default=PartnerUser.Role.RESPONDER
    )
    
    token = models.CharField(max_length=64, unique=True, editable=False)
    
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invites'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Partner Invite'
        verbose_name_plural = 'Partner Invites'
    
    def __str__(self):
        return f"Invite for {self.email} to {self.organization.name}"
    
    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            from datetime import timedelta
            from django.utils import timezone
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        from django.utils import timezone
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        return not self.is_accepted and not self.is_expired


class CaseNote(models.Model):
    """Human-authored notes for an incident report."""
    case = models.ForeignKey('cases.IncidentReport', on_delete=models.CASCADE, related_name='partner_notes')
    author = models.ForeignKey(PartnerUser, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note by {self.author} on {self.case.case_id}"


class PartnerAuditLog(models.Model):
    """Audit log for critical partner actions."""
    ACTION_CHOICES = [
        ('CLAIM', 'Claimed Case'),
        ('STATUS_CHANGE', 'Changed Status'),
        ('MEMBER_REMOVE', 'Removed Team Member'),
        ('ROLE_CHANGE', 'Updated Member Role'),
    ]
    
    organization = models.ForeignKey(PartnerOrganization, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

