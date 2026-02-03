from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from accounts.models import DiscountCode
from .pricing_utils import calculate_booking_price
from django.shortcuts import render, redirect, get_object_or_404
from .forms import (
    ContactForm, ApplicationForm, BusinessCompanyInfoForm, OfficeSetupForm , ZipCheckForm, NotAvailableZipForm,CallRequestForm, FeedbackRequestForm
)
from django.views.decorators.http import require_POST

from .models import (
    Job, Application, BookingNote, BusinessBooking, BusinessService, DateSurcharge, PrivateAddon,
    BusinessBundle, BusinessAddon, PrivateService, AvailableZipCode, PrivateBooking, CallRequest,
    EmailRequest, PrivateMainCategory, FeedbackRequest, NoShowReport, BookingStatusHistory,
    Contact,
    ScheduleRule,
)
from accounts.models import (
    Customer,
    BookingRequestFix,
    CustomerNotification,
    CustomerNote,
    Incident,
    ServiceReview,
    ProviderProfile,
    ProviderAdminMessage,
    ChatMessage,
)
from django.http import JsonResponse
import json
from django.contrib import messages
import json
from datetime import datetime  # فوق
from .pricing_utils import calculate_booking_price
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django import forms
from django.forms import modelform_factory
from django.db.models import Q, JSONField
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe

from .dashboard import get_dashboard_items, get_item_by_slug

# ================================
# STATIC PAGES
# ================================
def home(request):
    feedbacks = list(FeedbackRequest.objects.order_by("-created_at"))
    return render(request, "home/home.html", {"feedbacks": feedbacks})

def about(request):
    return render(request, "home/about.html")

def faq(request):
    return render(request, "home/FAQ.html")

def Privacy_Policy(request):
    return render(request, "home/Privacy_Policy.html")

def Cookies_Policy(request):
    return render(request, "home/Cookies_Policy.html")

def Accessibility_Statement(request):
    return render(request, "home/Accessibility_Statement.html")

def T_C(request):
    return render(request, "home/T&C.html")


def feedback_request(request):
    form = FeedbackRequestForm()
    if request.method == "POST":
        form = FeedbackRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you! We received your message.")
            return redirect("home:feedback_request")
    return render(request, "home/feedback_request.html", {"form": form})


