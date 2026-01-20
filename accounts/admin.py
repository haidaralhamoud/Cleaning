from django.contrib import admin
from .models import Customer, CustomerPreferences, LoyaltyTier, Promotion, Reward, Service , BookingChecklist

from home.models import PrivateBooking, BusinessBooking
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



@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "min_points",
        "max_points",
        "is_active",
        "order",
    )

    list_editable = (
        "order",
        "is_active",
    )

    search_fields = ("name",)
    ordering = ("order",)



@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("title", "points_required", "is_active")
    list_editable = ("points_required", "is_active")




@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "points_multiplier",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("title",)    





@admin.register(CustomerPreferences)
class CustomerPreferencesAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "frequency",
        "updated_at",
    )

    search_fields = (
        "customer__first_name",
        "customer__last_name",
        "customer__email",
    )

    readonly_fields = ("updated_at",)

    fieldsets = (
        ("Customer", {
            "fields": ("customer",)
        }),
        ("Cleaning Preferences", {
            "fields": ("cleaning_types", "priorities")
        }),
        ("Products", {
            "fields": ("preferred_products", "excluded_products")
        }),
        ("Scheduling", {
            "fields": ("frequency",)
        }),
        ("Lifestyle & Add-ons", {
            "fields": ("lifestyle_addons",)
        }),
        ("Assembly & Renovations", {
            "fields": ("assembly_services",)
        }),
        ("System", {
            "fields": ("updated_at",)
        }),
    )    