from django.contrib import admin
from .models import ElectricalService, ConsultationRequest
from .admin_site import electricity_admin_site


@admin.register(ElectricalService, site=electricity_admin_site)
class ElectricalServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "order")
    list_editable = ("is_active", "order")
    search_fields = ("title",)
    ordering = ("order", "title")


@admin.register(ConsultationRequest, site=electricity_admin_site)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "service", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("full_name", "phone", "email")
    ordering = ("-created_at",)