@require_POST
def service_contact_submit(request):
    service_slug = (request.POST.get("service_slug") or "").strip()
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    person_number = (request.POST.get("person_number") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    message = (request.POST.get("message") or "").strip()

    if service_slug:
        message = f"[Service: {service_slug}]\n{message}"

    Contact.objects.create(
        first_name=first_name or "Guest",
        last_name=last_name or "",
        email=email or "no-reply@example.com",
        country_code=person_number or "+1",
        phone=phone or "",
        message=message or "",
        inquiry_type="general",
        preferred_method="email",
    )

    if service_slug:
        return redirect("accounts:service_detail", slug=service_slug)
    return redirect("home:home")


def _staff_required(user):
    return user.is_authenticated and user.is_staff


def _dashboard_notifications():
    def _booking_dashboard_url(booking_type, booking_id):
        if booking_type == "business":
            slug = "business-bookings"
        elif booking_type == "private":
            slug = "private-bookings"
        else:
            return "/dashboard/"
        return f"/dashboard/{slug}/{booking_id}/edit/"

    def _status_label(status_value):
        labels = {
            "ORDERED": "Order placed",
            "SCHEDULED": "Confirmed / Scheduled",
            "ASSIGNED": "Provider assigned",
            "ON_THE_WAY": "Provider on the way",
            "STARTED": "Service started",
            "PAUSED": "Service paused",
            "RESUMED": "Service resumed",
            "COMPLETED": "Service completed",
            "CANCELLED_BY_CUSTOMER": "Cancelled by customer",
            "NO_SHOW": "No show",
            "INCIDENT_REPORTED": "Incident reported",
            "REFUNDED": "Refunded",
        }
        return labels.get(status_value, status_value)
    now = timezone.now()
    since = now - timedelta(days=1)

    new_private = PrivateBooking.objects.filter(created_at__gte=since).count()
    new_business = BusinessBooking.objects.filter(created_at__gte=since).count()
    new_contacts = Contact.objects.filter(created_at__gte=since).count()
    new_incidents = Incident.objects.filter(created_at__gte=since).count()
    new_reviews = ServiceReview.objects.filter(created_at__gte=since).count()
    new_messages = ChatMessage.objects.filter(created_at__gte=since).count()
    new_customers = Customer.objects.filter(user__date_joined__gte=since).count()
    new_providers = ProviderProfile.objects.filter(user__date_joined__gte=since).count()
    pending_no_show = NoShowReport.objects.filter(decision="PENDING").count()
    open_request_fixes = BookingRequestFix.objects.filter(status="OPEN").count()
    updated_customer_notes = CustomerNote.objects.filter(updated_at__gte=since).count()

    recent_status = list(
        BookingStatusHistory.objects.filter(created_at__gte=since)
        .order_by("-created_at")[:6]
    )
    recent_fixes = list(
        BookingRequestFix.objects.filter(created_at__gte=since)
        .order_by("-created_at")[:6]
    )
    recent_contacts = list(
        Contact.objects.filter(created_at__gte=since)
        .order_by("-created_at")[:6]
    )
    recent_customer_notes = list(
        CustomerNote.objects.filter(updated_at__gte=since)
        .select_related("customer")
        .order_by("-updated_at")[:6]
    )
    recent_incidents = list(
        Incident.objects.filter(created_at__gte=since)
        .select_related("customer")
        .order_by("-created_at")[:6]
    )
    recent_reviews = list(
        ServiceReview.objects.filter(created_at__gte=since)
        .select_related("customer")
        .order_by("-created_at")[:6]
    )
    recent_messages = list(
        ChatMessage.objects.filter(created_at__gte=since)
        .select_related("sender", "thread")
        .order_by("-created_at")[:6]
    )

    items = []
    for r in recent_status:
        status_text = _status_label(r.status)
        note = (r.note or "").strip()
        detail = f"Status update: {status_text}"
        if note and note.lower() != status_text.lower():
            detail = f"{detail} - {note}"
        items.append({
            "title": f"{r.booking_type.title()} #{r.booking_id} - {status_text}",
            "detail": detail,
            "time": r.created_at,
            "url": _booking_dashboard_url(r.booking_type, r.booking_id),
        })
    for fix in recent_fixes:
        items.append({
            "title": f"Request Fix #{fix.id}",
            "detail": f"{fix.booking_type.title()} booking #{fix.booking_id}",
            "time": fix.created_at,
            "url": "/dashboard/request-fixes/",
        })
    for contact in recent_contacts:
        items.append({
            "title": f"Contact: {contact.first_name} {contact.last_name}".strip(),
            "detail": contact.inquiry_type or "Contact form",
            "time": contact.created_at,
            "url": "/dashboard/contacts/",
        })
    for note in recent_customer_notes:
        items.append({
            "title": "Customer Notes Updated",
            "detail": getattr(note.customer, "email", "") or str(note.customer),
            "time": note.updated_at,
            "url": "/dashboard/customer-notes/",
        })
    for inc in recent_incidents:
        items.append({
            "title": f"Incident #{inc.id}",
            "detail": getattr(inc.customer, "email", "") or str(inc.customer),
            "time": inc.created_at,
            "url": "/dashboard/incidents/",
        })
    for rev in recent_reviews:
        items.append({
            "title": f"New Review: {rev.service_title}",
            "detail": getattr(rev.customer, "email", "") or str(rev.customer),
            "time": rev.created_at,
            "url": "/dashboard/service-reviews/",
        })
    for msg in recent_messages:
        booking_type = msg.thread.booking_type
        booking_id = msg.thread.booking_id
        message_preview = (msg.text or "").strip()
        if len(message_preview) > 60:
            message_preview = f"{message_preview[:60]}..."
        detail = f"{booking_type.title()} #{booking_id}"
        if message_preview:
            detail = f"{detail} - {message_preview}"
        items.append({
            "title": f"New Message from {msg.sender}",
            "detail": detail,
            "time": msg.created_at,
            "url": _booking_dashboard_url(booking_type, booking_id),
        })
    items = sorted(items, key=lambda i: i["time"], reverse=True)[:6]

    total = (
        new_private
        + new_business
        + new_contacts
        + new_incidents
        + new_reviews
        + new_messages
        + new_customers
        + new_providers
        + pending_no_show
        + open_request_fixes
        + updated_customer_notes
    )
    return {
        "dashboard_notif_count": total,
        "dashboard_notif_items": items,
        "dashboard_new_bookings": new_private + new_business,
        "dashboard_pending_no_show": pending_no_show,
        "dashboard_open_fixes": open_request_fixes,
        "dashboard_notif_meter": min(total, 100),
        "dashboard_new_customers": new_customers,
        "dashboard_new_providers": new_providers,
        "dashboard_new_incidents": new_incidents,
        "dashboard_new_reviews": new_reviews,
        "dashboard_new_messages": new_messages,
    }


@user_passes_test(_staff_required)
def dashboard_notifications_api(request):
    data = _dashboard_notifications()
    return JsonResponse({
        "count": data["dashboard_notif_count"],
        "new_bookings": data["dashboard_new_bookings"],
        "pending_no_show": data["dashboard_pending_no_show"],
        "new_customers": data.get("dashboard_new_customers", 0),
        "new_incidents": data.get("dashboard_new_incidents", 0),
        "new_reviews": data.get("dashboard_new_reviews", 0),
        "new_messages": data.get("dashboard_new_messages", 0),
        "items": [
            {
                "title": i["title"],
                "detail": i["detail"],
                "time": i["time"].strftime("%b %d, %I:%M %p"),
                "url": i.get("url", ""),
            }
            for i in data["dashboard_notif_items"]
        ],
    })


@user_passes_test(_staff_required)
def dashboard_home(request):
    items = get_dashboard_items()
    cards = []
    now = timezone.now()
    for item in items:
        try:
            count = item.model.objects.count()
        except Exception:
            count = 0
        alert_count = 0
        if item.model == PrivateBooking:
            alert_count = PrivateBooking.objects.filter(created_at__gte=now - timedelta(days=1)).count()
        elif item.model == BusinessBooking:
            alert_count = BusinessBooking.objects.filter(created_at__gte=now - timedelta(days=1)).count()
        elif item.model == NoShowReport:
            alert_count = NoShowReport.objects.filter(decision="PENDING").count()
        cards.append({
            "slug": item.slug,
            "label": item.label,
            "icon": item.icon,
            "count": count,
            "alert_count": alert_count,
        })
    context = {"cards": cards, "items": items}
    context.update(_dashboard_notifications())
    return render(request, "dashboard/index.html", context)


@user_passes_test(_staff_required)
def dashboard_change_password(request):
    if request.method != "POST":
        return redirect("home:dashboard_home")

    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Password updated successfully.")
    else:
        messages.error(request, "Please check the password fields and try again.")

    return redirect("home:dashboard_home")


def _model_fields(model):
    fields = []
    for f in model._meta.fields:
        if f.auto_created:
            continue
        fields.append(f.name)
    return fields


JSON_EDIT_MODELS = {PrivateService, PrivateAddon}
JSON_EDIT_FIELDS = {
    PrivateService: {"questions"},
    PrivateAddon: {"questions"},
}


class BusinessBundleDashboardForm(forms.ModelForm):
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


class BusinessBookingDashboardForm(forms.ModelForm):
    services_needed_text = forms.CharField(
        required=False,
        label="Services needed (one per line)",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter one service per line.",
    )
    addons_text = forms.CharField(
        required=False,
        label="Add-ons (one per line)",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter one add-on per line.",
    )
    frequency_type = forms.ChoiceField(
        required=False,
        label="Frequency type",
        choices=[
            ("", "Select frequency"),
            ("daily", "Daily"),
            ("times_per_week", "Times per week"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("ondemand", "On-demand"),
            ("yearly", "Yearly"),
        ],
    )
    frequency_times = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=7,
        label="Times per week (if applicable)",
    )

    class Meta:
        model = BusinessBooking
        fields = "__all__"

    def _lines_to_list(self, value):
        if not value:
            return []
        return [line.strip() for line in value.splitlines() if line.strip()]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            services = self.instance.services_needed or []
            addons = self.instance.addons or []
            if isinstance(services, (list, tuple)):
                self.fields["services_needed_text"].initial = "\n".join(map(str, services))
            else:
                self.fields["services_needed_text"].initial = str(services)
            if isinstance(addons, (list, tuple)):
                self.fields["addons_text"].initial = "\n".join(map(str, addons))
            else:
                self.fields["addons_text"].initial = str(addons)

            freq = self.instance.frequency or {}
            if isinstance(freq, dict):
                freq_type = freq.get("type") or ""
                if freq_type == "times_per_week":
                    self.fields["frequency_type"].initial = "times_per_week"
                    self.fields["frequency_times"].initial = freq.get("value") or ""
                else:
                    self.fields["frequency_type"].initial = freq_type
            else:
                self.fields["frequency_type"].initial = ""

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.services_needed = self._lines_to_list(
            self.cleaned_data.get("services_needed_text")
        )
        instance.addons = self._lines_to_list(self.cleaned_data.get("addons_text"))

        freq_type = self.cleaned_data.get("frequency_type") or ""
        if freq_type == "times_per_week":
            value = self.cleaned_data.get("frequency_times") or 1
            instance.frequency = {"type": "times_per_week", "value": value}
        elif freq_type:
            instance.frequency = {"type": freq_type}
        else:
            instance.frequency = None

        if commit:
            instance.save()
        return instance


EMOJI_OPTIONS = [
    "🧹", "🧽", "🧼", "🧴", "🧺", "🧻", "🧤", "🪣", "🪟", "🧯",
    "🧪", "🧫", "🧷", "🪤", "🧰", "🪛", "🔧", "🧲", "🚽", "🚿",
    "🛁", "🧊", "🧺", "🧴", "🧹", "🧼", "🪟"
]


class BusinessAddonDashboardForm(forms.ModelForm):
    emoji = forms.CharField(
        required=False,
        label="Emoji",
        help_text="Pick an emoji from the list or type your own. Tip: press Windows + . to open the emoji picker.",
        widget=forms.TextInput(attrs={
            "list": "emoji-options",
            "placeholder": "Pick an emoji",
        }),
    )

    class Meta:
        model = BusinessAddon
        fields = "__all__"


class DateSurchargeDashboardForm(forms.ModelForm):
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


class ScheduleRuleDashboardForm(forms.ModelForm):
    KEY_CHOICES = [
        ("frequency_type", "Frequency"),
        ("day", "Day of week"),
    ]

    key = forms.ChoiceField(choices=[("", "---------")] + KEY_CHOICES)

    class Meta:
        model = ScheduleRule
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["key"].label = "Rule type"
        self.fields["value"].label = "Rule value"
        self.fields["price_change"].label = "Price change (%)"
        self.fields["value"].widget.attrs.update({
            "list": "scheduleRuleValues",
            "placeholder": "Pick a value (or type a custom one)",
        })
        self.fields["price_change"].help_text = "Use negative for discounts (e.g. -15). Positive adds a surcharge."


def _exclude_fields_for_form(model):
    excluded = []
    for f in model._meta.fields:
        if f.auto_created:
            excluded.append(f.name)
        if isinstance(f, JSONField) and model not in JSON_EDIT_MODELS:
            excluded.append(f.name)
        if isinstance(f, JSONField) and model in JSON_EDIT_MODELS:
            allowed = JSON_EDIT_FIELDS.get(model, set())
            if allowed and f.name not in allowed:
                excluded.append(f.name)
        if getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
            excluded.append(f.name)
    if model.__name__ == "PrivateAddon" and f.name == "form_html":
        excluded.append(f.name)
    return list(dict.fromkeys(excluded))


def _json_readonly(obj, exclude_fields=()):
    data = {}
    for f in obj._meta.fields:
        if isinstance(f, JSONField):
            if f.name in exclude_fields:
                continue
            data[f.name] = getattr(obj, f.name)
    return data


def _json_formfield_callback(model, db_field, **kwargs):
    if isinstance(db_field, JSONField):
        if model in JSON_EDIT_MODELS and db_field.name in JSON_EDIT_FIELDS.get(model, set()):
            return forms.JSONField(
                label=db_field.verbose_name,
                required=not db_field.blank,
                widget=forms.Textarea(attrs={
                    "rows": 8,
                    "placeholder": (
                        "{\"q1\": {\"label\": \"Question\", \"type\": \"select\", "
                        "\"options\": [\"Option 1\", \"Option 2\"]}}"
                    ),
                }),
                help_text=(
                    "Paste valid JSON. Example keys: label, type, options."
                ),
            )
        return forms.JSONField(
            label=db_field.verbose_name,
            required=not db_field.blank,
            widget=forms.Textarea(attrs={"rows": 6}),
        )
    return db_field.formfield(**kwargs)


def _bootstrap_form(form):
    for name, field in form.fields.items():
        widget = field.widget
        base_class = widget.attrs.get("class", "")
        input_type = getattr(widget, "input_type", "")
        if input_type in ("checkbox", "radio"):
            widget.attrs["class"] = f"{base_class} form-check-input".strip()
        elif widget.__class__.__name__ in ("Select", "SelectMultiple"):
            widget.attrs["class"] = f"{base_class} form-select".strip()
        else:
            widget.attrs["class"] = f"{base_class} form-control".strip()
    return form


@user_passes_test(_staff_required)
def dashboard_model_list(request, model):
    item = get_item_by_slug(model)
    if not item:
        return render(request, "dashboard/not_found.html", {"items": get_dashboard_items()})

    qs = item.model.objects.all()
    service_id = request.GET.get("service_id")
    if service_id and item.model.__name__ in {"ServiceCard", "ServicePricing", "ServiceEstimate", "ServiceEcoPromise"}:
        qs = qs.filter(service_id=service_id)
    q = request.GET.get("q", "").strip()
    if q:
        text_fields = [
            f.name for f in item.model._meta.fields
            if f.get_internal_type() in ("CharField", "TextField", "EmailField")
        ]
        query = Q()
        for name in text_fields:
            query |= Q(**{f"{name}__icontains": q})
        qs = qs.filter(query)

    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page"))

    display_fields = _model_fields(item.model)[:5]

    context = {
        "items": get_dashboard_items(),
        "item": item,
        "objects": page,
        "display_fields": display_fields,
        "query": q,
    }
    context.update(_dashboard_notifications())
    return render(request, "dashboard/list.html", context)


@user_passes_test(_staff_required)
def dashboard_model_create(request, model):
    item = get_item_by_slug(model)
    if not item:
        return render(request, "dashboard/not_found.html", {"items": get_dashboard_items()})

    if item.model == BusinessBundle:
        Form = BusinessBundleDashboardForm
    elif item.model == BusinessBooking:
        Form = modelform_factory(
            item.model,
            form=BusinessBookingDashboardForm,
            exclude=_exclude_fields_for_form(item.model),
        )
    elif item.model == BusinessAddon:
        Form = BusinessAddonDashboardForm
    elif item.model == DateSurcharge:
        Form = DateSurchargeDashboardForm
    elif item.model == ScheduleRule:
        Form = ScheduleRuleDashboardForm
    else:
        Form = modelform_factory(
            item.model,
            exclude=_exclude_fields_for_form(item.model),
            formfield_callback=lambda db_field, **kwargs: _json_formfield_callback(item.model, db_field, **kwargs),
        )
    if request.method == "POST":
        form = Form(request.POST, request.FILES)
        form = _bootstrap_form(form)
        if form.is_valid():
            obj = form.save(commit=False)
            if isinstance(obj, ProviderAdminMessage) and not obj.created_by_id:
                obj.created_by = request.user
            obj.save()
            return redirect("home:dashboard_model_list", model=item.slug)
    else:
        initial = {}
        if item.model == PrivateAddon:
            service_id = request.GET.get("service_id")
            if service_id:
                initial["service"] = service_id
        if item.model == ProviderAdminMessage:
            provider_id = request.GET.get("provider_id")
            if provider_id:
                initial["provider"] = provider_id
        form = _bootstrap_form(Form(initial=initial))

    context = {
        "items": get_dashboard_items(),
        "item": item,
        "form": form,
        "mode": "create",
        "emoji_datalist": EMOJI_OPTIONS if item.model == BusinessAddon else None,
    }
    context.update(_dashboard_notifications())
    return render(request, "dashboard/form.html", context)


@user_passes_test(_staff_required)
def dashboard_model_edit(request, model, pk):
    item = get_item_by_slug(model)
    if not item:
        return render(request, "dashboard/not_found.html", {"items": get_dashboard_items()})

    obj = get_object_or_404(item.model, pk=pk)
    prev_status = None
    if item.model.__name__ == "BookingRequestFix":
        prev_status = getattr(obj, "status", None)
    if item.model == BusinessBundle:
        Form = BusinessBundleDashboardForm
    elif item.model == BusinessBooking:
        Form = modelform_factory(
            item.model,
            form=BusinessBookingDashboardForm,
            exclude=_exclude_fields_for_form(item.model),
        )
    elif item.model == BusinessAddon:
        Form = BusinessAddonDashboardForm
    elif item.model == DateSurcharge:
        Form = DateSurchargeDashboardForm
    elif item.model == ScheduleRule:
        Form = ScheduleRuleDashboardForm
    else:
        Form = modelform_factory(
            item.model,
            exclude=_exclude_fields_for_form(item.model),
            formfield_callback=lambda db_field, **kwargs: _json_formfield_callback(item.model, db_field, **kwargs),
        )
    if request.method == "POST":
        form = Form(request.POST, request.FILES, instance=obj)
        form = _bootstrap_form(form)
        if form.is_valid():
            obj = form.save()
            if item.model.__name__ == "BookingRequestFix":
                new_status = getattr(obj, "status", None)
                if prev_status and new_status and new_status != prev_status:
                    CustomerNotification.objects.create(
                        user=obj.customer,
                        title="Request Fix Updated",
                        body=f"Your request fix for booking #{obj.booking_id} is now {new_status.replace('_', ' ').title()}.",
                        notification_type="request_fix",
                        booking_type=obj.booking_type,
                        booking_id=obj.booking_id,
                        request_fix=obj,
                    )
            return redirect("home:dashboard_model_list", model=item.slug)
    else:
        form = _bootstrap_form(Form(instance=obj))

    addon_form_preview = None
    addons_for_service = None
    if item.model.__name__ == "PrivateAddon" and obj.form_html:
        addon_form_preview = mark_safe(obj.form_html)
    if item.model == PrivateService:
        addons_for_service = PrivateAddon.objects.filter(service=obj).order_by("title")

    json_readonly = None
    if item.model not in {BusinessBundle, BusinessBooking}:
        json_readonly = _json_readonly(
            obj,
            exclude_fields=JSON_EDIT_FIELDS.get(item.model, set())
        )

    context = {
        "items": get_dashboard_items(),
        "item": item,
        "form": form,
        "mode": "edit",
        "object": obj,
        "json_readonly": json_readonly,
        "addon_form_preview": addon_form_preview,
        "addons_for_service": addons_for_service,
        "emoji_datalist": EMOJI_OPTIONS if item.model == BusinessAddon else None,
    }
    context.update(_dashboard_notifications())
    return render(request, "dashboard/form.html", context)


@user_passes_test(_staff_required)
def dashboard_model_delete(request, model, pk):
    item = get_item_by_slug(model)
    if not item:
        return render(request, "dashboard/not_found.html", {"items": get_dashboard_items()})

    obj = get_object_or_404(item.model, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("home:dashboard_model_list", model=item.slug)

    context = {
        "items": get_dashboard_items(),
        "item": item,
        "object": obj,
    }
    context.update(_dashboard_notifications())
    return render(request, "dashboard/confirm_delete.html", context)


@user_passes_test(_staff_required)
def dashboard_date_surcharge_quick_weekend(request):
    amount_raw = request.GET.get("amount", "10")
    surcharge_type = request.GET.get("type", "percent")
    if surcharge_type not in {"percent", "fixed"}:
        surcharge_type = "percent"

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

    return redirect("home:dashboard_model_list", model="date-surcharges")


# ================================
# CONTACT
# ================================
def contact(request):
    show_popup = False

    if request.method == "POST":
        form = ContactForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            show_popup = True
    else:
        form = ContactForm()

    return render(request, "home/contact.html", {
        "form": form,
        "show_popup": show_popup
    })


# ================================
# CAREERS
# ================================
def careers_home(request):
    jobs = Job.objects.filter(is_active=True)

    if jobs.exists():
        return render(request, "home/career_page.html", {"jobs": jobs})

    if request.method == "POST":
        Application.objects.create(
            full_name=request.POST.get("full_name"),
            email=request.POST.get("email"),
            phone=request.POST.get("phone"),
            area=request.POST.get("area"),
            availability=request.POST.get("availability"),
            message=request.POST.get("message"),
            cv=request.FILES.get("cv"),
            job=None,
        )
        return render(request, "home/success_appy.html")

    return render(request, "home/career_page_no opining.html")


def apply_page(request, job_id=None):
    job = Job.objects.filter(id=job_id).first()

    if request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return render(request, "home/success_appy.html")
    else:
        form = ApplicationForm(initial={"job": job})

    return render(request, "home/career_page_available.html", {"form": form, "job": job})


# ================================
# ALL BUSINESS SERVICES
# ================================
def all_services_business(request):
    services = BusinessService.objects.all()
    return render(request, "home/AllServicesBusiness.html", {"services": services})


# ================================
# BOOKING START
# ================================
def business_services(request):
    request.session["business_booking_draft"] = {}
    request.session.modified = True
    return redirect("home:business_company_info", booking_id=0)


def business_start_booking(request):
    service = request.GET.get("service")
    request.session["business_booking_draft"] = {
        "selected_service": service,
        "path_type": "bundle",
        "is_urgent": request.GET.get("urgent") == "1",
    }
    request.session.modified = True
    return redirect("home:business_company_info", booking_id=0)


def _get_business_draft(request):
    return request.session.get("business_booking_draft", {})


def _update_business_draft(request, updates):
    data = _get_business_draft(request)
    data.update(updates)
    request.session["business_booking_draft"] = data
    request.session.modified = True


def _draft_booking_from_session(request):
    data = _get_business_draft(request)
    booking = BusinessBooking()
    booking.id = 0
    for field in (
        "selected_service",
        "company_name",
        "contact_person",
        "role",
        "office_address",
        "email",
        "phone",
        "office_size",
        "num_employees",
        "floors",
        "restrooms",
        "kitchen_cleaning",
        "services_needed",
        "addons",
        "frequency",
        "start_date",
        "preferred_time",
        "days_type",
        "custom_date",
        "custom_time",
        "notes",
        "path_type",
        "is_urgent",
    ):
        if field in data:
            setattr(booking, field, data.get(field))
    bundle_id = data.get("selected_bundle_id")
    if bundle_id:
        booking.selected_bundle_id = bundle_id
    return booking


# ================================
# STEP 1 — COMPANY INFO
# ================================
def business_company_info(request, booking_id):
    draft = _get_business_draft(request)
    if not draft and booking_id != 0:
        request.session["business_booking_draft"] = {}
        request.session.modified = True
        return redirect("home:business_company_info", booking_id=0)

    booking = _draft_booking_from_session(request)

    if booking.path_type not in ["bundle", "custom"]:
        _update_business_draft(request, {"path_type": "bundle"})

    total_steps = 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        form = BusinessCompanyInfoForm(request.POST)
        if form.is_valid():
            _update_business_draft(request, form.cleaned_data)
            return redirect("home:business_office_setup", booking_id=0)
    else:
        form = BusinessCompanyInfoForm(initial=draft)

    return render(request, "home/company_info.html", {
        "booking": booking,
        "form": form,
        "step": 1,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
    })


# ================================
# STEP 2 — OFFICE SETUP
# ================================
def business_office_setup(request, booking_id):
    draft = _get_business_draft(request)
    if not draft and booking_id != 0:
        return redirect("home:business_company_info", booking_id=0)

    booking = _draft_booking_from_session(request)

    total_steps = 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        form = OfficeSetupForm(request.POST)
        if form.is_valid():
            _update_business_draft(request, form.cleaned_data)
            return redirect("home:business_bundles", booking_id=0)
    else:
        form = OfficeSetupForm(initial=draft)

    return render(request, "home/business_office_setup.html", {
        "booking": booking,
        "form": form,
        "step": 2,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
    })


# ================================
# STEP 3 — BUNDLES (BUNDLE PATH)
# ================================
def business_bundles(request, booking_id):
    draft = _get_business_draft(request)
    if not draft and booking_id != 0:
        return redirect("home:business_company_info", booking_id=0)

    booking = _draft_booking_from_session(request)

    _update_business_draft(request, {"path_type": "bundle"})

    total_steps = 7
    range_steps = range(1, total_steps + 1)
    bundles = BusinessBundle.objects.all()

    if request.method == "POST":
        bundle_id = request.POST.get("bundle_id")
        if bundle_id:
            _update_business_draft(request, {"selected_bundle_id": int(bundle_id)})
        return redirect("home:business_frequency", booking_id=0)

    return render(request, "home/business_bundles.html", {
        "booking": booking,
        "bundles": bundles,
        "step": 3,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
    })


# ================================
# STEP 3 CUSTOM — SERVICES NEEDED
# ================================
def business_services_needed(request, booking_id):
    draft = _get_business_draft(request)
    if not draft and booking_id != 0:
        return redirect("home:business_company_info", booking_id=0)

    booking = _draft_booking_from_session(request)

    _update_business_draft(request, {"path_type": "custom"})

    total_steps = 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        selected_services = request.POST.get("selected_services")
        if selected_services:
            _update_business_draft(request, {"services_needed": json.loads(selected_services)})
        return redirect("home:business_addons", booking_id=0)

    return render(request, "home/business_services_needed.html", {
        "booking": booking,
        "services": BusinessService.objects.all(),
        "step": 4,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
    })


# ================================
# STEP 4 — ADDONS (CUSTOM PATH)
# ================================
def business_addons(request, booking_id):
    draft = _get_business_draft(request)
    if not draft and booking_id != 0:
        return redirect("home:business_company_info", booking_id=0)

    booking = _draft_booking_from_session(request)

    total_steps = 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        raw = request.POST.get("selected_addons", "")

        # 🛡 حماية كاملة من الأخطاء
        if not raw.strip():
            selected_addons = []
        else:
            try:
                selected_addons = json.loads(raw)
            except json.JSONDecodeError:
                selected_addons = []

        _update_business_draft(request, {"addons": selected_addons})

        return redirect("home:business_frequency", booking_id=0)

    return render(request, "home/business_addons.html", {
        "booking": booking,
        "addons": BusinessAddon.objects.all(),
        "step": 5,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
    })

# ================================
# STEP 4 OR 5 — FREQUENCY
# ================================
def business_frequency(request, booking_id):
    draft = _get_business_draft(request)
    if not draft and booking_id != 0:
        return redirect("home:business_company_info", booking_id=0)

    booking = _draft_booking_from_session(request)

    if booking.path_type == "bundle":
        step_number = 4
    else:
        step_number = 6

    total_steps = 7

    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        freq_raw = request.POST.get("frequency_data")
        if freq_raw:
            _update_business_draft(request, {"frequency": json.loads(freq_raw)})
        return redirect("home:business_scheduling", booking_id=0)

    return render(request, "home/business_frequency.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
    })


# ================================
# STEP 5 OR 6 — SCHEDULING
# ================================
def business_scheduling(request, booking_id):
    draft = _get_business_draft(request)
    if not draft and booking_id != 0:
        return redirect("home:business_company_info", booking_id=0)

    booking = _draft_booking_from_session(request)

    if booking.path_type == "bundle":
        step_number = 5
    else:
        step_number = 7

    total_steps = 7

    range_steps = range(1, total_steps + 1)

    if request.method == "POST":

        # أخذ البيانات
        start_date = request.POST.get("start_date")
        preferred_time = request.POST.get("preferred_time")

        # التحقق
        if not start_date or not preferred_time:
            return render(request, "home/SchedulingNotes.html", {
                "booking": booking,
                "step": step_number,
                "total_steps": total_steps,
                "range_total_steps": range_steps,
                "error": "Please select a start date and preferred time."
            })

        _update_business_draft(request, {
            "start_date": start_date,
            "preferred_time": preferred_time,
            "days_type": request.POST.get("days_type"),
            "custom_date": request.POST.get("custom_date") or None,
            "custom_time": request.POST.get("custom_time") or None,
            "notes": request.POST.get("notes"),
        })

        draft = _get_business_draft(request)
        created = BusinessBooking(
            selected_service=draft.get("selected_service"),
            company_name=draft.get("company_name"),
            contact_person=draft.get("contact_person"),
            role=draft.get("role"),
            office_address=draft.get("office_address"),
            email=draft.get("email"),
            phone=draft.get("phone"),
            office_size=draft.get("office_size"),
            num_employees=draft.get("num_employees"),
            floors=draft.get("floors"),
            restrooms=draft.get("restrooms"),
            kitchen_cleaning=bool(draft.get("kitchen_cleaning")),
            services_needed=draft.get("services_needed"),
            addons=draft.get("addons"),
            frequency=draft.get("frequency"),
            start_date=draft.get("start_date"),
            preferred_time=draft.get("preferred_time"),
            days_type=draft.get("days_type"),
            custom_date=draft.get("custom_date"),
            custom_time=draft.get("custom_time"),
            notes=draft.get("notes"),
            path_type=draft.get("path_type") or "bundle",
            is_urgent=bool(draft.get("is_urgent")),
            user=request.user if request.user.is_authenticated else None,
        )
        selected_bundle_id = draft.get("selected_bundle_id")
        if selected_bundle_id:
            created.selected_bundle_id = selected_bundle_id

        created.save()
        created.log_status(user=request.user, note="Order placed")
        if created.is_urgent:
            created.log_status(user=request.user, note="Urgent booking (same day) requested")
        request.session.pop("business_booking_draft", None)

        return redirect("home:business_thank_you", booking_id=created.id)

    return render(request, "home/SchedulingNotes.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
    })

