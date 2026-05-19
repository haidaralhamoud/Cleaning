from django.core.cache import cache

from .models import BusinessMainCategory, PrivateMainCategory


HEADER_SERVICES_CACHE_KEY = "home:header_services:v1"
HEADER_SERVICES_CACHE_TTL = 300


def _build_header_categories():
    private_categories = []
    private_qs = (
        PrivateMainCategory.objects.prefetch_related("services")
        .only("title", "slug", "display_order")
        .order_by("display_order", "title", "id")
    )
    for category in private_qs:
        private_categories.append({
            "title": category.title,
            "slug": category.slug,
            "header_services": [
                {"title": service.title, "slug": service.slug}
                for service in sorted(
                    list(category.services.all()),
                    key=lambda service: (service.display_order, service.title, service.id),
                )
            ],
        })

    business_categories = []
    business_qs = (
        BusinessMainCategory.objects.prefetch_related("services")
        .only("title", "slug")
        .order_by("title")
    )
    for category in business_qs:
        business_categories.append({
            "title": category.title,
            "slug": category.slug,
            "header_services": [
                {"title": service.title, "id": service.id}
                for service in sorted(
                    list(category.services.all()),
                    key=lambda service: (service.title, service.id),
                )
            ],
        })

    return {
        "header_private_categories": private_categories,
        "header_business_categories": business_categories,
    }


def header_private_services(request):
    cached = cache.get(HEADER_SERVICES_CACHE_KEY)
    if cached is None:
        cached = _build_header_categories()
        cache.set(HEADER_SERVICES_CACHE_KEY, cached, HEADER_SERVICES_CACHE_TTL)
    return cached
