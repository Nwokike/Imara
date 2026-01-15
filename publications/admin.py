from django.contrib import admin
from .models import Category, Article, Tag, Comment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'category', 'author_organization', 'published_at', 'author')
    list_filter = ('status', 'category', 'author_organization', 'tags')
    search_fields = ('title',)
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('tags',)
    autocomplete_fields = ('author', 'author_organization')
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'intro_image', 'content')
        }),
        ('Classification', {
            'fields': ('category', 'tags', 'author', 'author_organization')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Publishing', {
            'fields': ('status', 'published_at', 'created_at', 'updated_at')
        }),
    )


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('name', 'article', 'is_approved', 'is_spam', 'created_at')
    list_filter = ('is_approved', 'is_spam', 'created_at')
    search_fields = ('name', 'email', 'content')
    list_editable = ('is_approved', 'is_spam')
    readonly_fields = ('ip_address', 'created_at')
    actions = ['approve_comments', 'mark_as_spam']
    
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True, is_spam=False)
        self.message_user(request, f"{queryset.count()} comments approved.")
    approve_comments.short_description = "Approve selected comments"
    
    def mark_as_spam(self, request, queryset):
        queryset.update(is_spam=True, is_approved=False)
        self.message_user(request, f"{queryset.count()} comments marked as spam.")
    mark_as_spam.short_description = "Mark selected as spam"


