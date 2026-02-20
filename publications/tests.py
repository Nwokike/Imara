from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from unittest import mock
from .models import Article, Category, Tag, Comment


class CategoryTests(TestCase):
    def test_category_slug_auto_generation(self):
        """Test that category slugs are auto-generated"""
        cat = Category.objects.create(name='Safety Tips')
        self.assertEqual(cat.slug, 'safety-tips')


class ArticleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='author', email='author@test.com', password='pass'
        )
        self.category = Category.objects.create(name='News', slug='news')
    
    def test_article_slug_auto_generation(self):
        """Test article slug is auto-generated from title"""
        article = Article.objects.create(
            title='How to Stay Safe Online',
            author=self.user,
            status='published'
        )
        self.assertEqual(article.slug, 'how-to-stay-safe-online')
    
    def test_article_slug_collision_handling(self):
        """Test duplicate slugs get counter suffix"""
        Article.objects.create(
            title='Test Article', author=self.user, slug='test-article'
        )
        article2 = Article.objects.create(
            title='Test Article', author=self.user
        )
        self.assertEqual(article2.slug, 'test-article-1')
    
    def test_meta_title_auto_population(self):
        """Test meta_title defaults to title"""
        article = Article.objects.create(
            title='My Article', author=self.user
        )
        self.assertEqual(article.meta_title, 'My Article')

    def test_render_as_html(self):
        """Test native Editor.js JSON to HTML conversion"""
        content = {
            "blocks": [
                {"type": "header", "data": {"text": "Safe Online", "level": 2}},
                {"type": "paragraph", "data": {"text": "Always use 2FA."}}
            ]
        }
        article = Article.objects.create(
            title='Safety', author=self.user, content=content
        )
        html = article.render_as_html
        self.assertIn('<h2 class=\'font-bold mt-6 mb-2\'>Safe Online</h2>', html)
        self.assertIn('<p class=\'mb-4\'>Always use 2FA.</p>', html)

    def test_seo_metadata(self):
        """Test SEO metadata fields"""
        article = Article.objects.create(
            title='SEO Test', author=self.user,
            meta_description="Expert safety advice for Africans."
        )
        self.assertEqual(article.meta_title, "SEO Test")
        self.assertEqual(article.meta_description, "Expert safety advice for Africans.")

    def test_sitemap_loads(self):
        """Test sitemap.xml loads successfully"""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ArticleViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('author', 'a@b.com', 'pass')
        from django.utils import timezone
        self.article = Article.objects.create(
            title='Published Article',
            slug='published-article',
            author=self.user,
            status='published',
            published_at=timezone.now()
        )
    
    def test_article_list_page_loads(self):
        """Test article list page loads"""
        response = self.client.get(reverse('publications:article_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_article_detail_page_loads(self):
        """Test article detail page loads"""
        response = self.client.get(
            reverse('publications:article_detail', args=[self.article.slug])
        )
        self.assertEqual(response.status_code, 200)
    
    def test_unpublished_article_not_visible(self):
        """Test draft articles are not publicly visible"""
        draft = Article.objects.create(
            title='Draft Article',
            slug='draft-article',
            author=self.user,
            status='draft'
        )
        response = self.client.get(
            reverse('publications:article_detail', args=[draft.slug])
        )
        self.assertEqual(response.status_code, 404)


class CommentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('author', 'a@b.com', 'pass')
        from django.utils import timezone
        self.article = Article.objects.create(
            title='Test', slug='test', author=self.user,
            status='published', published_at=timezone.now()
        )
    
    def test_comment_creation(self):
        """Test comment can be created"""
        comment = Comment.objects.create(
            article=self.article,
            name='Tester',
            content='Great article!'
        )
        self.assertFalse(comment.is_approved)  # Default is False
        self.assertFalse(comment.is_spam)

    @mock.patch('utils.captcha.validate_turnstile', return_value=(True, None))
    def test_submit_comment_creates_unapproved(self, mock_turnstile):
        client = Client()
        response = client.post(
            reverse('publications:submit_comment', args=[self.article.slug]),
            data={
                "name": "Tester",
                "email": "t@example.com",
                "content": "Nice post",
                "cf-turnstile-response": "test",
            }
        )
        self.assertIn(response.status_code, [200, 302])
        c = Comment.objects.get(article=self.article)
        self.assertFalse(c.is_approved)
