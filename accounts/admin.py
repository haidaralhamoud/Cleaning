from django.contrib import admin
from .models import Customer, Service

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["label", "key"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "email", "phone"]
    search_fields = ["first_name", "last_name", "email"]
    list_filter = ["preferred_language"]

    readonly_fields = ("formatted_addons",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("first_name", "last_name", "email", "phone",
                       "personal_identity_number")
        }),
        ("Address", {
            "fields": ("country", "city", "postal_code",
                       "house_num", "full_address")
        }),
        ("Services", {
            "fields": ("desired_services", "formatted_addons")
        }),
        ("Other", {
            "fields": ("optional_note", "preferred_language",
                       "profile_photo", "password", "accepted_terms")
        }),
    )

    def formatted_addons(self, obj):
        if not obj.custom_addons:
            return "— No Add-ons —"
        return ", ".join(obj.custom_addons)

    formatted_addons.short_description = "Custom Add-ons"