# ================================
# STEP 6 OR 7 — THANK YOU
# ================================
def business_thank_you(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    if booking.path_type == "bundle":
        step_number = 6
    else:
        step_number = 7

    total_steps = 7

    range_steps = range(1, total_steps + 1)
    if booking.user is None and request.user.is_authenticated:
        booking.user = request.user
        booking.save()
    return render(request, "home/business_thank_you.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })



# ================================================================================================================
def all_services(request):
    services = PrivateService.objects.all()
    if request.GET.get("urgent") == "1":
        request.session["urgent_booking"] = True
        request.session.modified = True
    return render(request, "home/AllServicesPrivate.html", {"services": services})





AVAILABLE_ZIPS = ["123", "111", "325", "777"]  # مؤقتاً

def private_zip_step1(request, service_slug):
    service = get_object_or_404(PrivateService, slug=service_slug)
    if request.GET.get("urgent") == "1":
        request.session["urgent_booking"] = True
        request.session.modified = True

    zip_form = ZipCheckForm()
    not_available_form = None
    show_not_available = False
    zip_code_value = None

    if request.method == "POST":

        # 1) الضغط على Check Availability
        if "zip-submit" in request.POST:
            zip_form = ZipCheckForm(request.POST)
            if zip_form.is_valid():
                zip_code_value = zip_form.cleaned_data["zip"]

                if zip_code_value in AVAILABLE_ZIPS:

                    # (اختياري) إنشاء booking لاحقاً، مو هون
                    request.session["zip_code"] = zip_code_value

                    return redirect(
                        "home:private_zip_available",
                        service_slug=service.slug
                    )

                else:
                    show_not_available = True
                    not_available_form = NotAvailableZipForm(
                        initial={"zip_code": zip_code_value}
                    )

        # 2) الضغط على Submit تبع الفورم التاني
        elif "contact-submit" in request.POST:
            show_not_available = True
            not_available_form = NotAvailableZipForm(request.POST)
            if not_available_form.is_valid():
                obj = not_available_form.save(commit=False)
                obj.service = service
                obj.save()

                messages.success(
                    request,
                    "Thank you! We'll contact you as soon as we expand to your area."
                )
                return redirect("home:private_zip_step1",
                                service_slug=service_slug)

    if not not_available_form and show_not_available:
        not_available_form = NotAvailableZipForm()

    return render(request, "home/zip code.html", {
        "service": service,
        "zip_form": zip_form,
        "show_not_available": show_not_available,
        "not_available_form": not_available_form,
    })

@login_required
def private_booking_checkout(request, booking_id):
    booking = get_object_or_404(PrivateBooking, id=booking_id)
    services = PrivateService.objects.filter(slug__in=booking.selected_services)

    pricing = calculate_booking_price(booking)
    services_total = Decimal(str(pricing["services_total"]))
    addons_total = Decimal(str(pricing["addons_total"]))
    schedule_extra = Decimal(str(pricing["schedule_extra"]))
    subtotal = Decimal(str(pricing["subtotal"]))
    base_total = Decimal(str(pricing["final"]))
    date_surcharge = Decimal(str(pricing.get("date_surcharge", 0) or 0))
    duration_seconds = int(pricing.get("duration_seconds", 0) or 0)

    rot_value = Decimal(str(pricing.get("rot", 0) or 0))
    rot_percent = pricing.get("rot_percent", 0) or 0
    if rot_value < 0:
        rot_value = Decimal("0.00")
    final_after_rot = base_total

    if booking.subtotal != subtotal or booking.total_price != final_after_rot or booking.rot_discount != rot_value:
        booking.subtotal = subtotal
        booking.total_price = final_after_rot
        booking.rot_discount = rot_value
        booking.save(update_fields=["subtotal", "total_price", "rot_discount"])

    customer = None
    if request.user.is_authenticated:
        customer = Customer.objects.filter(user=request.user).first()

    display_address = None
    if customer:
        display_address = customer.primary_address or customer.full_address
    if not display_address:
        display_address = "Not provided"

    display_area = booking.area
    if not display_area and customer:
        display_area = customer.city
    if not display_area:
        display_area = "Not provided"

    if booking.duration_hours:
        display_duration = booking.duration_hours
    elif duration_seconds > 0:
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        display_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        display_duration = "To be confirmed"

    # ربط المستخدم
    if booking.user is None:
        booking.user = request.user
        booking.save(update_fields=["user"])

    # ==========================
    # 🧮 PREVIEW CALCULATION
    # ==========================
    discount_preview_amount = Decimal("0.00")
    final_preview_price = final_after_rot

    if booking.discount_code:
        is_valid, reason = booking.discount_code.validate(user=request.user)
        if is_valid:
            discount_preview_amount = (
                final_after_rot * Decimal(booking.discount_code.percent) / Decimal(100)
            )
            final_preview_price = final_after_rot - discount_preview_amount
        else:
            booking.discount_code = None
            booking.save(update_fields=["discount_code"])
            messages.warning(request, reason or "Discount code is not valid anymore.")

    # ==========================
    # 📨 POST
    # ==========================
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        # 🎟 APPLY DISCOUNT (Preview only)
        if form_type == "discount":
            code_input = (request.POST.get("discount_code") or "").strip()
            dc = DiscountCode.objects.filter(code__iexact=code_input).first()

            if not dc:
                messages.error(request, "Invalid discount code.")
            else:
                is_valid, reason = dc.validate(user=request.user)
                if not is_valid:
                    messages.error(request, reason)
                else:
                    booking.discount_code = dc
                    booking.save(update_fields=["discount_code"])
                    messages.success(request, "Discount code applied successfully ✅")

            return redirect("home:private_booking_checkout", booking_id=booking.id)

        # 💳 CONFIRM PAYMENT
        elif form_type == "payment":
            booking.payment_method = request.POST.get("payment_method")
            booking.card_number = request.POST.get("card_number")
            booking.card_expiry = request.POST.get("card_expiry")
            booking.card_cvv = request.POST.get("card_cvv")
            booking.card_name = request.POST.get("card_name")
            booking.accepted_terms = True

            fresh_pricing = calculate_booking_price(booking)
            final_amount = Decimal(str(fresh_pricing["final"]))
            discount_amount = Decimal("0.00")

            if booking.discount_code:
                dc = booking.discount_code
                is_valid, reason = dc.validate(user=request.user)
                if not is_valid:
                    messages.error(request, reason or "Discount code is not valid.")
                    return redirect("home:private_booking_checkout", booking_id=booking.id)

                discount_amount = final_amount * Decimal(dc.percent) / Decimal(100)
                final_amount -= discount_amount

                dc.used_count += 1
                if dc.max_uses is not None and dc.used_count >= dc.max_uses:
                    dc.is_used = True
                dc.save(update_fields=["used_count", "is_used"])

                booking.discount_code = None

            booking.total_price = final_amount
            booking.rot_discount = Decimal(str(fresh_pricing.get("rot", 0) or 0))
            booking.subtotal = Decimal(str(fresh_pricing.get("subtotal", 0) or 0))
            booking.save()
            return redirect("home:thank_you_page")

        elif form_type == "remove_discount":
            booking.discount_code = None
            booking.save(update_fields=["discount_code"])
            messages.info(request, "Discount code removed.")
            return redirect("home:private_booking_checkout", booking_id=booking.id)
    return render(request, "home/checkout.html", {
        "booking": booking,
        "services": services,
        "discount_preview_amount": discount_preview_amount,
        "final_preview_price": final_preview_price,
        "pricing": pricing,
        "services_total": services_total,
        "addons_total": addons_total,
        "schedule_extra": schedule_extra,
        "date_surcharge": date_surcharge,
        "subtotal": subtotal,
        "base_total": base_total,
        "rot_value": rot_value,
        "display_address": display_address,
        "display_area": display_area,
        "display_duration": display_duration,
        "rot_percent": rot_percent,
    })

def private_zip_available(request, service_slug):
    service = get_object_or_404(PrivateService, slug=service_slug)

    call_success = False
    email_success = False

    # معالجة طلب المكالمة
    if request.method == "POST" and request.POST.get("form_type") == "call_request":
        CallRequest.objects.create(
            full_name=request.POST.get("name", ""),
            phone=request.POST.get("phone", ""),
            email=request.POST.get("email", ""),
            preferred_time=request.POST.get("preferred_time", None),
            message=request.POST.get("message", ""),
            language=request.POST.get("language", ""),
        )
        call_success = True

    # معالجة إرسال الإيميل
    if request.method == "POST" and request.POST.get("form_type") == "email_request":
        EmailRequest.objects.create(
            email_from=request.POST.get("email_from", ""),
            subject=request.POST.get("subject", ""),
            message=request.POST.get("message", ""),
            attachment=request.FILES.get("attachment")
        )
        email_success = True

    return render(request, "home/good_zip.html", {
        "service": service,
        "service_slug": service_slug,
        "call_success": call_success,
        "email_success": email_success,
    })

def private_thank_you(request):
    return render(request, "home/thank_you_page.html")

def submit_call_request(request):
    if request.method == "POST":
        form = CallRequestForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True})

        return JsonResponse({"success": False, "errors": form.errors})

    return JsonResponse({"success": False, "error": "Invalid request"})



