from django.conf import settings
from django.contrib.sitemaps.views import sitemap as django_sitemap
from django.http import HttpResponse

from .sitemaps import SITEMAPS


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /accounts/",
        "Disallow: /booking/checkout/",
        "Disallow: /private/cart/",
        "Disallow: /private/api/",
        "Disallow: /stripe/",
        "",
        f"Sitemap: {settings.PUBLIC_SITE_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    return django_sitemap(request, sitemaps=SITEMAPS)
