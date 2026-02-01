from django import forms
from django.utils import timezone 
from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django import forms
from .models import (
    Contact,
    Job,
    Application,
    BusinessService,
    BusinessBooking,
    BusinessBundle,
    BusinessAddon,
    PrivateMainCategory,
    PrivateService,
    PrivateBooking,
    AvailableZipCode,
    NotAvailableZipRequest,
    CallRequest,
    EmailRequest,
    PrivateAddon,
    ServiceQuestionRule,
    AddonRule,
    ScheduleRule,
    DateSurcharge,
    BookingStatusHistory,
    NoShowReport,
    ServiceCard,
    ServicePricing,
    ServiceEstimate,
    ServiceEcoPromise,
    ServiceEcoPoint,
)
from jsoneditor.forms import JSONEditor
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.http import HttpResponseRedirect
from accounts.models import BookingChecklist
from accounts.models import BookingChecklist   # ✅ استيراد فقط
# # Register your models here.
# أعلى الملف
from accounts.models import PointsTransaction

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
admin.site.register(BookingStatusHistory)


class BookingChecklistInline(admin.StackedInline):
    model = BookingChecklist
    extra = 0
    can_delete = False

@admin.register(BusinessBooking)
class BusinessBookingAdmin(admin.ModelAdmin):
    change_form_template = "admin/home/businessbooking/change_form.html"

    list_display = (
        "id",
        "company_name",
        "email",
        "phone",
        "status",
        "total_price",
        "refund_amount",
        "is_refunded",
        "path_type",
        "created_at",
    )
    inlines = [BookingChecklistInline]  
    search_fields = ("company_name", "email", "phone")
    ordering = ("-created_at",)

    # =========================
    # PRETTY JSON
    # =========================
    def pretty_json_colored(self, data):
        if not data:
            return format_html("<span style='color:#6c757d;'>—</span>")

        html = '<div style="display:flex;flex-wrap:wrap;gap:6px;">'

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
    # FIELDSETS (مرة وحدة فقط)
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

        ("Assignment", {
            "fields": ("provider",),
        }),

        ("Schedule", {
            "fields": (
                "start_date",
                "preferred_time",
                "quoted_duration_minutes",  # ⏱ هنا
                "days_type",
                "custom_date",
                "custom_time",
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

        ("Pricing", {
            "fields": ("total_price",),
            "classes": ("collapse",),
        }),

        ("💰 Refund (Admin Only)", {
            "fields": ("refund_amount", "refund_reason", "is_refunded"),
            "classes": ("collapse",),
        }),


        ("System", {
            "fields": ("status", "created_at"),
        }),


    )

    # =========================
    # READONLY (مرة وحدة فقط)
    # =========================
    def get_readonly_fields(self, request, obj=None):
        if not obj:
            return ()

        model_fields = [f.name for f in self.model._meta.fields]

        hidden_json_fields = ("services_needed", "addons", "frequency")
        pretty_fields = ("services_needed_pretty", "addons_pretty", "frequency_pretty")

        # 🔒 VIEW MODE: كلشي Read-only
        if request.GET.get("edit") != "1":
            return tuple(model_fields) + pretty_fields

        # ✏️ EDIT MODE: شو بدنا نفتح؟
        editable_fields = (
            # Assignment
            "provider",

            # Schedule
            "start_date",
            "preferred_time",
            "days_type",
            "custom_date",
            "custom_time",
            "quoted_duration_minutes",

            # Pricing / refund
            "refund_amount",
            "refund_reason",
            "is_refunded",
        )

        # كل الحقول ما عدا editable = Read-only
        return tuple(
            f for f in model_fields
            if f not in editable_fields
            and f not in hidden_json_fields
        ) + pretty_fields

    def response_change(self, request, obj):
        if "_cancel_booking" in request.POST:

            refund_amount = None

            # إذا كان Business → خلي الأدمن يكتب المبلغ
            if obj.total_price > 0:
                refund_amount = obj.total_price
            else:
                # Business بدون سعر (manual)
                refund_amount = obj.refund_amount or None

            obj.cancel_by_admin(
                admin_user=request.user,
                note="Cancelled from admin",
                refund_amount=refund_amount
            )

            self.message_user(
                request,
                "❌ Booking cancelled & refund applied successfully."
            )
            return HttpResponseRedirect(".")

        return super().response_change(request, obj)




    # =========================
    # SAVE_MODEL (مرة وحدة فقط)
    #  - assign provider
    #  - apply refund
    # =========================
  
    def cancel_booking(self, request, queryset):
        for booking in queryset:
            booking.cancel_by_admin(admin_user=request.user, note="Cancelled from admin")
    cancel_booking.short_description = "❌ Cancel selected bookings"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


    def save_model(self, request, obj, form, change):
        old = None
        if change:
            old = BusinessBooking.objects.get(pk=obj.pk)

        super().save_model(request, obj, form, change)

        # =========================
        # PROVIDER ASSIGN LOGIC
        # =========================
        if obj.provider and old and old.provider != obj.provider:
            obj.assign_provider(
                provider=obj.provider,
                user=request.user
            )
        elif obj.provider and obj.status == "ORDERED":
            obj.assign_provider(
                provider=obj.provider,
                user=request.user
            )

        # =========================
        # ⭐ LOYALTY POINTS
        # =========================
        admin_points = form.cleaned_data.get("admin_points")

        if admin_points and admin_points != 0 and obj.user:
            PointsTransaction.objects.create(
                user=obj.user,
                amount=admin_points,
                reason=f"Admin adjustment – Business Booking #{obj.id}"
            )

            self.message_user(
                request,
                f"✅ {admin_points} loyalty points applied.",
                messages.SUCCESS
            )


    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        form.base_fields["admin_points"] = forms.IntegerField(
            required=False,
            label="⭐ Loyalty Points (Admin)",
            help_text="Add or deduct points (use negative number to deduct)"
        )
        return form



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


class BusinessBundleAdminForm(forms.ModelForm):
    what_included_text = forms.CharField(
        required=False,
        label="What's included (one per line)",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter one item per line.",
    )
    why_choose_text = forms.CharField(
        required=False,
        label="Why choose this bundle (one per line)",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter one item per line.",
    )
    addons_text = forms.CharField(
        required=False,
        label="Popular add-ons (one per line)",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Enter one item per line.",
    )

    class Meta:
        model = BusinessBundle
        fields = (
            "title",
            "slug",
            "discount",
            "short_description",
            "target_audience",
            "what_included_text",
            "why_choose_text",
            "addons_text",
            "notes",
            "image",
        )

    def _lines_to_list(self, value):
        if not value:
            return []
        return [line.strip() for line in value.splitlines() if line.strip()]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["what_included_text"].initial = "\n".join(
                self.instance.what_included or []
            )
            self.fields["why_choose_text"].initial = "\n".join(
                self.instance.why_choose or []
            )
            self.fields["addons_text"].initial = "\n".join(self.instance.addons or [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.what_included = self._lines_to_list(
            self.cleaned_data.get("what_included_text")
        )
        instance.why_choose = self._lines_to_list(
            self.cleaned_data.get("why_choose_text")
        )
        instance.addons = self._lines_to_list(self.cleaned_data.get("addons_text"))
        if commit:
            instance.save()
        return instance


@admin.register(BusinessBundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("title", "discount")
    prepopulated_fields = {"slug": ("title",)}
    form = BusinessBundleAdminForm





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


class ServiceCardInline(admin.StackedInline):
    model = ServiceCard
    extra = 0
    fields = ("title", "icon", "body", "order")


class ServicePricingInline(admin.StackedInline):
    model = ServicePricing
    extra = 0
    fields = (
        "title",
        "card_title",
        "subtitle",
        "price_label",
        "price_value",
        "price_note",
        "description",
        "cta_text",
        "cta_url",
    )


class ServiceEstimateInline(admin.StackedInline):
    model = ServiceEstimate
    extra = 0
    fields = ("title", "property_label", "bedrooms_label", "cta_text", "note")


class ServiceEcoPromiseInline(admin.StackedInline):
    model = ServiceEcoPromise
    extra = 0
    fields = ("title", "subtitle", "cta_text")


class ServiceEcoPointInline(admin.TabularInline):
    model = ServiceEcoPoint
    extra = 0
    fields = ("title", "body", "icon", "order")




@admin.register(ScheduleRule)
class ScheduleRuleAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "price_change")
    

@admin.register(PrivateService)
class PrivateServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "slug", "price")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        ("Basic Info", {
            "fields": (
                "category",
                "title",
                "slug",
                "price",
                "description",
                "recommended",
                "image",
            )
        }),
        ("Hero / Introduction", {
            "fields": (
                "hero_image",
                "hero_subtitle",
                "intro_text",
                "starting_price",
                "hero_cta_text",
                "hero_cta_url",
            ),
            "classes": ("collapse",),
        }),
        ("Questions (JSON)", {
            "fields": ("questions",),
            "classes": ("collapse",)
        }),
    )
    inlines = [
        PrivateAddonInline,
        ServiceQuestionRuleInline,
        ServiceCardInline,
        ServicePricingInline,
        ServiceEstimateInline,
        ServiceEcoPromiseInline,
    ]


@admin.register(ServiceCard)
class ServiceCardAdmin(admin.ModelAdmin):
    list_display = ("service", "title", "order")


@admin.register(ServiceEcoPromise)
class ServiceEcoPromiseAdmin(admin.ModelAdmin):
    list_display = ("service", "title")
    inlines = [ServiceEcoPointInline]


@admin.register(ServicePricing)
class ServicePricingAdmin(admin.ModelAdmin):
    list_display = ("service", "title", "price_value")


@admin.register(ServiceEstimate)
class ServiceEstimateAdmin(admin.ModelAdmin):
    list_display = ("service", "title")


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

    list_display = (
        "id",
        "status",
        "total_price",
        "refund_amount",
        "is_refunded",
        "created_at",
    )
    inlines = [BookingChecklistInline]
    list_filter = ("booking_method", "zip_is_available", "schedule_mode")
    search_fields = ("id", "zip_code")
    ordering = ("-created_at",)

    # =========================
    # PRETTY JSON (مثل شغلك)
    # =========================
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
        elif isinstance(data, dict):
            for key, value in data.items():
                html += f"""
                <div style="
                    background:#ffffff;
                    border:1px solid #dee2e6;
                    border-radius:8px;
                    padding:10px;
                    margin-bottom:10px;
                ">
                    <div style="font-weight:700;color:#6f42c1;margin-bottom:6px;">
                        🧹 {key}
                    </div>
                """
                if isinstance(value, dict) and "title" in value:
                    html += f"""
                    <div style="background:#f1f3f5;border-radius:8px;padding:8px;margin-left:10px;">
                        <div style="font-weight:700;">🧺 {value.get('title')}</div>
                        <div style="margin-left:10px;">
                            Quantity: <b>{value.get('quantity', '-')}</b><br>
                            Unit price: <b>${value.get('unit_price', 0)}</b><br>
                            Total: <b style="color:#198754;">${value.get('price', 0)}</b>
                        </div>
                    </div>
                    """
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

    # =========================
    # FIELDSETS (مرة وحدة)
    # =========================
    base_fieldsets = (
        ("ZIP Code Check", {"fields": ("zip_code", "zip_is_available")}),
        ("Booking Method", {"fields": ("booking_method", "schedule_mode")}),

        ("Category & Services", {
            "fields": ("main_category", "selected_services_pretty", "service_answers_pretty")
        }),

        ("Add-ons", {"fields": ("addons_selected_pretty",)}),

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

        ("Per-Service Scheduling", {"fields": ("service_schedules_pretty",)}),

        ("Checkout", {
            "fields": ("subtotal", "rot_discount", "total_price", "address", "area", "duration_hours"),
            "classes": ("collapse",)
        }),

        ("💰 Refund (Admin Only)", {
            "fields": ("refund_amount", "refund_reason", "is_refunded"),
            "classes": ("collapse",),
        }),

        ("System Fields", {"fields": ("status", "created_at")}),
    )

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

    # =========================
    # READONLY (مرة وحدة)
    # =========================
    def get_readonly_fields(self, request, obj=None):
        if not obj:
            return ()

        model_fields = [f.name for f in self.model._meta.fields]
        pretty = (
            "selected_services_pretty",
            "service_answers_pretty",
            "addons_selected_pretty",
            "service_schedules_pretty",
            "special_timing_requests_pretty",
        )

        # View mode: readonly
        ro = tuple(model_fields) + pretty

        # Edit mode: allow refund fields
        if request.GET.get("edit") == "1":
            ro = tuple(
                f for f in model_fields
                if f not in ("refund_amount", "refund_reason", "is_refunded")
            ) + pretty

        # إذا refunded: قفل كل شي
        if obj.is_refunded:
            ro = tuple(model_fields) + pretty

        return ro

    # =========================
    # SAVE = APPLY REFUND (مرة وحدة)
    # =========================
    def save_model(self, request, obj, form, change):
        old = None
        if change:
            old = BusinessBooking.objects.get(pk=obj.pk)

        super().save_model(request, obj, form, change)

        # ✅ الحالة 1: provider تغيّر
        if obj.provider and old and old.provider != obj.provider:
            obj.assign_provider(
                provider=obj.provider,
                user=request.user
            )

        # ✅ الحالة 2: provider موجود لكن الحالة لسه ORDERED
        elif obj.provider and obj.status == "ORDERED":
            obj.assign_provider(
                provider=obj.provider,
                user=request.user
            )

    def has_add_permission(self, request):
        return False

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
    class DateSurchargeForm(forms.ModelForm):
        WEEKDAY_CHOICES = [
            ("Mon", "Monday"),
            ("Tue", "Tuesday"),
            ("Wed", "Wednesday"),
            ("Thu", "Thursday"),
            ("Fri", "Friday"),
            ("Sat", "Saturday"),
            ("Sun", "Sunday"),
        ]

        weekday = forms.ChoiceField(choices=[("", "---------")] + WEEKDAY_CHOICES, required=False)

        class Meta:
            model = DateSurcharge
            fields = "__all__"

        def clean(self):
            cleaned = super().clean()
            rule_type = cleaned.get("rule_type")
            weekday = cleaned.get("weekday")
            date = cleaned.get("date")

            if rule_type == "weekday":
                if not weekday:
                    self.add_error("weekday", "Please choose a weekday.")
                cleaned["date"] = None
            elif rule_type == "date":
                if not date:
                    self.add_error("date", "Please select a date.")
                cleaned["weekday"] = None

            return cleaned

    form = DateSurchargeForm
    list_display = ("rule_type", "weekday", "date", "amount", "surcharge_type")
    list_filter = ("rule_type", "weekday", "date")
    change_form_template = "admin/home/datesurcharge/change_form.html"

    class Media:
        js = ("admin/date_surcharge.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "quick-weekend/",
                self.admin_site.admin_view(self.quick_weekend),
                name="home_datesurcharge_quick_weekend",
            ),
        ]
        return custom + urls

    def quick_weekend(self, request):
        if not self.has_add_permission(request):
            messages.error(request, "You do not have permission to add surcharges.")
            return redirect("..")

        amount_raw = request.GET.get("amount", "10")
        surcharge_type = request.GET.get("type", "percent")
        try:
            amount = float(amount_raw)
        except ValueError:
            amount = 10

        for weekday in ("Sat", "Sun"):
            obj, created = DateSurcharge.objects.get_or_create(
                rule_type="weekday",
                weekday=weekday,
                defaults={"amount": amount, "surcharge_type": surcharge_type},
            )
            if not created:
                obj.amount = amount
                obj.surcharge_type = surcharge_type
                obj.save(update_fields=["amount", "surcharge_type"])

        messages.success(request, "Weekend surcharges updated for Saturday and Sunday.")
        return redirect("..")




@admin.register(NoShowReport)
class NoShowReportAdmin(admin.ModelAdmin):
    list_display = ("booking_type", "booking_id", "provider", "decision", "created_at")
    list_filter = ("decision", "booking_type")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        previous_decision = None

        if obj.pk:
            previous_decision = NoShowReport.objects.get(pk=obj.pk).decision

        # حفظ التعديل أولاً
        super().save_model(request, obj, form, change)

        # إذا تغيّر القرار
        if previous_decision != obj.decision:
            booking = self.get_booking(obj)

            if not booking:
                return

            if obj.decision == "APPROVED":
                booking.approve_no_show(
                    admin_user=request.user,
                    note=obj.reviewed_note or obj.provider_note or "No show approved"
                )

            elif obj.decision == "REJECTED":
                booking.reject_no_show(
                    admin_user=request.user,
                    note=obj.reviewed_note or "No show rejected"
                )

            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            obj.save(update_fields=["reviewed_by", "reviewed_at"])

    def get_booking(self, obj):
        if obj.booking_type == "private":
            return PrivateBooking.objects.filter(id=obj.booking_id).first()
        return BusinessBooking.objects.filter(id=obj.booking_id).first()

    list_display = (
        "booking_type",
        "booking_id",
        "provider",
        "decision",
        "created_at",
    )
    list_filter = ("decision",)
    actions = ["approve_no_show", "reject_no_show"]

    def approve_no_show(self, request, queryset):
        for report in queryset:

            if report.booking_type == "private":
                booking = PrivateBooking.objects.filter(id=report.booking_id).first()
            else:
                booking = BusinessBooking.objects.filter(id=report.booking_id).first()

            if not booking:
                continue

            # 🔴 هذا هو السطر اللي كان ناقصك
            booking.approve_no_show(
                admin_user=request.user,
                note="Customer not available (No Show)"
            )

            report.decision = "APPROVED"
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.save()

    approve_no_show.short_description = "✅ Approve No Show"

    def reject_no_show(self, request, queryset):
        queryset.update(
            decision="REJECTED",
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )

    reject_no_show.short_description = "❌ Reject No Show"
