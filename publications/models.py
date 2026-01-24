from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django_editorjs2.fields import EditorJSField


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name_plural = "Categories"


class Tag(models.Model):
    """Tags for article categorization and related posts."""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Article(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )

    # Core Content
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=250)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    author_organization = models.ForeignKey(
        'partners.PartnerOrganization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
        help_text="Partner organization authoring this article (optional)"
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    tags = models.ManyToManyField(Tag, blank=True, related_name='articles')
    intro_image = models.ImageField(upload_to='articles/', blank=True, null=True)
    
    # Rich Content (Editor.js)
    content = EditorJSField(
        blank=True,
        null=True
    )
    
    # Meta / SEO
    meta_title = models.CharField(max_length=160, blank=True, help_text="SEO Title (60 chars ideal)")
    meta_description = models.CharField(max_length=300, blank=True, help_text="SEO Description (160 chars ideal)")
    
    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title
        
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.meta_title:
            self.meta_title = self.title
        super().save(*args, **kwargs)
    
    def get_related_articles(self, limit=3):
        """Get related articles based on shared tags or category."""
        if self.tags.exists():
            return Article.objects.filter(
                tags__in=self.tags.all(),
                status='published'
            ).exclude(id=self.id).distinct()[:limit]
        elif self.category:
            return Article.objects.filter(
                category=self.category,
                status='published'
            ).exclude(id=self.id)[:limit]
        return Article.objects.filter(status='published').exclude(id=self.id)[:limit]
    
    def get_previous_article(self):
        """Get the previous published article by date."""
        return Article.objects.filter(
            status='published',
            published_at__lt=self.published_at
        ).order_by('-published_at').first()
    
    def get_next_article(self):
        """Get the next published article by date."""
        return Article.objects.filter(
            status='published',
            published_at__gt=self.published_at
        ).order_by('published_at').first()


class Comment(models.Model):
    """
    Minimal, privacy-focused comment system.
    Comments are pre-moderated by default (Turnstile reduces spam, staff approves).
    Staff can mark comments as spam or approve/unapprove them via admin.
    """
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    # Anonymous-friendly: only name required
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, help_text="Optional, never displayed")
    content = models.TextField(max_length=1000)
    
    # Moderation
    is_approved = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    
    # Metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
    
    def __str__(self):
        return f"{self.name} on {self.article.title[:30]}"


