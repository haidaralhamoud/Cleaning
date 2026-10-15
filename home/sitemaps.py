from django.contrib.sitemaps import Sitemap
from django.conf import settings
from django.urls import reverse
from types import SimpleNamespace
from urllib.parse import urlsplit

from .models import BusinessService, PrivateService


class PublicHostSitemap(Sitemap):
    """Always emit the configured canonical host, independent of request/Site rows."""

    def get_urls(self, page=1, site=None, protocol=None):
        canonical = urlsplit(settings.PUBLIC_SITE_URL)
        public_site = SimpleNamespace(domain=canonical.netloc)
        return super().get_urls(
            page=page,
            site=public_site,
            protocol=canonical.scheme or "https",
        )


class StaticPagesSitemap(PublicHostSitemap):
    protocol = "https"
    changefreq = "weekly"
    view_names = (
        "home:home", "home:about", "home:contact", "home:faq",
        "home:all_services_private", "home:business_all_services",
        "home:airbnb_management", "home:Privacy_Policy",
        "home:Cookies_Policy", "home:T_C", "home:Accessibility_Statement",
    )

    def items(self):
        return self.view_names

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == "home:home" else 0.7


class PrivateServiceSitemap(PublicHostSitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return PrivateService.objects.order_by("display_order", "title")

    def location(self, item):
        return reverse("accounts:service_detail", args=[item.slug])


class BusinessServiceSitemap(PublicHostSitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return BusinessService.objects.order_by("title")

    def location(self, item):
        return reverse("home:business_service_detail", args=[item.pk])


SITEMAPS = {
    "pages": StaticPagesSitemap,
    "private-services": PrivateServiceSitemap,
    "business-services": BusinessServiceSitemap,
}
