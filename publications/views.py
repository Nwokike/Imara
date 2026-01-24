from django.views.generic import ListView, DetailView
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator
from .models import Article, Comment
from utils.ratelimit import form_ratelimit


class ArticleListView(ListView):
    model = Article
    template_name = 'publications/article_list.html'
    context_object_name = 'articles'
    paginate_by = 10

    def get_queryset(self):
        # Only show published articles
        return Article.objects.filter(status='published', published_at__lte=timezone.now()).order_by('-published_at')


class ArticleDetailView(DetailView):
    model = Article
    template_name = 'publications/article_detail.html'
    context_object_name = 'article'

    def get_queryset(self):
        # Only show published articles
        return Article.objects.filter(status='published', published_at__lte=timezone.now())
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get approved comments
        context['comments'] = self.object.comments.filter(is_approved=True)
        # Get prev/next
        context['previous_article'] = self.object.get_previous_article()
        context['next_article'] = self.object.get_next_article()
        return context


class SubmitCommentView(View):
    """Handle comment submission with Turnstile validation."""
    
    @method_decorator(form_ratelimit)
    def post(self, request, slug):
        from utils.captcha import validate_turnstile
        
        article = get_object_or_404(Article, slug=slug, status='published')
        
        # Validate Turnstile
        token = request.POST.get('cf-turnstile-response')
        is_valid, error_msg = validate_turnstile(token, request.META.get('REMOTE_ADDR'))
        
        if not is_valid:
            messages.error(request, error_msg)
            return redirect('publications:article_detail', slug=slug)
        
        # Get form data
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        content = request.POST.get('content', '').strip()
        
        # Validate
        if not name or not content:
            messages.error(request, "Name and comment are required.")
            return redirect('publications:article_detail', slug=slug)
        
        if len(content) > 1000:
            messages.error(request, "Comment is too long (max 1000 characters).")
            return redirect('publications:article_detail', slug=slug)
        
        # Create comment (pre-moderation by default)
        Comment.objects.create(
            article=article,
            name=name,
            email=email,
            content=content,
            ip_address=request.META.get('REMOTE_ADDR'),
            is_approved=False
        )
        
        messages.success(request, "Thank you! Your comment has been received and is awaiting moderation.")
        return redirect('publications:article_detail', slug=slug)

