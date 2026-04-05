from .models import BusinessMainCategory, PrivateMainCategory


def header_private_services(request):
    private_categories = list(
        PrivateMainCategory.objects.prefetch_related("services")
        .only("title", "slug")
        .order_by("title")
    )
    for category in private_categories:
        category.header_services = sorted(
            list(category.services.all()),
            key=lambda service: (service.display_order, service.title, service.id),
        )

    business_categories = list(
        BusinessMainCategory.objects.prefetch_related("services")
        .only("title", "slug")
        .order_by("title")
    )
    for category in business_categories:
        category.header_services = sorted(
            list(category.services.all()),
            key=lambda service: (service.title, service.id),
        )

    return {
        "header_private_categories": private_categories,
        "header_business_categories": business_categories,
    }
