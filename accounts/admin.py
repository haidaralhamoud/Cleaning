from django.contrib import admin
from .models import Customer, Service

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["label", "key"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "email", "phone"]
    search_fields = ["first_name", "last_name", "email", "phone"]
    list_filter = ["preferred_language", "gender"]

    readonly_fields = ("formatted_addons",)

    fieldsets = (
        ("Basic Information", {
            "fields": (
                "user",
                "first_name", "last_name",
                "email", "phone",
                "personal_identity_number",
                "profile_photo",
                "gender", "pronouns",
                "date_of_birth",
            )
        }),

        ("Contact Preferences", {
            "fields": (
                "country_code",
                "preferred_contact_method",
                "preferred_language",
            )
        }),

        ("Address", {
            "fields": (
                "country", "city",
                "postal_code", "house_num",
                "full_address",
            )
        }),

        ("Address & Locations", {
            "fields": (
                "primary_address",
                "additional_locations",
                "entry_code",
                "parking_notes",
            )
        }),

        ("Emergency Contact", {
            "fields": (
                "emergency_first_name",
                "emergency_last_name",
                "emergency_phone",
                "emergency_relation",
            )
        }),

        ("Services", {
            "fields": (
                "desired_services",
                "formatted_addons",
            )
        }),

        ("Other", {
            "fields": (
                "optional_note",
                "accepted_terms",
            )
        }),
    )

    def formatted_addons(self, obj):
        if not obj.custom_addons:
            return "— No Add-ons —"
        return ", ".join(obj.custom_addons)

    formatted_addons.short_description = "Custom Add-ons"
