from django.shortcuts import render
from .models import ElectricalService


def home(request):
    return render(request, "electricity/landing.html")


def services(request):
    services_qs = ElectricalService.objects.filter(is_active=True).order_by("order", "title")
    return render(request, "electricity/services.html", {"services": services_qs})
