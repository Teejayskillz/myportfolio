# your_project_name/sitemap.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from blog.models import Post

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'weekly'

    def items(self):
        return [
            'pages:home',
            'pages:about',
            'contact:contact_page',
            'pricing:pricing_page',
            'projects:project_list' # <--- CHANGE THIS LINE from 'all_projects' to 'project_list'
        ]

    def location(self, item):
        return reverse(item)

class BlogPostSitemap(Sitemap):
    priority = 0.6
    changefreq = 'daily'

    def items(self):
        return Post.objects.filter(status='published')

    def lastmod(self, obj):
        return obj.updated