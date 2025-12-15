from django.contrib import admin
from .models import Contact , Job , Application , BusinessService,BusinessBooking ,BusinessBundle,BusinessAddon, PrivateMainCategory,PrivateService,PrivateBooking,AvailableZipCode,NotAvailableZipRequest,CallRequest,EmailRequest,PrivateAddon,    ServiceQuestionRule, AddonRule, ScheduleRule ,DateSurcharge
from jsoneditor.forms import JSONEditor



# # Register your models here.
admin.site.register(Contact)
# admin.site.register(Service)
admin.site.register(Job)
admin.site.register(BusinessService)
admin.site.register(BusinessBooking)
admin.site.register(BusinessAddon)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "phone", "job", "application_type", "created_at"]
    list_filter = ["job", "created_at"]

    def application_type(self, obj):
        if obj.job:
            return "Job Application"
        return "Open Application"

    application_type.short_description = "Type"


@admin.register(BusinessBundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("title", "discount")  
    prepopulated_fields = {"slug": ("title",)}





# ================================
# 1. MAIN CATEGORY
# ================================
@admin.register(PrivateMainCategory)
class PrivateMainCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title")
    search_fields = ("title",)


# ================================
# 2. PRIVATE SERVICE
# ================================


class PrivateAddonInline(admin.StackedInline):
    model = PrivateAddon
    extra = 1
    fields = ("title", "slug", "icon", "price", "price_per_unit", "form_html")
class ServiceQuestionRuleInline(admin.TabularInline):
    model = ServiceQuestionRule
    extra = 1


@admin.register(ScheduleRule)
class ScheduleRuleAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "price_change")
    

@admin.register(PrivateService)
class PrivateServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "slug", "price")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        ("Basic Info", {
            "fields": ("category", "title", "slug", "price", "description", "recommended", "image")
        }),
        ("Questions (JSON)", {
            "fields": ("questions",),
            "classes": ("collapse",)
        }),
    )
    inlines = [PrivateAddonInline, ServiceQuestionRuleInline]

# ================================
# 3. PRIVATE BOOKING
# ================================
@admin.register(PrivateBooking)
class PrivateBookingAdmin(admin.ModelAdmin):
    list_display = ("id", "zip_code", "zip_is_available", "booking_method", "schedule_mode", "created_at")
    list_filter = ("booking_method", "zip_is_available", "schedule_mode")
    search_fields = ("id", "zip_code")

    readonly_fields = ("created_at",)

    # الحقول الكاملة (سنختار منها ديناميكياً لاحقاً)
    base_fieldsets = (
        ("ZIP Code Check", {
            "fields": ("zip_code", "zip_is_available")
        }),

        ("Booking Method", {
            "fields": ("booking_method", "schedule_mode")
        }),

        ("Category & Services", {
            "fields": ("main_category", "selected_services", "service_answers")
        }),

        ("Add-ons", {
            "fields": ("addons_selected",)
        }),

        # 🟦 SAME MODE fields
        ("Same Schedule (applies to all services)", {
            "fields": (
                "appointment_date",
                "appointment_time_window",
                "frequency_type",
                "day_work_best",
                "special_timing_requests",
                "End_Date",
            ),
        }),

        # 🟣 PER SERVICE MODE fields
        ("Per-Service Scheduling", {
            "fields": ("service_schedules",)
        }),

        ("Checkout", {
            "fields": (
                "subtotal", "rot_discount", "total_price",
                "address", "area", "duration_hours",
            ),
            "classes": ("collapse",)
        }),

        ("Payment", {
            "fields": (
                "payment_method",
                "card_number", "card_expiry", "card_cvv", "card_name",
                "accepted_terms",
            ),
            "classes": ("collapse",)
        }),

        ("System Fields", {
            "fields": ("created_at",),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """
        إظهار/إخفاء البلوكات بناءً على قيمة schedule_mode
        """
        if obj is None:
            # أثناء الإضافة الجديدة، نظهر كل شيء
            return self.base_fieldsets

        mode = getattr(obj, "schedule_mode", None)

        # ننسخ الـ fieldsets كي لا نعدل على الأصل
        final_sets = []

        for title, config in self.base_fieldsets:
            # إخفاء بلوك SAME إذا الوضع per_service
            if mode == "per_service" and title == "Same Schedule (applies to all services)":
                continue

            # إخفاء بلوك PER-SERVICE إذا الوضع same
            if mode == "same" and title == "Per-Service Scheduling":
                continue

            final_sets.append((title, config))

        return final_sets

@admin.register(CallRequest)
class CallRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "preferred_time", "created_at")
    search_fields = ("full_name", "phone", "email")



class AddonRuleInline(admin.TabularInline):
    model = AddonRule
    extra = 1



@admin.register(EmailRequest)
class EmailRequestAdmin(admin.ModelAdmin):
    list_display = ("email_from", "subject", "created_at")
    search_fields = ("email_from", "subject", "message")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "attachment")

    fieldsets = (
        ("Email Details", {
            "fields": ("email_from", "subject", "message", "attachment")
        }),
        ("System Info", {
            "fields": ("created_at",)
        }),
    )


@admin.register(PrivateAddon)
class PrivateAddonAdmin(admin.ModelAdmin):
    list_display = ("title", "service", "slug", "price", "price_per_unit")
    search_fields = ("title", "slug")
    inlines = [AddonRuleInline]


@admin.register(DateSurcharge)
class DateSurchargeAdmin(admin.ModelAdmin):
    list_display = ("rule_type", "weekday", "date", "amount", "surcharge_type")
    list_filter = ("rule_type", "weekday", "date")
