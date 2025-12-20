from django.contrib import admin
from .models import Contact , Job , Application , BusinessService,BusinessBooking ,BusinessBundle,BusinessAddon, PrivateMainCategory,PrivateService,PrivateBooking,AvailableZipCode,NotAvailableZipRequest,CallRequest,EmailRequest,PrivateAddon,    ServiceQuestionRule, AddonRule, ScheduleRule ,DateSurcharge
from jsoneditor.forms import JSONEditor
from django.utils.html import format_html
from django.utils.safestring import mark_safe


# # Register your models here.
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "phone",
        "inquiry_type",
        "preferred_method",
        "created_at",
    )

    search_fields = (
        "first_name",
        "last_name",
        "email",
        "phone",
    )

    ordering = ("-created_at",)

    # كل الحقول Read Only
    readonly_fields = [f.name for f in Contact._meta.fields]

    # 🔹 دمج الاسم الأول + الأخير
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = "Name"

    # ❌ منع أي تعديل
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# admin.site.register(Service)
admin.site.register(Job)
admin.site.register(BusinessService)


@admin.register(BusinessBooking)
class BusinessBookingAdmin(admin.ModelAdmin):
    change_form_template = "admin/home/businessbooking/change_form.html"

    list_display = (
        "id",
        "company_name",
        "email",
        "phone",
        "path_type",
        "created_at",
    )

    search_fields = ("company_name", "email", "phone")
    ordering = ("-created_at",)

    # =========================
    # PRETTY JSON (FINAL)
    # =========================
    def pretty_json_colored(self, data):
        if not data:
            return format_html("<span style='color:#6c757d;'>—</span>")

        html = '<div style="display:flex;flex-wrap:wrap;gap:6px;">'

        # 🟦 LIST (services / addons)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    label = item.get("title", "—")
                    icon = "🧩"
                else:
                    label = item
                    icon = "🔹"

                html += f"""
                <span style="
                    background:#e7f1ff;
                    color:#0d6efd;
                    padding:6px 12px;
                    border-radius:20px;
                    font-weight:600;
                    font-size:13px;
                ">
                    {icon} {label}
                </span>
                """

        # 🟩 DICT (frequency)
        elif isinstance(data, dict):
            for key, value in data.items():
                html += f"""
                <span style="
                    background:#e9f7ef;
                    color:#198754;
                    padding:6px 12px;
                    border-radius:20px;
                    font-weight:600;
                    font-size:13px;
                ">
                    {key}: {value}
                </span>
                """

        html += "</div>"
        return mark_safe(html)

    # =========================
    # PRETTY FIELDS
    # =========================
    def services_needed_pretty(self, obj):
        return self.pretty_json_colored(obj.services_needed)
    services_needed_pretty.short_description = "Services Needed"

    def addons_pretty(self, obj):
        return self.pretty_json_colored(obj.addons)
    addons_pretty.short_description = "Add-ons"

    def frequency_pretty(self, obj):
        return self.pretty_json_colored(obj.frequency)
    frequency_pretty.short_description = "Frequency"

    # =========================
    # FIELDSETS
    # =========================
    fieldsets = (
        ("Service", {
            "fields": ("selected_service", "selected_bundle", "path_type"),
        }),
        ("Company Info", {
            "fields": (
                "company_name",
                "contact_person",
                "role",
                "office_address",
                "email",
                "phone",
            ),
        }),
        ("Office Setup", {
            "fields": (
                "office_size",
                "num_employees",
                "floors",
                "restrooms",
                "kitchen_cleaning",
            ),
        }),
        ("Services & Add-ons", {
            "fields": (
                "services_needed_pretty",
                "addons_pretty",
                "frequency_pretty",
            ),
        }),
        ("System", {
            "fields": ("created_at",),
        }),
    )

    # =========================
    # READONLY LOGIC
    # =========================
    def get_readonly_fields(self, request, obj=None):
        model_fields = [f.name for f in self.model._meta.fields]

        pretty_fields = (
            "services_needed_pretty",
            "addons_pretty",
            "frequency_pretty",
        )

        hidden_json_fields = (
            "services_needed",
            "addons",
            "frequency",
        )

        if request.GET.get("edit") != "1":
            return tuple(
                f for f in model_fields if f not in hidden_json_fields
            ) + pretty_fields

        return (
            "created_at",
            *pretty_fields,
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False
  
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

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import PrivateBooking



@admin.register(PrivateBooking)
class PrivateBookingAdmin(admin.ModelAdmin):
    change_form_template = "admin/home/privatebooking/change_form.html"

    # =====================================================
    # LIST VIEW
    # =====================================================
    list_display = (
        "id",
        "zip_badge",
        "booking_method_badge",
        "schedule_mode_badge",
        "created_at",
    )

    list_filter = ("booking_method", "zip_is_available", "schedule_mode")
    search_fields = ("id", "zip_code")
    ordering = ("-created_at",)

    # =====================================================
    # BADGES
    # =====================================================
    def zip_badge(self, obj):
        if obj.zip_is_available:
            return format_html(
                '<span style="background:#198754;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">✔ Available</span>'
            )
        return format_html(
            '<span style="background:#dc3545;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">✘ Not Available</span>'
        )
    zip_badge.short_description = "ZIP"

    def booking_method_badge(self, obj):
        colors = {
            "online": "#0d6efd",
            "call": "#6f42c1",
            "whatsapp": "#25d366",
        }
        color = colors.get(obj.booking_method, "#6c757d")
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:12px;font-size:12px;">{}</span>',
            color,
            obj.booking_method.upper()
        )
    booking_method_badge.short_description = "Method"

    def schedule_mode_badge(self, obj):
        if obj.schedule_mode == "same":
            return format_html(
                '<span style="background:#20c997;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">SAME</span>'
            )
        return format_html(
            '<span style="background:#fd7e14;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">PER SERVICE</span>'
        )
    schedule_mode_badge.short_description = "Schedule"

    # =====================================================
    # PRETTY JSON CORE 🔥
    # =====================================================
    def pretty_json_colored(self, data):
        if not data:
            return mark_safe("<span style='color:#6c757d;'>—</span>")

        html = """
        <div style="
            background:#f8f9fa;
            border:1px solid #e0e0e0;
            border-radius:10px;
            padding:12px;
            font-size:13px;
        ">
        """

        # ---------- LIST ----------
        if isinstance(data, list):
            for item in data:
                html += f"""
                <div style="
                    background:#e7f1ff;
                    color:#0d6efd;
                    padding:6px 10px;
                    border-radius:8px;
                    margin-bottom:6px;
                    font-weight:600;
                ">
                    🔹 {item}
                </div>
                """

        # ---------- DICT ----------
        elif isinstance(data, dict):
            for key, value in data.items():

                # ===== SERVICE / ADDON GROUP =====
                html += f"""
                <div style="
                    background:#ffffff;
                    border:1px solid #dee2e6;
                    border-radius:8px;
                    padding:10px;
                    margin-bottom:10px;
                ">
                    <div style="
                        font-weight:700;
                        color:#6f42c1;
                        margin-bottom:6px;
                    ">
                        🧹 {key}
                    </div>
                """

                # ===== ADD-ON OBJECT =====
                if isinstance(value, dict) and "title" in value:
                    html += f"""
                    <div style="
                        background:#f1f3f5;
                        border-radius:8px;
                        padding:8px;
                        margin-left:10px;
                    ">
                        <div style="font-weight:700;">🧺 {value.get('title')}</div>
                        <div style="margin-left:10px;">
                            Quantity: <b>{value.get('quantity', '-')}</b><br>
                            Unit price: <b>${value.get('unit_price', 0)}</b><br>
                            Total: <b style="color:#198754;">${value.get('price', 0)}</b>
                        </div>
                    </div>
                    """

                # ===== NORMAL KEY/VALUE =====
                elif isinstance(value, dict):
                    for k, v in value.items():
                        html += f"""
                        <div style="margin-left:12px;margin-bottom:4px;">
                            <span style="color:#198754;font-weight:600;">{k}</span> :
                            <span style="color:#212529;">{v}</span>
                        </div>
                        """

                html += "</div>"

        html += "</div>"
        return mark_safe(html)

    # =====================================================
    # PRETTY FIELDS
    # =====================================================
    def selected_services_pretty(self, obj):
        return self.pretty_json_colored(obj.selected_services)
    selected_services_pretty.short_description = "Selected Services"

    def service_answers_pretty(self, obj):
        return self.pretty_json_colored(obj.service_answers)
    service_answers_pretty.short_description = "Service Answers"

    def addons_selected_pretty(self, obj):
        return self.pretty_json_colored(obj.addons_selected)
    addons_selected_pretty.short_description = "Add-ons Selected"

    def service_schedules_pretty(self, obj):
        return self.pretty_json_colored(obj.service_schedules)
    service_schedules_pretty.short_description = "Service Schedules"

    def special_timing_requests_pretty(self, obj):
        return self.pretty_json_colored(obj.special_timing_requests)
    special_timing_requests_pretty.short_description = "Special Timing Requests"

    # =====================================================
    # FIELDSETS
    # =====================================================
    base_fieldsets = (
        ("ZIP Code Check", {"fields": ("zip_code", "zip_is_available")}),
        ("Booking Method", {"fields": ("booking_method", "schedule_mode")}),

        ("Category & Services", {
            "fields": (
                "main_category",
                "selected_services_pretty",
                "service_answers_pretty",
            )
        }),

        ("Add-ons", {
            "fields": ("addons_selected_pretty",)
        }),

        ("Same Schedule (applies to all services)", {
            "fields": (
                "appointment_date",
                "appointment_time_window",
                "frequency_type",
                "day_work_best",
                "special_timing_requests_pretty",
                "End_Date",
            ),
        }),

        ("Per-Service Scheduling", {
            "fields": ("service_schedules_pretty",)
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

    # =====================================================
    # DYNAMIC FIELDSETS
    # =====================================================
    def get_fieldsets(self, request, obj=None):
        if not obj:
            return self.base_fieldsets

        final_sets = []
        for title, config in self.base_fieldsets:
            if obj.schedule_mode == "per_service" and title.startswith("Same Schedule"):
                continue
            if obj.schedule_mode == "same" and title.startswith("Per-Service"):
                continue
            final_sets.append((title, config))
        return final_sets

    # =====================================================
    # READ ONLY (VIEW MODE)
    # =====================================================
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields] + [
            "selected_services_pretty",
            "service_answers_pretty",
            "addons_selected_pretty",
            "service_schedules_pretty",
            "special_timing_requests_pretty",
        ]
@admin.register(CallRequest)
class CallRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "preferred_time", "created_at")
    search_fields = ("full_name", "phone", "email")
    ordering = ("-created_at",)

    readonly_fields = [f.name for f in CallRequest._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PrivateAddon)
class PrivateAddonAdmin(admin.ModelAdmin):
    list_display = ("title", "service", "slug", "price", "price_per_unit")
    search_fields = ("title", "slug")
    inlines = [AddonRuleInline]


@admin.register(DateSurcharge)
class DateSurchargeAdmin(admin.ModelAdmin):
    list_display = ("rule_type", "weekday", "date", "amount", "surcharge_type")
    list_filter = ("rule_type", "weekday", "date")