def private_booking_start(request, service_slug):
    """
    بيتندّه لما نعمل Book Online من صفحة الـ ZIP.
    بينشئ PrivateBooking جديد ويربطه بالخدمة اللي بلش منها.
    """
    service = get_object_or_404(PrivateService, slug=service_slug)

    urgent_flag = request.GET.get("urgent") == "1" or request.session.get("urgent_booking")

    booking = PrivateBooking.objects.create(
        booking_method="online",
        main_category=service.category.slug,
        selected_services=[service.slug],
        user=request.user if request.user.is_authenticated else None,
        is_urgent=bool(urgent_flag),
    )

    if urgent_flag:
        booking.log_status(note="Urgent booking (same day) requested")
        request.session.pop("urgent_booking", None)
    return redirect("home:private_booking_services", booking_id=booking.id)

def private_booking_services(request, booking_id):
    booking = get_object_or_404(PrivateBooking, id=booking_id)

    selected_slugs = booking.selected_services or []
    if not selected_slugs:
        return redirect("home:all_services_private")

    services = (
        PrivateService.objects
        .filter(slug__in=selected_slugs)
        .select_related("category")
        .prefetch_related("addons_list")
    )

    if request.method == "POST":
        # 1) جمع إجابات الأسئلة
        service_answers = booking.service_answers or {}

        for service in services:
            s_key = service.slug
            service_answers.setdefault(s_key, {})

            if service.questions:
                for q_key, q_info in service.questions.items():
                    field_name = f"{s_key}__{q_key}"
                    q_type = (q_info or {}).get("type")
                    if q_type in ("multiselect", "checkbox"):
                        service_answers[s_key][q_key] = request.POST.getlist(field_name)
                    else:
                        service_answers[s_key][q_key] = request.POST.get(field_name, "")

        booking.service_answers = service_answers

        # 2) الـ Add-ons
        addons_json = request.POST.get("addons_selected") or "{}"

        try:
            raw_addons = json.loads(addons_json)
        except:
            raw_addons = {}

        # Server-side validation: all service questions required
        missing = []
        for service in services:
            s_key = service.slug
            if not service.questions:
                continue
            for q_key, q_info in service.questions.items():
                q_type = (q_info or {}).get("type")
                answer = service_answers.get(s_key, {}).get(q_key)
                if q_type in ("multiselect", "checkbox"):
                    if not answer:
                        missing.append(f"{s_key}__{q_key}")
                else:
                    if not answer:
                        missing.append(f"{s_key}__{q_key}")

        if missing:
            messages.error(request, "Please answer all required service questions before continuing.")
            pricing = calculate_booking_price(booking)
            return render(request, "home/YourServicesBooking.html", {
                "booking": booking,
                "services": services,
                "saved_addons": json.dumps(raw_addons or {}),
                "pricing": pricing,
            })


        final_addons = {}

        for service_slug, addons in raw_addons.items():
            final_addons[service_slug] = {}

            for addon_slug, addon_data in addons.items():

                # 1) جبنا الإضافة من الداتا بيز
                try:
                    addon_obj = PrivateAddon.objects.get(slug=addon_slug)
                except PrivateAddon.DoesNotExist:
                    continue

                quantity = int(addon_data.get("quantity", 1))

                # 2) حساب السعر
                if addon_obj.price_per_unit:
                    total_price = quantity * addon_obj.price_per_unit + addon_obj.price
                    print(1)
                else:
                    total_price = quantity * addon_obj.price_per_unit + addon_obj.price
                    print(total_price)

                # 3) نحفظ الشكل الصحيح
                final_addons[service_slug][addon_slug] = {
                    "title": addon_obj.title,
                    "quantity": quantity,
                    "unit_price": float(addon_obj.price_per_unit or addon_obj.price),
                    "price": float(total_price),
                }

        booking.addons_selected = final_addons


        # ⭐⭐⭐ 2.5) تخزين الـ schedule لو وصل من الصفحة ⭐⭐⭐
        schedules_json = request.POST.get("schedules_json")
        if schedules_json:
            try:
                booking.service_schedules = json.loads(schedules_json)
            except:
                booking.service_schedules = {}

        # 3) حساب السعر
        pricing = calculate_booking_price(booking)

        booking.pricing_details = pricing
        booking.subtotal = Decimal(str(pricing["subtotal"]))
        booking.rot_discount = Decimal(str(pricing["rot"]))
        booking.total_price = Decimal(str(pricing["final"]))
        booking.save()

        # لو الطلب AJAX → رجّع JSON
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            from django.http import JsonResponse
            return JsonResponse(pricing)

        return redirect("home:private_booking_schedule", booking_id=booking.id)

    # GET
    pricing = calculate_booking_price(booking)
    return render(request, "home/YourServicesBooking.html", {
        "booking": booking,
        "services": services,
        "saved_addons": json.dumps(booking.addons_selected or {}),
        "pricing": pricing,
    })

