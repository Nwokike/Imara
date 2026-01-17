from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from publications.models import Article


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['home', 'report_form', 'partner', 'contact', 'consent', 'policies']

    def location(self, item):
        return reverse(item)


class ArticleSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Article.objects.filter(status='published').order_by('-published_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('publications:article_detail', args=[obj.slug])


sitemaps = {
    'static': StaticViewSitemap,
    'articles': ArticleSitemap,
}
