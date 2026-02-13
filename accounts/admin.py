from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Customer,
    CustomerPreferences,
    LoyaltyTier,
    Promotion,
    ProviderProfile,
    ProviderRatingSummary,
    Reward,
    Service,
    BookingChecklist,
    DiscountCode,
    UserAccessProfile,
)

# =========================
# SERVICE
# =========================
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("label", "key")


# =========================
# CUSTOMER
# =========================
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone")
    search_fields = ("first_name", "last_name", "email", "phone")
    list_filter = ("preferred_language", "gender")


# =========================
# CUSTOMER PREFERENCES
# =========================
@admin.register(CustomerPreferences)
class CustomerPreferencesAdmin(admin.ModelAdmin):
    list_display = ("customer", "frequency", "updated_at")
    readonly_fields = ("updated_at",)


# =========================
# LOYALTY / REWARDS
# =========================
@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = ("name", "min_points", "max_points", "is_active", "order")
    list_editable = ("order", "is_active")
    ordering = ("order",)


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("title", "points_required", "is_active")
    list_editable = ("points_required", "is_active")


# =========================
# PROMOTIONS
# =========================
@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("title", "points_multiplier", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


# =========================
# DISCOUNT CODES
# =========================
@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent", "user", "is_used", "expires_at", "created_at")
    search_fields = ("code", "user__username", "user__email")
    list_filter = ("is_used", "percent")


# =========================
# PROVIDER PROFILE
# =========================
@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "area", "city", "region", "is_active", "has_photo")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__email", "area", "city", "region")
    readonly_fields = ("preview_photo",)

    def has_photo(self, obj):
        return bool(obj.photo)

    has_photo.boolean = True
    has_photo.short_description = "Photo"

    def preview_photo(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height:150px;border-radius:10px;" />',
                obj.photo.url
            )
        return "No photo"

    preview_photo.short_description = "Photo Preview"


# =========================
# PROVIDER RATING SUMMARY
# =========================
@admin.register(ProviderRatingSummary)
class ProviderRatingSummaryAdmin(admin.ModelAdmin):
    list_display = ("provider", "avg_rating", "total_reviews", "updated_at")
    ordering = ("-avg_rating",)
    readonly_fields = ("updated_at",)
    search_fields = ("provider__username", "provider__email")


@admin.register(UserAccessProfile)
class UserAccessProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "site", "role", "created_at")
    list_filter = ("site", "role")
    search_fields = ("user__username", "user__email")