def private_cart_continue(request):
    cart = request.session.get("private_cart", [])

    if not cart:
        return redirect("home:all_services_private")

    # نختار أول خدمة لتحديد مسار الـ ZIP
    first_service_slug = cart[0]

    return redirect(
        "home:private_zip_step1",
        service_slug=first_service_slug
    )



def private_cart(request):
    cart = request.session.get("private_cart", [])

    services = PrivateService.objects.filter(slug__in=cart)

    return render(request, "home/PrivateCart.html", {
        "services": services,
        "cart": cart,
    })


def private_cart_remove_json(request, service_slug):
    cart = request.session.get("private_cart", [])

    if service_slug in cart:
        cart.remove(service_slug)

    request.session["private_cart"] = cart
    request.session.modified = True

    return JsonResponse({
        "success": True,
        "count": len(cart)
    })

def private_cart_add(request, slug):
    cart = request.session.get("private_cart", [])

    if slug not in cart:
        cart.append(slug)

    request.session["private_cart"] = cart
    request.session.modified = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "ok",
            "count": len(cart)
        })

    return redirect("home:private_cart")


def private_cart_count(request):
    cart = request.session.get("private_cart", [])
    return JsonResponse({"count": len(cart)})

def private_booking_schedule(request, booking_id):
    booking = get_object_or_404(PrivateBooking, id=booking_id)

    if not booking.selected_services:
        cart = request.session.get("private_cart", [])
        if cart:
            booking.selected_services = cart
            booking.save(update_fields=["selected_services"])

    services = PrivateService.objects.filter(slug__in=booking.selected_services)

    # -----------------------------
    # 1) تجهيز قوانين الزيادة للـ JS
    # -----------------------------
    raw_rules = list(DateSurcharge.objects.values(
        "rule_type", "weekday", "date", "surcharge_type", "amount"
    ))
    date_rules_json = json.dumps(raw_rules, cls=DjangoJSONEncoder)
    schedule_rules_json = json.dumps(
        list(ScheduleRule.objects.values("key", "value", "price_change")),
        cls=DjangoJSONEncoder,
    )

    # -----------------------------
    # 2) POST – تخزين البيانات
    # -----------------------------
    if request.method == "POST":
        print(1)
        # MODE
        mode = request.POST.get("schedule_mode")
        booking.schedule_mode = mode

        # ---------------- SAME MODE ----------------
        if mode == "same":
            print(2)
            # تاريخ
            date = request.POST.get("appointment_date")
            booking.appointment_date = date if date else None
            print(booking.appointment_date)
            # وقت
            time_window = request.POST.get("appointment_time_window")
            booking.appointment_time_window = time_window
            print(booking.appointment_time_window)
            # Frequency
            frequency = request.POST.get("frequency_type")
            booking.frequency_type = frequency
            print(booking.frequency_type)
            # أيام العمل
            days_json = request.POST.get("day_work_best")
            booking.day_work_best = json.loads(days_json) if days_json else []
            print(booking.day_work_best)
            # Special timing
            special = request.POST.get("special_timing_requests")
            booking.special_timing_requests = special
            
            # End Date
            end_date = request.POST.get("End_Date")
            booking.End_Date = end_date if end_date else None

            # تفريغ الجدول المنفصل
            booking.service_schedules = {}

        # ---------------- PER SERVICE MODE ----------------
        elif mode == "per_service":
            schedules_json = request.POST.get("schedules_json")
            print(3)
            if schedules_json:
                try:
                    schedules = json.loads(schedules_json)
                except:
                    schedules = {}
            else:
                schedules = {}

            booking.service_schedules = schedules

            # تفريغ قيم المود "same"
            booking.appointment_date = None
            booking.appointment_time_window = None
            booking.frequency_type = None
            booking.day_work_best = []
            booking.special_timing_requests = None
            booking.End_Date = None

        # -----------------------------
        # 3) إعادة حساب السعر
        # -----------------------------
        pricing = calculate_booking_price(booking)
        booking.pricing_details = pricing
        booking.total_price = pricing["final"]
        booking.subtotal = pricing["subtotal"]
        booking.rot_discount = pricing["rot"]

        booking.save()

        return redirect("home:private_booking_checkout" , booking_id=booking.id)

    # -----------------------------
    # 3) Render
    # -----------------------------
    print(4)
    return render(request, "home/Private_scheduale.html", {
        "booking": booking,
        "services": services,
        "date_rules": date_rules_json,
        "schedule_rules": schedule_rules_json,
        "pricing": calculate_booking_price(booking),
    })


