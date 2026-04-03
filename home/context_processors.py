from .models import PrivateService


def header_private_services(request):
    services = list(
        PrivateService.objects.only("title", "slug", "display_order").order_by("display_order", "title", "id")[:12]
    )
    return {"header_private_services": services}