def private_price_api(request, booking_id):

    booking = get_object_or_404(PrivateBooking, id=booking_id)

    if not booking.selected_services:
        cart = request.session.get("private_cart", [])
        if cart:
            booking.selected_services = cart
            booking.save(update_fields=["selected_services"])

    # --------------------------
    # 1) جدولة: same أو per_service
    # --------------------------
    mode = request.GET.get("mode")
    if mode:
        booking.schedule_mode = mode

    # --------------------------
    # 2) SAME MODE INPUTS
    # --------------------------
    date = request.GET.get("date")
    if date:
        booking.appointment_date = date

    tw = request.GET.get("time_window")
    if tw:
        booking.appointment_time_window = tw

    freq = request.GET.get("frequency")
    if freq:
        booking.frequency_type = freq

    days = request.GET.get("days")
    days_list = None
    if days:
        try:
            days_list = json.loads(days)
            booking.day_work_best = days_list
        except:
            booking.day_work_best = []

    # --------------------------
    # 3) PER-SERVICE MODE INPUTS
    # --------------------------
    schedule_json = request.GET.get("schedules_json")
    if schedule_json:
        try:
            booking.service_schedules = json.loads(schedule_json)
        except:
            booking.service_schedules = {}

    # IMPORTANT: ما منعمل save() حتى لا نخرب الخطوات
    # نحسب مباشرة
    # ----- NEW: قراءة weekday القادمة من التقويم -----
    weekday = request.GET.get("weekday")
    if (days_list is None or days_list == []) and weekday:
        try:
            booking.day_work_best = json.loads(weekday)
        except:
            booking.day_work_best = []
    # -----------------------------------------------

    pricing = calculate_booking_price(booking)

    return JsonResponse({
        "services_total": pricing["services_total"],
        "addons_total": pricing["addons_total"],
        "subtotal": pricing["subtotal"],
        "schedule_extra": pricing["schedule_extra"],
        "rot": pricing["rot"],
        "final": pricing["final"],
        "duration_hours": pricing.get("duration_hours", 0),
        "duration_seconds": pricing.get("duration_seconds", 0),
    })


@csrf_exempt
def private_update_answer_api(request, booking_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    booking = get_object_or_404(PrivateBooking, id=booking_id)

    field = request.POST.get("field")
    value = request.POST.get("value")
    service_slug = request.POST.get("service")

    if not field or not service_slug:
        return JsonResponse({"error": "Missing data"}, status=400)

    parsed_value = value
    if value:
        trimmed = value.strip()
        if trimmed.startswith("[") or trimmed.startswith("{"):
            try:
                parsed_value = json.loads(trimmed)
            except json.JSONDecodeError:
                parsed_value = value

    answers = booking.service_answers or {}
    answers.setdefault(service_slug, {})
    answers[service_slug][field] = parsed_value

    booking.service_answers = answers
    pricing = calculate_booking_price(booking)
    duration_seconds = int(pricing.get("duration_seconds", 0) or 0)
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    booking.duration_hours = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    booking.save(update_fields=["service_answers", "duration_hours"])

    return JsonResponse({"success": True})



@csrf_exempt
def private_update_addons_api(request, booking_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    booking = get_object_or_404(PrivateBooking, id=booking_id)

    raw = request.POST.get("addons_json", "{}")

    try:
        addons = json.loads(raw)
    except:
        addons = {}

    booking.addons_selected = addons
    pricing = calculate_booking_price(booking)
    duration_seconds = int(pricing.get("duration_seconds", 0) or 0)
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    booking.duration_hours = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    booking.subtotal = pricing.get("subtotal", 0) or 0
    booking.total_price = pricing.get("final", 0) or 0
    booking.rot_discount = pricing.get("rot", 0) or 0
    booking.pricing_details = pricing
    booking.save(update_fields=["addons_selected", "duration_hours", "subtotal", "total_price", "rot_discount", "pricing_details"])

    return JsonResponse({
        "success": True,
        "pricing": {
            "services_total": pricing.get("services_total", 0),
            "addons_total": pricing.get("addons_total", 0),
            "subtotal": pricing.get("subtotal", 0),
            "rot": pricing.get("rot", 0),
            "final": pricing.get("final", 0),
            "duration_seconds": pricing.get("duration_seconds", 0),
        },
    })



@require_POST
def add_booking_note(request):
    booking_type = request.POST.get("booking_type")
    booking_id = request.POST.get("booking_id")
    text = request.POST.get("text", "").strip()

    if not text:
        return JsonResponse({"error": "Empty note"}, status=400)

    if booking_type == "private":
        booking = PrivateBooking.objects.get(id=booking_id)
        note = BookingNote.objects.create(
            private_booking=booking,
            text=text
        )

    elif booking_type == "business":
        booking = BusinessBooking.objects.get(id=booking_id)
        note = BookingNote.objects.create(
            business_booking=booking,
            text=text
        )
    else:
        return JsonResponse({"error": "Invalid type"}, status=400)

    return JsonResponse({
        "id": note.id,
        "text": note.text,
        "created_at": note.created_at.strftime("%Y-%m-%d %H:%M")
    })
