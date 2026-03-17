from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_date
import logging
from datetime import timedelta
import re
import stripe

from accounts.models import DiscountCode
from .pricing_utils import calculate_booking_price
from django.shortcuts import render, redirect, get_object_or_404
from .forms import (
    ContactForm, ApplicationForm, BusinessCompanyInfoForm, OfficeSetupForm , ZipCheckForm, NotAvailableZipForm,CallRequestForm, FeedbackRequestForm
)
from django.views.decorators.http import require_POST
from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse

from .models import (
    BaseBooking, Job, Application, BookingNote, BusinessBooking, BusinessService, BusinessServiceCard, DateSurcharge, PrivateAddon,
    BusinessBundle, BusinessAddon, PrivateService, AvailableZipCode, PrivateBooking, PrivateBookingDraft, CallRequest,
    EmailRequest, PrivateMainCategory, FeedbackRequest, NoShowReport, BookingStatusHistory,
    Contact, FAQCategory, FAQItem, StripeWebhookEvent,
    ScheduleRule,
)
from accounts.models import (
    Customer,
    BookingRequestFix,
    CustomerNotification,
    CustomerNote,
    Incident,
    Invoice,
    PaymentMethod,
    ServiceReview,
    ProviderProfile,
    ProviderAdminMessage,
    ChatMessage,
)
from django.http import JsonResponse, HttpResponse
import json
from django.contrib import messages
import json
from datetime import datetime  # فوق
from .pricing_utils import calculate_booking_price
from .availability_utils import (
    generate_slots,
    select_nearest_provider,
    provider_available_after_minutes,
)
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash, get_user_model
from django import forms
from django.forms import modelform_factory
from django.db.models import Q, JSONField, Prefetch
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe

from .dashboard import get_dashboard_items, get_item_by_slug

logger = logging.getLogger(__name__)
User = get_user_model()

DRAFT_SESSION_KEY = "private_booking_draft"


def _get_private_draft_data(request):
    data = request.session.get(DRAFT_SESSION_KEY)
    if not isinstance(data, dict):
        data = {}
    return data


def _save_private_draft_data(request, data):
    request.session[DRAFT_SESSION_KEY] = data
    request.session.modified = True


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_optional_date(value):
    if not value:
        return None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    return parse_date(str(value))


def _date_is_before_today(value):
    if not value:
        return False
    return value < timezone.localdate()


def _get_private_booking_customer_snapshot(customer):
    if customer is None:
        return {}
    return {
        "address": customer.display_address(),
        "area": customer.display_city(),
        "zip_code": customer.display_postal_code(),
    }


def _build_private_booking_from_draft(draft, user=None):
    booking = PrivateBooking()
    draft_user_id = draft.get("user_id")
    if user and user.is_authenticated:
        booking.user = user
    elif draft_user_id:
        booking.user_id = draft_user_id

    customer = Customer.objects.filter(user_id=booking.user_id).first() if booking.user_id else None
    customer_snapshot = _get_private_booking_customer_snapshot(customer)

    booking.booking_method = draft.get("booking_method")
    booking.main_category = draft.get("main_category")
    booking.selected_services = draft.get("selected_services") or []
    booking.service_answers = draft.get("service_answers") or {}
    booking.addons_selected = draft.get("addons_selected") or {}
    booking.service_schedules = draft.get("service_schedules") or {}
    booking.schedule_mode = draft.get("schedule_mode") or "same"
    booking.appointment_date = _parse_optional_date(draft.get("appointment_date"))
    booking.appointment_time_window = draft.get("appointment_time_window")
    booking.frequency_type = draft.get("frequency_type")
    booking.special_timing_requests = draft.get("special_timing_requests")
    booking.day_work_best = draft.get("day_work_best") or []
    booking.End_Date = _parse_optional_date(draft.get("End_Date"))
    booking.pricing_details = draft.get("pricing_details")
    booking.total_price = Decimal(str(draft.get("total_price", 0) or 0))
    booking.subtotal = Decimal(str(draft.get("subtotal", 0) or 0))
    booking.rot_discount = Decimal(str(draft.get("rot_discount", 0) or 0))
    booking.address = draft.get("address") or customer_snapshot.get("address")
    booking.area = draft.get("area") or customer_snapshot.get("area")
    booking.duration_hours = draft.get("duration_hours")
    booking.quoted_duration_minutes = draft.get("quoted_duration_minutes") or 0
    booking.is_urgent = bool(draft.get("is_urgent"))
    booking.zip_code = draft.get("zip_code") or customer_snapshot.get("zip_code")
    booking.zip_is_available = bool(draft.get("zip_is_available"))
    booking.scheduled_at = _parse_iso_datetime(draft.get("scheduled_at"))
    return booking


def _stripe_amount_from_decimal(amount):
    if amount is None:
        return 0
    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((quantized * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _stripe_minimum_amount_cents(currency):
    minimums = {
        "sek": 300,
    }
    return minimums.get((currency or "").lower(), 0)


def _card_details_from_intent(intent):
    brand = None
    last4 = None
    charges = intent.get("charges", {}) if isinstance(intent, dict) else {}
    data = charges.get("data", []) if isinstance(charges, dict) else []
    if data:
        details = data[0].get("payment_method_details", {})
        card = details.get("card", {})
        brand = card.get("brand")
        last4 = card.get("last4")
    if not brand or not last4:
        payment_method = intent.get("payment_method")
        if isinstance(payment_method, dict):
            card = payment_method.get("card", {})
            brand = brand or card.get("brand")
            last4 = last4 or card.get("last4")
    return brand, last4


def _get_or_create_checkout_stripe_customer(customer):
    if customer is None:
        return None

    stripe_customer_id = (getattr(customer, "stripe_customer_id", None) or "").strip()
    if stripe_customer_id:
        try:
            stripe_customer = stripe.Customer.retrieve(stripe_customer_id)
            if not getattr(stripe_customer, "deleted", False):
                return stripe_customer_id
        except Exception:
            logger.warning("Stored Stripe customer is invalid for customer %s", customer.id, exc_info=True)
        customer.stripe_customer_id = None
        customer.save(update_fields=["stripe_customer_id"])

    stripe_customer = stripe.Customer.create(
        email=customer.email or None,
        name=f"{customer.first_name} {customer.last_name}".strip() or None,
        metadata={
            "app_customer_id": str(customer.id),
            "user_id": str(customer.user_id),
        },
    )
    customer.stripe_customer_id = stripe_customer.id
    customer.save(update_fields=["stripe_customer_id"])
    return stripe_customer.id


def _serialize_private_payment_summary(summary):
    return {
        "amount": f"{summary['amount']:.2f}",
        "amount_cents": summary["amount_cents"],
        "currency": summary["currency"],
    }


def _calculate_private_payment_summary(booking, currency):
    fresh_pricing = calculate_booking_price(booking)
    base_total = Decimal(str(fresh_pricing.get("final", 0) or 0))
    subtotal = Decimal(str(fresh_pricing.get("subtotal", 0) or 0))
    rot_discount = Decimal(str(fresh_pricing.get("rot", 0) or 0))

    customer = None
    if booking.user_id:
        customer = Customer.objects.filter(user_id=booking.user_id).first()

    completed_bookings = 0
    if booking.user_id:
        completed_bookings = (
            PrivateBooking.objects.filter(user_id=booking.user_id, status="COMPLETED").count()
            + BusinessBooking.objects.filter(user_id=booking.user_id, status="COMPLETED").count()
        )

    referral_discount_percent = 10
    referral_discount_eligible = (
        customer is not None
        and customer.has_referral_discount
        and completed_bookings == 0
    )

    final_amount = base_total
    discount_code = None
    referral_discount_applied = False

    if booking.discount_code:
        dc = booking.discount_code
        is_valid, _ = dc.validate(user=booking.user)
        if is_valid:
            discount_amount = base_total * Decimal(dc.percent) / Decimal(100)
            final_amount = base_total - discount_amount
            discount_code = dc

    if referral_discount_eligible and discount_code is None:
        referral_discount_amount = base_total * Decimal(referral_discount_percent) / Decimal(100)
        final_amount = base_total - referral_discount_amount
        referral_discount_applied = True

    final_amount = final_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "pricing": fresh_pricing,
        "base_total": base_total,
        "subtotal": subtotal,
        "rot_discount": rot_discount,
        "amount": final_amount,
        "amount_cents": _stripe_amount_from_decimal(final_amount),
        "currency": (currency or "").lower(),
        "discount_code": discount_code,
        "referral_discount_applied": referral_discount_applied,
        "customer": customer,
    }


def _payment_intent_metadata_matches(intent, draft_record, user_id=None):
    metadata = getattr(intent, "metadata", None) or {}
    if str(metadata.get("booking_type") or "") != "private":
        return False
    if str(metadata.get("draft_id") or "") != str(draft_record.id):
        return False
    if user_id is not None and str(metadata.get("user_id") or "") != str(user_id):
        return False
    return True


def _verify_private_payment_intent(intent, draft_record, summary, require_user_id=None):
    if intent.status != "succeeded":
        return False, "Payment not completed."

    received_amount = intent.get("amount_received") or intent.get("amount") or 0
    if int(received_amount) != int(summary["amount_cents"]):
        return False, "Payment amount mismatch."

    intent_currency = (intent.get("currency") or "").lower()
    if intent_currency != summary["currency"]:
        return False, "Payment currency mismatch."

    if not _payment_intent_metadata_matches(intent, draft_record, user_id=require_user_id):
        return False, "Payment metadata mismatch."

    return True, None


def _apply_private_booking_payment(booking, intent, payment_summary=None):
    if booking.payment_status == "succeeded":
        return

    payment_summary = payment_summary or _calculate_private_payment_summary(
        booking,
        (intent.get("currency") or settings.STRIPE_CURRENCY or "usd").lower(),
    )

    if payment_summary["discount_code"] is not None:
        dc = payment_summary["discount_code"]
        dc.used_count += 1
        if dc.max_uses is not None and dc.used_count >= dc.max_uses:
            dc.is_used = True
        dc.save(update_fields=["used_count", "is_used"])
        booking.discount_code = None

    customer = payment_summary["customer"]
    if payment_summary["referral_discount_applied"] and customer and customer.has_referral_discount:
        customer.has_referral_discount = False
        customer.save(update_fields=["has_referral_discount"])

    brand, last4 = _card_details_from_intent(intent)
    booking.payment_method = "card"
    booking.payment_status = intent.get("status")
    booking.payment_intent_id = intent.get("id")
    booking.payment_amount = payment_summary["amount"]
    booking.payment_currency = payment_summary["currency"] or None
    booking.payment_brand = brand
    booking.payment_last4 = last4
    booking.accepted_terms = True
    booking.total_price = payment_summary["amount"]
    booking.subtotal = payment_summary["subtotal"]
    booking.rot_discount = payment_summary["rot_discount"]
    booking.save()


def _sync_private_booking_invoice(booking, intent, payment_summary=None):
    if booking is None or not booking.user_id:
        return

    customer = Customer.objects.filter(user_id=booking.user_id).first()
    if customer is None:
        return

    payment_summary = payment_summary or {
        "amount": booking.payment_amount or booking.total_price or Decimal("0.00"),
        "currency": booking.payment_currency or settings.STRIPE_CURRENCY or "usd",
    }

    payment_method = None
    raw_payment_method = intent.get("payment_method")
    stripe_payment_method_id = ""
    if isinstance(raw_payment_method, dict):
        stripe_payment_method_id = (raw_payment_method.get("id") or "").strip()
    elif raw_payment_method:
        stripe_payment_method_id = str(raw_payment_method).strip()

    if stripe_payment_method_id:
        payment_method = PaymentMethod.objects.filter(
            customer=customer,
            stripe_payment_method_id=stripe_payment_method_id,
        ).first()

    if payment_method is None and booking.payment_last4 and booking.payment_brand:
        payment_method = PaymentMethod.objects.filter(
            customer=customer,
            card_last4=booking.payment_last4,
            card_type=(booking.payment_brand or "").lower(),
        ).order_by("-is_default", "-created_at").first()

    Invoice.objects.update_or_create(
        customer=customer,
        booking_type="private",
        booking_id=booking.id,
        defaults={
            "amount": payment_summary["amount"],
            "currency": str(payment_summary.get("currency") or "usd").upper(),
            "status": "PAID" if intent.get("status") == "succeeded" else "PENDING",
            "payment_method": payment_method,
            "paid_at": timezone.now() if intent.get("status") == "succeeded" else None,
            "note": f"Stripe PaymentIntent {intent.get('id') or ''}".strip(),
        },
    )


def _create_private_booking_from_draft_payload(payload):
    booking = _build_private_booking_from_draft(payload)
    booking.accepted_terms = True
    scheduled_at = _parse_iso_datetime(payload.get("scheduled_at"))
    if scheduled_at:
        booking.scheduled_at = scheduled_at

    user_id = payload.get("user_id")
    if user_id:
        booking.user_id = user_id

    discount_code_id = payload.get("discount_code_id")
    if discount_code_id:
        booking.discount_code_id = discount_code_id

    booking.save()
    return booking


def _mark_private_draft_failed(draft_record, status_value, error_message=None):
    update_fields = ["payment_status", "status"]
    draft_record.payment_status = status_value
    draft_record.status = "failed"
    if error_message:
        logger.error(
            "Private booking draft %s marked failed: %s",
            draft_record.id,
            error_message,
        )
    draft_record.save(update_fields=update_fields)


def _normalize_location(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _booking_location_candidates(booking):
    if not booking:
        return []
    values = []
    if hasattr(booking, "area") and booking.area:
        values.append(booking.area)
    if hasattr(booking, "address") and booking.address:
        values.append(booking.address)
    if hasattr(booking, "office_address") and booking.office_address:
        values.append(booking.office_address)
    return [_normalize_location(v) for v in values if v]


def _provider_matches_location(provider_profile, booking_locations):
    if not booking_locations:
        return True
    if not provider_profile:
        return False
    provider_values = [
        provider_profile.area,
        provider_profile.city,
        provider_profile.region,
    ] + (provider_profile.nearby_areas or [])
    provider_values = [_normalize_location(v) for v in provider_values if v]
    if not provider_values:
        return False
    for booking_loc in booking_locations:
        for provider_loc in provider_values:
            if not booking_loc or not provider_loc:
                continue
            if booking_loc == provider_loc:
                return True
            if booking_loc in provider_loc or provider_loc in booking_loc:
                return True
    return False


def _filtered_provider_queryset(booking):
    providers = (
        User.objects.filter(provider_profile__is_active=True)
        .select_related("provider_profile")
        .order_by("username")
    )
    if not booking:
        return providers

    booking_locations = _booking_location_candidates(booking)
    allowed_ids = []
    for provider in providers:
        profile = getattr(provider, "provider_profile", None)
        if not profile:
            continue
        if not booking.provider_is_available(provider):
            continue
        allowed_ids.append(provider.id)

    if booking.provider_id and booking.provider_id not in allowed_ids:
        allowed_ids.append(booking.provider_id)

    return User.objects.filter(id__in=allowed_ids).order_by("username")


def _provider_debug_payload(booking):
    booking_locations = _booking_location_candidates(booking)
    providers = (
        User.objects.filter(provider_profile__isnull=False)
        .select_related("provider_profile")
        .order_by("username")
    )
    rows = []
    for provider in providers:
        reasons = []
        profile = getattr(provider, "provider_profile", None)
        if not profile:
            reasons.append("No provider profile")
        else:
            if not profile.is_active:
                reasons.append("Profile inactive")
            if booking_locations and not _provider_matches_location(profile, booking_locations):
                reasons.append("Location differs")
        if profile and booking and not booking.provider_is_available(provider):
            reasons.append("Overlapping booking")

        blocking_reasons = [reason for reason in reasons if reason in {"No provider profile", "Profile inactive", "Overlapping booking"}]
        status = "Included" if not blocking_reasons else "Excluded"
        rows.append({
            "username": provider.get_full_name() or provider.username,
            "reasons": reasons,
            "status": status,
        })
    return {
        "booking_locations": booking_locations,
        "providers": rows,
    }

# ================================
# STATIC PAGES
# ================================
def home(request):
    feedbacks = list(FeedbackRequest.objects.order_by("-created_at"))
    return render(request, "home/home.html", {"feedbacks": feedbacks})

def about(request):
    return render(request, "home/about.html")

def faq(request):
    categories = (
        FAQCategory.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch("items", queryset=FAQItem.objects.filter(is_active=True))
        )
    )
    return render(request, "home/FAQ.html", {"faq_categories": categories})

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
        BookingRequestFix.objects.filter(created_at__gte=since).exclude(status="OPEN")
        .order_by("-created_at")[:6]
    )
    recent_open_fixes = list(
        BookingRequestFix.objects.filter(status="OPEN")
        .order_by("-created_at")[:6]
    )
    recent_pending_no_show = list(
        NoShowReport.objects.filter(decision="PENDING")
        .select_related("provider")
        .order_by("-created_at")[:6]
    )
    recent_contacts = list(
        Contact.objects.filter(created_at__gte=since)
        .order_by("-created_at")[:6]
    )
    recent_customers = list(
        Customer.objects.filter(user__date_joined__gte=since)
        .select_related("user")
        .order_by("-user__date_joined")[:6]
    )
    recent_providers = list(
        ProviderProfile.objects.filter(user__date_joined__gte=since)
        .select_related("user")
        .order_by("-user__date_joined")[:6]
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
    for fix in recent_open_fixes:
        items.append({
            "title": f"Open Request Fix #{fix.id}",
            "detail": f"{fix.booking_type.title()} booking #{fix.booking_id}",
            "time": fix.created_at,
            "url": "/dashboard/request-fixes/",
        })
    for report in recent_pending_no_show:
        provider_name = str(report.provider) if report.provider_id else "Unknown provider"
        items.append({
            "title": f"Pending No-Show #{report.id}",
            "detail": f"{report.booking_type.title()} booking #{report.booking_id} - {provider_name}",
            "time": report.created_at,
            "url": "/dashboard/no-show-reports/",
        })
    for contact in recent_contacts:
        items.append({
            "title": f"Contact: {contact.first_name} {contact.last_name}".strip(),
            "detail": contact.inquiry_type or "Contact form",
            "time": contact.created_at,
            "url": "/dashboard/contacts/",
        })
    for customer in recent_customers:
        customer_name = f"{customer.first_name} {customer.last_name}".strip() or customer.email or str(customer)
        items.append({
            "title": "New Customer",
            "detail": customer_name,
            "time": customer.user.date_joined,
            "url": "/dashboard/customers/",
        })
    for provider in recent_providers:
        provider_name = getattr(provider.user, "username", "") or str(provider.user)
        items.append({
            "title": "New Provider Signup",
            "detail": provider_name,
            "time": provider.user.date_joined,
            "url": "/dashboard/provider-profiles/",
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


def _dashboard_booking_url(booking_type, booking_id):
    if booking_type == "business":
        return f"/dashboard/business-bookings/{booking_id}/edit/"
    return f"/dashboard/private-bookings/{booking_id}/edit/"


def _dashboard_get_booking_instance(booking_type, booking_id):
    if booking_type == "business":
        return get_object_or_404(BusinessBooking, pk=booking_id)
    return get_object_or_404(PrivateBooking, pk=booking_id)


def _dashboard_async_response(request, ok, message, status=200):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": ok, "message": message}, status=status)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("home:dashboard_home")


def _dashboard_uses_view_mode(item):
    return item.slug in {
        "contacts",
        "feedback",
        "applications",
        "private-bookings",
        "business-bookings",
        "call-requests",
        "email-requests",
        "request-fixes",
        "customer-notifications",
        "service-reviews",
        "service-comments",
        "customer-notes",
        "incidents",
    }


def _dashboard_booking_customer_label(booking):
    if isinstance(booking, BusinessBooking):
        return booking.company_name or booking.contact_person or booking.email or f"Business #{booking.id}"
    user = getattr(booking, "user", None)
    if user:
        full_name = user.get_full_name().strip()
        if full_name:
            return full_name
        if user.email:
            return user.email
        return user.username
    return f"Private #{booking.id}"


def _dashboard_booking_service_label(booking):
    if isinstance(booking, BusinessBooking):
        return booking.selected_service or booking.selected_bundle or "Business service"
    selected = booking.selected_services or []
    if isinstance(selected, list) and selected:
        return ", ".join(str(value) for value in selected[:2])
    return booking.main_category or "Private service"


def _dashboard_booking_when(booking):
    start_dt, _ = booking.get_service_window()
    if start_dt:
        return timezone.localtime(start_dt).strftime("%b %d, %I:%M %p")
    if isinstance(booking, PrivateBooking) and booking.appointment_date:
        return f"{booking.appointment_date:%b %d, %Y} {booking.appointment_time_window or ''}".strip()
    if isinstance(booking, BusinessBooking):
        raw_date = booking.custom_date or booking.start_date
        raw_time = booking.custom_time or booking.preferred_time or ""
        if raw_date:
            return f"{raw_date:%b %d, %Y} {raw_time}".strip()
    return "Time not set"


def _dashboard_booking_priority(booking, now):
    start_dt, _ = booking.get_service_window()
    overdue = bool(start_dt and start_dt < now and booking.status not in BaseBooking.INACTIVE_STATUSES)
    if overdue:
        return "high"
    if booking.is_urgent:
        return "high"
    if booking.provider_id is None:
        return "medium"
    return "normal"


def _dashboard_action_center(now):
    active_statuses = ["ORDERED", "SCHEDULED", "ASSIGNED", "ON_THE_WAY", "STARTED", "PAUSED", "RESUMED"]
    unassigned_private = list(
        PrivateBooking.objects.filter(provider__isnull=True, status__in=["ORDERED", "SCHEDULED"])
        .select_related("user")
        .order_by("created_at")[:3]
    )
    unassigned_business = list(
        BusinessBooking.objects.filter(provider__isnull=True, status__in=["ORDERED", "SCHEDULED"])
        .select_related("user", "selected_bundle")
        .order_by("created_at")[:3]
    )
    pending_no_shows = list(
        NoShowReport.objects.filter(decision="PENDING")
        .select_related("provider")
        .order_by("-created_at")[:3]
    )
    open_fixes = list(
        BookingRequestFix.objects.filter(status="OPEN")
        .select_related("customer")
        .order_by("-created_at")[:3]
    )
    unread_incidents = list(
        Incident.objects.filter(status="open")
        .select_related("customer")
        .order_by("-created_at")[:3]
    )

    actions = []
    for booking in unassigned_private:
        actions.append({
            "title": f"Assign private booking #{booking.id}",
            "detail": f"{_dashboard_booking_customer_label(booking)} • {_dashboard_booking_when(booking)}",
            "meta": _dashboard_booking_service_label(booking),
            "count": None,
            "priority": _dashboard_booking_priority(booking, now),
            "url": _dashboard_booking_url("private", booking.id),
            "action_label": "Open booking",
            "cta": "Assign provider",
        })
    for booking in unassigned_business:
        actions.append({
            "title": f"Assign business booking #{booking.id}",
            "detail": f"{_dashboard_booking_customer_label(booking)} • {_dashboard_booking_when(booking)}",
            "meta": _dashboard_booking_service_label(booking),
            "count": None,
            "priority": _dashboard_booking_priority(booking, now),
            "url": _dashboard_booking_url("business", booking.id),
            "action_label": "Open booking",
            "cta": "Assign provider",
        })
    for report in pending_no_shows:
        provider_name = str(report.provider) if report.provider_id else "Unknown provider"
        actions.append({
            "title": f"Review no-show #{report.id}",
            "detail": f"{report.booking_type.title()} booking #{report.booking_id} • {provider_name}",
            "meta": "Decision pending",
            "count": None,
            "priority": "high",
            "url": "/dashboard/no-show/",
            "cta": "Review case",
            "primary_action": {
                "label": "Approve no-show",
                "url": reverse("home:dashboard_no_show_decision", args=[report.id, "approve"]),
            },
            "secondary_action": {
                "label": "Reject",
                "url": reverse("home:dashboard_no_show_decision", args=[report.id, "reject"]),
            },
        })
    for fix in open_fixes:
        customer_name = getattr(fix.customer, "email", "") or getattr(fix.customer, "username", "") or str(fix.customer)
        actions.append({
            "title": f"Open fix request #{fix.id}",
            "detail": f"{customer_name} • {fix.booking_type.title()} booking #{fix.booking_id}",
            "meta": "Customer waiting for follow-up",
            "count": None,
            "priority": "high",
            "url": "/dashboard/request-fixes/",
            "action_label": "Open fix",
            "cta": "Open fix",
            "primary_action": {
                "label": "Mark in review",
                "url": reverse("home:dashboard_request_fix_status", args=[fix.id, "in-review"]),
            },
        })
    for incident in unread_incidents:
        actions.append({
            "title": f"Investigate incident #{incident.id}",
            "detail": f"{incident.customer} • {incident.incident_type or 'Incident'}",
            "meta": "Open incident",
            "count": None,
            "priority": "medium",
            "url": "/dashboard/incidents/",
            "action_label": "Open incident",
            "cta": "Open incident",
        })
    return sorted(
        actions,
        key=lambda item: {"high": 0, "medium": 1, "normal": 2}.get(item["priority"], 3),
    )[:8]


def _dashboard_today_queue(now):
    today = timezone.localdate()
    active_statuses = ["ORDERED", "SCHEDULED", "ASSIGNED", "ON_THE_WAY", "STARTED", "PAUSED", "RESUMED"]

    private_today = list(
        PrivateBooking.objects.filter(
            appointment_date=today,
            status__in=active_statuses,
        ).select_related("user", "provider")
    )
    business_today = list(
        BusinessBooking.objects.filter(
            Q(custom_date=today) | Q(start_date=today),
            status__in=active_statuses,
        ).select_related("user", "provider", "selected_bundle")
    )
    combined = private_today + business_today

    queue_items = []
    for booking in combined:
        start_dt, _ = booking.get_service_window()
        primary_action_label = "Open booking"
        if booking.provider_id is None:
            primary_action_label = "Assign provider"
        elif booking.status in ["STARTED", "ON_THE_WAY", "PAUSED", "RESUMED"]:
            primary_action_label = "Track booking"
        provider_options = []
        if booking.provider_id is None:
            for provider in _filtered_provider_queryset(booking):
                provider_label = provider.get_full_name().strip() or provider.username
                profile = getattr(provider, "provider_profile", None)
                area_label = ""
                if profile:
                    area_label = profile.area or profile.city or profile.region or ""
                if area_label:
                    provider_label = f"{provider_label} ({area_label})"
                provider_options.append({
                    "id": provider.id,
                    "label": provider_label,
                })
        queue_items.append({
            "title": f"{booking._booking_type().title()} booking #{booking.id}",
            "detail": _dashboard_booking_customer_label(booking),
            "service": _dashboard_booking_service_label(booking),
            "time_label": _dashboard_booking_when(booking),
            "status": booking.get_status_display(),
            "provider": str(booking.provider) if booking.provider_id else "Unassigned",
            "is_unassigned": booking.provider_id is None,
            "is_active": booking.status in ["STARTED", "ON_THE_WAY", "PAUSED", "RESUMED"],
            "is_overdue": bool(start_dt and start_dt < now and booking.status not in BaseBooking.INACTIVE_STATUSES),
            "url": _dashboard_booking_url(booking._booking_type(), booking.id),
            "primary_action_label": primary_action_label,
            "secondary_action_label": "Open details",
            "provider_options": provider_options,
            "assign_url": reverse("home:dashboard_assign_provider", args=[booking._booking_type(), booking.id]),
            "sort_key": start_dt or now,
        })
    queue_items = sorted(queue_items, key=lambda item: (item["sort_key"], item["is_unassigned"] is False))[:8]

    active_started = sum(1 for booking in combined if booking.status in ["STARTED", "ON_THE_WAY", "PAUSED", "RESUMED"])
    overdue = sum(1 for item in queue_items if item["is_overdue"])
    unassigned = sum(1 for item in queue_items if item["is_unassigned"])
    return {
        "summary": {
            "scheduled_today": len(combined),
            "active_now": active_started,
            "overdue": overdue,
            "unassigned": unassigned,
        },
        "items": queue_items,
    }


def _dashboard_unified_inbox(now):
    since = now - timedelta(days=7)
    inbox = []

    recent_private = list(
        PrivateBooking.objects.filter(created_at__gte=since)
        .select_related("user", "provider")
        .order_by("-created_at")[:5]
    )
    recent_business = list(
        BusinessBooking.objects.filter(created_at__gte=since)
        .select_related("user", "provider", "selected_bundle")
        .order_by("-created_at")[:5]
    )
    recent_fixes = list(
        BookingRequestFix.objects.filter(created_at__gte=since)
        .select_related("customer")
        .order_by("-created_at")[:5]
    )
    recent_incidents = list(
        Incident.objects.filter(created_at__gte=since)
        .select_related("customer")
        .order_by("-created_at")[:5]
    )
    recent_messages = list(
        ChatMessage.objects.filter(created_at__gte=since, is_read=False)
        .select_related("sender", "thread")
        .order_by("-created_at")[:5]
    )

    for booking in recent_private:
        inbox.append({
            "kind": "booking",
            "kind_label": "Private booking",
            "title": f"Private booking #{booking.id}",
            "detail": f"{_dashboard_booking_customer_label(booking)} • {_dashboard_booking_service_label(booking)}",
            "time": booking.created_at,
            "state": booking.get_status_display(),
            "url": _dashboard_booking_url("private", booking.id),
        })
    for booking in recent_business:
        inbox.append({
            "kind": "booking",
            "kind_label": "Business booking",
            "title": f"Business booking #{booking.id}",
            "detail": f"{_dashboard_booking_customer_label(booking)} • {_dashboard_booking_service_label(booking)}",
            "time": booking.created_at,
            "state": booking.get_status_display(),
            "url": _dashboard_booking_url("business", booking.id),
        })
    for fix in recent_fixes:
        customer_name = getattr(fix.customer, "email", "") or getattr(fix.customer, "username", "") or str(fix.customer)
        inbox.append({
            "kind": "fix",
            "kind_label": "Request fix",
            "title": f"Request fix #{fix.id}",
            "detail": f"{customer_name} • {fix.booking_type.title()} booking #{fix.booking_id}",
            "time": fix.created_at,
            "state": fix.get_status_display(),
            "url": "/dashboard/request-fixes/",
        })
    for incident in recent_incidents:
        inbox.append({
            "kind": "incident",
            "kind_label": "Incident",
            "title": f"Incident #{incident.id}",
            "detail": f"{incident.customer} • {incident.incident_type or 'Incident report'}",
            "time": incident.created_at,
            "state": incident.status.title(),
            "url": "/dashboard/incidents/",
        })
    for msg in recent_messages:
        inbox.append({
            "kind": "message",
            "kind_label": "Unread message",
            "title": f"Message from {msg.sender}",
            "detail": f"{msg.thread.booking_type.title()} booking #{msg.thread.booking_id}",
            "time": msg.created_at,
            "state": "Unread",
            "url": _dashboard_booking_url(msg.thread.booking_type, msg.thread.booking_id),
            "action_label": "Open thread",
        })

    return sorted(inbox, key=lambda item: item["time"], reverse=True)[:12]


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
    today_queue = _dashboard_today_queue(now)
    context = {
        "cards": cards,
        "items": items,
        "action_center": _dashboard_action_center(now),
        "today_queue": today_queue["items"],
        "today_queue_summary": today_queue["summary"],
        "unified_inbox": _dashboard_unified_inbox(now),
    }
    context.update(_dashboard_notifications())
    return render(request, "dashboard/index.html", context)


@user_passes_test(_staff_required)
@require_POST
def dashboard_request_fix_status(request, fix_id, status_slug):
    request_fix = get_object_or_404(BookingRequestFix, pk=fix_id)
    status_map = {
        "in-review": "IN_REVIEW",
        "resolved": "RESOLVED",
    }
    new_status = status_map.get(status_slug)
    if not new_status:
        return _dashboard_async_response(request, False, "Invalid request-fix status.", status=400)
    if request_fix.status != new_status:
        request_fix.status = new_status
        request_fix.save(update_fields=["status"])
        CustomerNotification.objects.create(
            user=request_fix.customer,
            title="Request Fix Updated",
            body=f"Your request fix for booking #{request_fix.booking_id} is now {new_status.replace('_', ' ').title()}.",
            notification_type="request_fix",
            booking_type=request_fix.booking_type,
            booking_id=request_fix.booking_id,
            request_fix=request_fix,
        )
    return _dashboard_async_response(request, True, f"Request fix #{request_fix.id} updated to {new_status.replace('_', ' ').title()}.")


@user_passes_test(_staff_required)
@require_POST
def dashboard_no_show_decision(request, report_id, decision_slug):
    report = get_object_or_404(NoShowReport, pk=report_id)
    if report.decision != "PENDING":
        return _dashboard_async_response(request, False, "This no-show report was already reviewed.", status=400)

    booking = _dashboard_get_booking_instance(report.booking_type, report.booking_id)
    note = f"Dashboard {decision_slug.replace('-', ' ')}"
    if decision_slug == "approve":
        report.decision = "APPROVED"
        report.reviewed_by = request.user
        report.reviewed_note = note
        report.reviewed_at = timezone.now()
        report.save(update_fields=["decision", "reviewed_by", "reviewed_note", "reviewed_at"])
        booking.approve_no_show(admin_user=request.user, note=note)
    elif decision_slug == "reject":
        report.decision = "REJECTED"
        report.reviewed_by = request.user
        report.reviewed_note = note
        report.reviewed_at = timezone.now()
        report.save(update_fields=["decision", "reviewed_by", "reviewed_note", "reviewed_at"])
        booking.reject_no_show(admin_user=request.user, note=note)
    else:
        return _dashboard_async_response(request, False, "Invalid no-show decision.", status=400)
    decision_label = "approved" if decision_slug == "approve" else "rejected"
    return _dashboard_async_response(request, True, f"No-show report #{report.id} {decision_label}.")


@user_passes_test(_staff_required)
@require_POST
def dashboard_assign_provider(request, booking_type, booking_id):
    booking = _dashboard_get_booking_instance(booking_type, booking_id)
    provider_id = (request.POST.get("provider_id") or "").strip()
    if not provider_id:
        return _dashboard_async_response(request, False, "Select a provider first.", status=400)

    allowed_provider = _filtered_provider_queryset(booking).filter(pk=provider_id).first()
    if not allowed_provider:
        return _dashboard_async_response(request, False, "Selected provider is not available for this booking.", status=400)

    try:
        booking.assign_provider(provider=allowed_provider, user=request.user)
        provider_name = allowed_provider.get_full_name().strip() or allowed_provider.username
        return _dashboard_async_response(request, True, f"{provider_name} assigned to booking #{booking.id}.")
    except Exception as exc:
        return _dashboard_async_response(request, False, str(exc) or "Could not assign provider.", status=400)


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
        if "provider" in self.fields:
            self.fields["provider"].queryset = _filtered_provider_queryset(self.instance)
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

    def clean_provider(self):
        provider = self.cleaned_data.get("provider")
        if not provider:
            return provider
        if self.instance and not self.instance.provider_is_available(provider):
            raise forms.ValidationError("Provider is already assigned to an overlapping booking.")
        return provider

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


class PrivateBookingDashboardForm(forms.ModelForm):
    class Meta:
        model = PrivateBooking
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "provider" in self.fields:
            self.fields["provider"].queryset = _filtered_provider_queryset(self.instance)

    def clean_provider(self):
        provider = self.cleaned_data.get("provider")
        if not provider:
            return provider
        if self.instance and not self.instance.provider_is_available(provider):
            raise forms.ValidationError("Provider is already assigned to an overlapping booking.")
        return provider


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

class ProviderProfileDashboardCreateForm(forms.Form):
    username = forms.CharField(label="Username", max_length=150)
    email = forms.EmailField(label="Email")
    first_name = forms.CharField(label="First name", required=False)
    last_name = forms.CharField(label="Last name", required=False)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    city = forms.CharField(label="City", required=False)
    region = forms.CharField(label="Region", required=False)
    area = forms.CharField(label="Area / District", required=False)
    nearby_areas = forms.CharField(
        label="Nearby areas",
        required=False,
        help_text="Comma-separated nearby areas.",
    )
    bio = forms.CharField(label="Bio", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    is_active = forms.BooleanField(label="Active", required=False, initial=True)

    def clean(self):
        cleaned = super().clean()
        pwd1 = cleaned.get("password1")
        pwd2 = cleaned.get("password2")
        if pwd1 and pwd2 and pwd1 != pwd2:
            self.add_error("password2", "Passwords do not match.")
        username = cleaned.get("username")
        if username and User.objects.filter(username=username).exists():
            self.add_error("username", "Username already exists.")
        email = cleaned.get("email")
        if email and User.objects.filter(email=email).exists():
            self.add_error("email", "Email already exists.")
        return cleaned

    def save(self):
        user = User(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email", ""),
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
            is_active=True,
        )
        user.set_password(self.cleaned_data["password1"])
        user.save()

        nearby_raw = self.cleaned_data.get("nearby_areas") or ""
        nearby_list = [p.strip() for p in nearby_raw.split(",") if p.strip()]

        profile = ProviderProfile.objects.create(
            user=user,
            bio=self.cleaned_data.get("bio", ""),
            is_active=bool(self.cleaned_data.get("is_active")),
            city=self.cleaned_data.get("city", ""),
            region=self.cleaned_data.get("region", ""),
            area=self.cleaned_data.get("area", ""),
            nearby_areas=nearby_list,
        )
        return profile


class ProviderProfileDashboardEditForm(forms.ModelForm):
    nearby_areas_text = forms.CharField(
        label="Nearby areas",
        required=False,
        help_text="Comma-separated nearby areas.",
    )

    class Meta:
        model = ProviderProfile
        fields = ["user", "bio", "is_active", "city", "region", "area"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "user" in self.fields:
            self.fields["user"].disabled = True
        if self.instance and self.instance.nearby_areas:
            self.fields["nearby_areas_text"].initial = ", ".join(self.instance.nearby_areas)

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw = self.cleaned_data.get("nearby_areas_text") or ""
        instance.nearby_areas = [p.strip() for p in raw.split(",") if p.strip()]
        if commit:
            instance.save()
        return instance


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
    if service_id and item.model.__name__ in {"ServiceCard", "ServicePricing", "ServiceEstimate", "ServiceEcoPromise", "BusinessServiceCard"}:
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

    field_names = {f.name for f in item.model._meta.fields}
    if "created_at" in field_names:
        qs = qs.order_by("-created_at", "-pk")
    elif "issued_at" in field_names:
        qs = qs.order_by("-issued_at", "-pk")
    elif "updated_at" in field_names:
        qs = qs.order_by("-updated_at", "-pk")
    elif "date_joined" in field_names:
        qs = qs.order_by("-date_joined", "-pk")
    else:
        qs = qs.order_by("-pk")

    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page"))

    display_fields_map = {
        "provider-profiles": ["user", "city", "region", "area", "nearby_areas", "is_active"],
        "business-services": ["title", "recommended", "detail_description", "image", "hero_image"],
        "business-service-cards": ["service", "title", "order"],
        "business-bundles": ["title", "discount", "short_description", "image"],
        "business-addons": ["title", "description", "emoji"],
        "private-services": ["title", "category", "price", "recommended", "image"],
        "private-addons": ["title", "service", "price", "price_per_unit", "icon"],
        "service-cards": ["service", "title", "order"],
        "service-pricing": ["service", "price_value", "price_note", "cta_text"],
        "service-estimates": ["service", "property_label", "bedrooms_label", "cta_text"],
        "service-eco": ["service", "title", "cta_text", "subtitle"],
        "service-eco-points": ["promise", "title", "order", "icon"],
    }
    display_fields = display_fields_map.get(item.slug, _model_fields(item.model)[:5])

    service_obj = None
    if service_id:
        if item.slug in {"service-cards", "service-pricing", "service-estimates", "service-eco", "service-eco-points"}:
            service_obj = PrivateService.objects.filter(id=service_id).first()
        if item.slug == "business-service-cards":
            service_obj = BusinessService.objects.filter(id=service_id).first()

    context = {
        "items": get_dashboard_items(),
        "item": item,
        "objects": page,
        "display_fields": display_fields,
        "query": q,
        "service_id": service_id,
        "service_obj": service_obj,
        "use_view_mode": _dashboard_uses_view_mode(item),
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
    elif item.model == PrivateBooking:
        Form = modelform_factory(
            item.model,
            form=PrivateBookingDashboardForm,
            exclude=_exclude_fields_for_form(item.model),
        )
    elif item.model == BusinessAddon:
        Form = BusinessAddonDashboardForm
    elif item.model == DateSurcharge:
        Form = DateSurchargeDashboardForm
    elif item.model == ScheduleRule:
        Form = ScheduleRuleDashboardForm
    elif item.model == ProviderProfile:
        Form = ProviderProfileDashboardCreateForm
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
            if isinstance(form, forms.ModelForm):
                obj = form.save(commit=False)
                if isinstance(obj, ProviderAdminMessage) and not obj.created_by_id:
                    obj.created_by = request.user
                obj.save()
            else:
                form.save()
            return redirect("home:dashboard_model_list", model=item.slug)
    else:
        initial = {}
        if item.model == PrivateAddon:
            service_id = request.GET.get("service_id")
            if service_id:
                initial["service"] = service_id
        if item.model == BusinessServiceCard:
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
    elif item.model == PrivateBooking:
        Form = modelform_factory(
            item.model,
            form=PrivateBookingDashboardForm,
            exclude=_exclude_fields_for_form(item.model),
        )
    elif item.model == BusinessAddon:
        Form = BusinessAddonDashboardForm
    elif item.model == DateSurcharge:
        Form = DateSurchargeDashboardForm
    elif item.model == ScheduleRule:
        Form = ScheduleRuleDashboardForm
    elif item.model == ProviderProfile:
        Form = ProviderProfileDashboardEditForm
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
    business_cards_for_service = None
    if item.model.__name__ == "PrivateAddon" and obj.form_html:
        addon_form_preview = mark_safe(obj.form_html)
    if item.model == PrivateService:
        addons_for_service = PrivateAddon.objects.filter(service=obj).order_by("title")
    if item.model == BusinessService:
        business_cards_for_service = BusinessServiceCard.objects.filter(service=obj).order_by("order", "title")

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
        "business_cards_for_service": business_cards_for_service,
        "emoji_datalist": EMOJI_OPTIONS if item.model == BusinessAddon else None,
    }
    if item.model in {BusinessBooking, PrivateBooking}:
        context["provider_debug"] = _provider_debug_payload(obj)
    context.update(_dashboard_notifications())
    return render(request, "dashboard/form.html", context)


@user_passes_test(_staff_required)
def dashboard_model_view(request, model, pk):
    item = get_item_by_slug(model)
    if not item:
        return render(request, "dashboard/not_found.html", {"items": get_dashboard_items()})

    obj = get_object_or_404(item.model, pk=pk)
    if item.model == BusinessBundle:
        Form = BusinessBundleDashboardForm
    elif item.model == BusinessBooking:
        Form = modelform_factory(
            item.model,
            form=BusinessBookingDashboardForm,
            exclude=_exclude_fields_for_form(item.model),
        )
    elif item.model == PrivateBooking:
        Form = modelform_factory(
            item.model,
            form=PrivateBookingDashboardForm,
            exclude=_exclude_fields_for_form(item.model),
        )
    elif item.model == BusinessAddon:
        Form = BusinessAddonDashboardForm
    elif item.model == DateSurcharge:
        Form = DateSurchargeDashboardForm
    elif item.model == ScheduleRule:
        Form = ScheduleRuleDashboardForm
    elif item.model == ProviderProfile:
        Form = ProviderProfileDashboardEditForm
    else:
        Form = modelform_factory(
            item.model,
            exclude=_exclude_fields_for_form(item.model),
            formfield_callback=lambda db_field, **kwargs: _json_formfield_callback(item.model, db_field, **kwargs),
        )

    form = _bootstrap_form(Form(instance=obj))
    for field in form.fields.values():
        field.disabled = True
        widget = field.widget
        existing_class = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{existing_class} dash-disabled-field".strip()

    addon_form_preview = None
    addons_for_service = None
    business_cards_for_service = None
    if item.model.__name__ == "PrivateAddon" and getattr(obj, "form_html", ""):
        addon_form_preview = mark_safe(obj.form_html)
    if item.model == PrivateService:
        addons_for_service = PrivateAddon.objects.filter(service=obj).order_by("title")
    if item.model == BusinessService:
        business_cards_for_service = BusinessServiceCard.objects.filter(service=obj).order_by("order", "title")

    json_readonly = _json_readonly(
        obj,
        exclude_fields=JSON_EDIT_FIELDS.get(item.model, set())
    )

    context = {
        "items": get_dashboard_items(),
        "item": item,
        "form": form,
        "mode": "view",
        "object": obj,
        "json_readonly": json_readonly,
        "addon_form_preview": addon_form_preview,
        "addons_for_service": addons_for_service,
        "business_cards_for_service": business_cards_for_service,
        "emoji_datalist": EMOJI_OPTIONS if item.model == BusinessAddon else None,
    }
    if item.model in {BusinessBooking, PrivateBooking}:
        context["provider_debug"] = _provider_debug_payload(obj)
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
    urgent_selected = request.GET.get("urgent") == "1"
    return render(request, "home/AllServicesBusiness.html", {
        "services": services,
        "urgent_selected": urgent_selected,
    })


def business_service_detail(request, service_id):
    service = get_object_or_404(BusinessService.objects.prefetch_related("cards"), id=service_id)
    urgent_selected = request.GET.get("urgent") == "1"
    return render(request, "home/business_service_detail.html", {
        "service": service,
        "cards": list(service.cards.all()),
        "urgent_selected": urgent_selected,
    })


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
        "selected_service": _normalize_business_service_title(service),
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


def _set_business_path_type(request, path_type):
    data = _get_business_draft(request)
    data["path_type"] = path_type
    if path_type == "bundle":
        data.pop("services_needed", None)
        data.pop("addons", None)
    elif path_type == "custom":
        data.pop("selected_bundle_id", None)
    request.session["business_booking_draft"] = data
    request.session.modified = True


def _normalize_business_service_title(raw_value):
    value = (raw_value or "").strip()
    if not value:
        return ""
    service = BusinessService.objects.filter(title__iexact=value).first()
    return service.title if service else value


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
    min_booking_date = timezone.localdate().isoformat()

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

    _set_business_path_type(request, "bundle")

    total_steps = 7
    range_steps = range(1, total_steps + 1)
    bundles = BusinessBundle.objects.all()

    if request.method == "POST":
        bundle_id = request.POST.get("bundle_id")
        if bundle_id:
            bundle = BusinessBundle.objects.filter(id=bundle_id).first()
            if bundle is None:
                return render(request, "home/business_bundles.html", {
                    "booking": booking,
                    "bundles": bundles,
                    "step": 3,
                    "total_steps": total_steps,
                    "range_total_steps": range_steps,
                    "booking_id": 0,
                    "error": "Selected bundle is not valid.",
                })
            _update_business_draft(request, {"selected_bundle_id": bundle.id})
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

    _set_business_path_type(request, "custom")

    total_steps = 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        selected_services = request.POST.get("selected_services")
        if selected_services:
            try:
                parsed_services = json.loads(selected_services)
            except json.JSONDecodeError:
                parsed_services = []
            _update_business_draft(request, {"services_needed": parsed_services})
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
            try:
                parsed_frequency = json.loads(freq_raw)
            except json.JSONDecodeError:
                parsed_frequency = {}
            _update_business_draft(request, {"frequency": parsed_frequency})
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

        # ??? ????????
        start_date_raw = request.POST.get("start_date")
        preferred_time = request.POST.get("preferred_time")
        custom_date_raw = request.POST.get("custom_date") or None

        # ??????
        if not start_date_raw or not preferred_time:
              return render(request, "home/SchedulingNotes.html", {
                  "booking": booking,
                  "step": step_number,
                  "total_steps": total_steps,
                  "range_total_steps": range_steps,
                  "error": "Please select a start date and preferred time.",
                  "min_booking_date": min_booking_date,
              })

        start_date = parse_date(start_date_raw)
        custom_date = parse_date(custom_date_raw) if custom_date_raw else None
        if not start_date or (custom_date_raw and not custom_date):
            return render(request, "home/SchedulingNotes.html", {
                "booking": booking,
                "step": step_number,
                "total_steps": total_steps,
                "range_total_steps": range_steps,
                "error": "Invalid date format. Please choose a valid date.",
                "min_booking_date": min_booking_date,
            })

        if _date_is_before_today(start_date) or (custom_date and _date_is_before_today(custom_date)):
            return render(request, "home/SchedulingNotes.html", {
                "booking": booking,
                "step": step_number,
                "total_steps": total_steps,
                "range_total_steps": range_steps,
                "error": "Booking date cannot be before today. Please choose today or a future date.",
                "min_booking_date": min_booking_date,
            })

        _update_business_draft(request, {
            "start_date": start_date_raw,
            "preferred_time": preferred_time,
            "days_type": request.POST.get("days_type"),
            "custom_date": custom_date_raw,
            "custom_time": request.POST.get("custom_time") or None,
            "notes": request.POST.get("notes"),
        })

        draft = _get_business_draft(request)
        path_type = draft.get("path_type") or "bundle"
        created = BusinessBooking(
            selected_service=_normalize_business_service_title(draft.get("selected_service")),
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
            services_needed=draft.get("services_needed") if path_type == "custom" else None,
            addons=draft.get("addons") if path_type == "custom" else None,
            frequency=draft.get("frequency") or {},
            start_date=start_date,
            preferred_time=draft.get("preferred_time"),
            days_type=draft.get("days_type"),
            custom_date=custom_date,
            custom_time=draft.get("custom_time"),
            notes=draft.get("notes"),
            path_type=path_type,
            is_urgent=bool(draft.get("is_urgent")),
            user=request.user if request.user.is_authenticated else None,
        )
        selected_bundle_id = draft.get("selected_bundle_id")
        if path_type == "bundle" and selected_bundle_id:
            created.selected_bundle_id = selected_bundle_id

        try:
            created.save()
            created.log_status(user=request.user, note="Order placed")
            if created.is_urgent:
                created.log_status(user=request.user, note="Urgent booking (same day) requested")
            request.session["latest_business_booking_id"] = created.id
            request.session.modified = True
            request.session.pop("business_booking_draft", None)
        except Exception:
            logger.exception("Business scheduling failed for draft=%s", draft)
            return render(request, "home/SchedulingNotes.html", {
                "booking": booking,
                "step": step_number,
                "total_steps": total_steps,
                "range_total_steps": range_steps,
                "error": "Something went wrong while placing your booking. Please try again.",
                "min_booking_date": min_booking_date,
            })

        return redirect("home:business_thank_you", booking_id=created.id)

    return render(request, "home/SchedulingNotes.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
        "booking_id": 0,
        "min_booking_date": min_booking_date,
    })

# ================================
# STEP 6 OR 7 — THANK YOU
# ================================
def business_thank_you(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)
    session_booking_id = request.session.get("latest_business_booking_id")
    is_owner = request.user.is_authenticated and booking.user_id == request.user.id
    is_same_session = str(session_booking_id or "") == str(booking.id)

    if not (is_owner or is_same_session):
        raise Http404("Booking not found")

    if booking.path_type == "bundle":
        step_number = 6
    else:
        step_number = 7

    total_steps = 7

    range_steps = range(1, total_steps + 1)
    min_booking_date = timezone.localdate().isoformat()
    return render(request, "home/business_thank_you.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })



# ================================================================================================================
def all_services(request):
    services = PrivateService.objects.all()
    urgent_param = request.GET.get("urgent")
    if urgent_param == "1":
        request.session["urgent_booking"] = True
        request.session.modified = True
    elif urgent_param == "0":
        request.session.pop("urgent_booking", None)
        request.session.modified = True
    urgent_selected = bool(request.session.get("urgent_booking")) or urgent_param == "1"
    return render(request, "home/AllServicesPrivate.html", {
        "services": services,
        "urgent_selected": urgent_selected,
    })





AVAILABLE_ZIP_RANGES = [
    (10000, 12999),  # Stockholm City
    (13100, 13199),  # Nacka
    (13200, 13299),
    (13300, 13399),
    (13500, 13599),  # Tyreso
    (13600, 13699),  # Haninge
    (14100, 14199),  # Huddinge
    (14200, 14299),
    (14500, 14599),  # Botkyrka
    (14600, 14699),
    (14700, 14799),
    (16900, 16999),  # Solna
    (17100, 17199),
    (17200, 17299),  # Sundbyberg
    (17400, 17499),
    (17500, 17599),  # Jarfalla
    (17700, 17799),
    (17800, 17899),  # Ekero
    (18100, 18199),  # Lidingo
    (18200, 18299),  # Danderyd
    (18300, 18399),  # Tabby
    (18600, 18699),  # Vallentuna
]


def _normalize_zip(zip_code_value):
    digits = "".join(ch for ch in str(zip_code_value) if ch.isdigit())
    if len(digits) != 5:
        return None
    return int(digits)


def _is_zip_available(zip_code_value):
    numeric = _normalize_zip(zip_code_value)
    if numeric is None:
        return False
    return any(start <= numeric <= end for start, end in AVAILABLE_ZIP_RANGES)


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
                normalized_zip = _normalize_zip(zip_code_value)

                if _is_zip_available(zip_code_value):

                    # (اختياري) إنشاء booking لاحقاً، مو هون
                    request.session["zip_code"] = str(normalized_zip) if normalized_zip else str(zip_code_value)
                    draft = _get_private_draft_data(request)
                    draft["zip_code"] = str(normalized_zip) if normalized_zip else str(zip_code_value)
                    draft["zip_is_available"] = True
                    _save_private_draft_data(request, draft)

                    return redirect(
                        "home:private_zip_available",
                        service_slug=service.slug
                    )

                else:
                    request.session.pop("zip_code", None)
                    show_not_available = True
                    not_available_form = NotAvailableZipForm(
                        initial={"zip_code": str(normalized_zip) if normalized_zip else zip_code_value}
                    )
            else:
                request.session.pop("zip_code", None)

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
def private_booking_checkout(request):
    draft = _get_private_draft_data(request)
    selected_slugs = draft.get("selected_services") or []
    if not selected_slugs:
        cart = request.session.get("private_cart", [])
        if cart:
            draft["selected_services"] = cart
            _save_private_draft_data(request, draft)
            selected_slugs = cart
        else:
            return redirect("home:all_services_private")

    services = PrivateService.objects.filter(slug__in=selected_slugs).select_related("category")
    temp_booking = _build_private_booking_from_draft(draft, request.user)

    pricing = calculate_booking_price(temp_booking)
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

    draft["subtotal"] = float(subtotal)
    draft["total_price"] = float(final_after_rot)
    draft["rot_discount"] = float(rot_value)
    draft["pricing_details"] = pricing
    draft["quoted_duration_minutes"] = int(pricing.get("duration_minutes") or 0)
    _save_private_draft_data(request, draft)

    customer = None
    if request.user.is_authenticated:
        customer = Customer.objects.filter(user=request.user).first()
    completed_bookings = 0
    if request.user.is_authenticated:
        completed_bookings = (
            PrivateBooking.objects.filter(user=request.user, status="COMPLETED").count()
            + BusinessBooking.objects.filter(user=request.user, status="COMPLETED").count()
        )
    referral_discount_percent = 10
    referral_discount_amount = Decimal("0.00")
    referral_discount_applied = False
    referral_discount_eligible = (
        customer is not None
        and customer.has_referral_discount
        and completed_bookings == 0
    )

    display_address = None
    if customer:
        display_address = customer.display_address()
    if not display_address:
        display_address = "Not provided"

    display_area = draft.get("area")
    if not display_area and customer:
        display_area = customer.display_city()
    if not display_area:
        display_area = "Not provided"

    customer_snapshot = _get_private_booking_customer_snapshot(customer)
    if customer_snapshot.get("address") and not draft.get("address"):
        draft["address"] = customer_snapshot["address"]
    if customer_snapshot.get("area") and not draft.get("area"):
        draft["area"] = customer_snapshot["area"]
    if customer_snapshot.get("zip_code") and not draft.get("zip_code"):
        draft["zip_code"] = customer_snapshot["zip_code"]
    _save_private_draft_data(request, draft)

    if draft.get("duration_hours"):
        display_duration = draft.get("duration_hours")
    elif duration_seconds > 0:
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        display_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        display_duration = "To be confirmed"

    # ربط المستخدم
    if temp_booking.user is None and request.user.is_authenticated:
        temp_booking.user = request.user

    # ==========================
    # 🧮 PREVIEW CALCULATION
    # ==========================
    discount_preview_amount = Decimal("0.00")
    final_preview_price = final_after_rot

    discount_code_display = None
    discount_code_id = draft.get("discount_code_id")
    if discount_code_id:
        dc = DiscountCode.objects.filter(id=discount_code_id).first()
        if not dc:
            draft.pop("discount_code_id", None)
            _save_private_draft_data(request, draft)
            messages.warning(request, "Discount code is not valid anymore.")
        else:
            is_valid, reason = dc.validate(user=request.user)
            if is_valid:
                discount_code_display = dc
                temp_booking.discount_code = dc
                discount_preview_amount = (
                    final_after_rot * Decimal(dc.percent) / Decimal(100)
                )
                final_preview_price = final_after_rot - discount_preview_amount
            else:
                draft.pop("discount_code_id", None)
                _save_private_draft_data(request, draft)
                messages.warning(request, reason or "Discount code is not valid anymore.")
    elif referral_discount_eligible:
        referral_discount_amount = final_after_rot * Decimal(referral_discount_percent) / Decimal(100)
        final_preview_price = final_after_rot - referral_discount_amount
        referral_discount_applied = True

    stripe_publishable_key = settings.STRIPE_PUBLISHABLE_KEY
    stripe_secret_key = settings.STRIPE_SECRET_KEY
    stripe_currency = (settings.STRIPE_CURRENCY or "sek").lower()

    payment_summary = _calculate_private_payment_summary(temp_booking, stripe_currency)
    final_preview_price = payment_summary["amount"]
    payment_summary_data = _serialize_private_payment_summary(payment_summary)

    draft["payment_summary"] = payment_summary_data
    _save_private_draft_data(request, draft)

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
                    draft["discount_code_id"] = dc.id
                    _save_private_draft_data(request, draft)
                    messages.success(request, "Discount code applied successfully.")

            return redirect("home:private_booking_checkout")

        # 💳 CONFIRM PAYMENT
        elif form_type == "payment":
            messages.error(request, "Please complete payment using the card form.")
            return redirect("home:private_booking_checkout")

        elif form_type == "remove_discount":
            draft.pop("discount_code_id", None)
            _save_private_draft_data(request, draft)
            messages.info(request, "Discount code removed.")
            return redirect("home:private_booking_checkout")

    # ==========================
    # STRIPE PAYMENT INTENT
    # ==========================
    stripe_client_secret = draft.get("stripe_client_secret")
    stripe_payment_intent_id = draft.get("payment_intent_id")
    stripe_ready = bool(stripe_publishable_key and stripe_secret_key)
    payment_element_version = "payment_element_card_v1"
    current_payment_signature = json.dumps(
        {
            "amount_cents": payment_summary_data["amount_cents"],
            "currency": payment_summary_data["currency"],
            "selected_services": selected_slugs,
            "discount_code_id": draft.get("discount_code_id"),
            "appointment_date": draft.get("appointment_date"),
            "appointment_time_window": draft.get("appointment_time_window"),
            "schedule_mode": draft.get("schedule_mode"),
        },
        sort_keys=True,
        cls=DjangoJSONEncoder,
    )

    if stripe_ready:
        if payment_summary["amount_cents"] <= 0:
            stripe_ready = False
            messages.error(request, "Payment amount must be greater than zero.")
        elif payment_summary["amount_cents"] < _stripe_minimum_amount_cents(stripe_currency):
            stripe_ready = False
            min_amount = Decimal(_stripe_minimum_amount_cents(stripe_currency)) / Decimal("100")
            messages.error(
                request,
                f"Minimum card payment is {min_amount:.2f} {stripe_currency.upper()}. "
                "Increase the booking total or reduce discounts."
            )
        else:
            stripe.api_key = stripe_secret_key
            customer_name = ""
            customer_email = ""
            customer_phone = ""
            if request.user.is_authenticated:
                customer_name = request.user.get_full_name() or request.user.username or ""
                customer_email = request.user.email or ""
            if customer:
                customer_name = customer_name or f"{customer.first_name} {customer.last_name}".strip()
                customer_email = customer_email or customer.email or ""
                customer_phone = customer.phone or ""
            stripe_customer_id = _get_or_create_checkout_stripe_customer(customer)

            draft_payload = dict(draft)
            draft_payload.update({
                "selected_services": selected_slugs,
                "pricing_details": pricing,
                "discount_code_id": draft.get("discount_code_id"),
                "user_id": request.user.id if request.user.is_authenticated else None,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
            })

            draft_record = None
            if stripe_payment_intent_id:
                draft_record = PrivateBookingDraft.objects.filter(
                    payment_intent_id=stripe_payment_intent_id,
                    user=request.user,
                ).first()

            metadata = {
                "booking_type": "private",
                "draft_id": str(draft_record.id) if draft_record else "",
                "user_id": str(request.user.id),
                "service_id": ",".join(selected_slugs),
                "date": draft.get("appointment_date") or "",
                "time": draft.get("appointment_time_window") or "",
                "price": payment_summary_data["amount"],
                "currency": payment_summary_data["currency"],
            }

            signature_changed = draft.get("payment_signature") != current_payment_signature

            try:
                intent = None
                needs_metadata_sync = False
                intent_requires_replacement = (
                    draft.get("payment_element_version") != payment_element_version
                    or (draft.get("payment_summary") or {}).get("currency") != stripe_currency
                )
                if not stripe_payment_intent_id or intent_requires_replacement:
                    create_kwargs = {
                        "amount": payment_summary["amount_cents"],
                        "currency": stripe_currency,
                        "payment_method_types": ["card"],
                        "metadata": {"booking_type": "private", "user_id": str(request.user.id)},
                        "description": "Private booking checkout",
                    }
                    if stripe_customer_id:
                        create_kwargs["customer"] = stripe_customer_id
                    intent = stripe.PaymentIntent.create(**create_kwargs)
                    needs_metadata_sync = True
                elif signature_changed:
                    intent = stripe.PaymentIntent.modify(
                        stripe_payment_intent_id,
                        amount=payment_summary["amount_cents"],
                    )
                    needs_metadata_sync = True
                elif not stripe_client_secret:
                    intent = stripe.PaymentIntent.retrieve(stripe_payment_intent_id)

                if intent is not None:
                    stripe_client_secret = intent.client_secret
                    stripe_payment_intent_id = intent.id

                draft_record, _ = PrivateBookingDraft.objects.update_or_create(
                    payment_intent_id=stripe_payment_intent_id,
                    defaults={
                        "user": request.user,
                        "payment_status": getattr(intent, "status", None) or draft.get("payment_status") or "requires_payment_method",
                        "payment_amount": payment_summary["amount"],
                        "payment_currency": stripe_currency,
                        "payload": draft_payload,
                        "status": "pending",
                    },
                )

                metadata["draft_id"] = str(draft_record.id)
                metadata_sync_key = f"{stripe_payment_intent_id}:{draft_record.id}:{current_payment_signature}"
                if not stripe_payment_intent_id:
                    raise ValueError("Stripe payment intent was not initialized.")
                if intent is None and (
                    needs_metadata_sync or draft.get("metadata_sync_key") != metadata_sync_key
                ):
                    intent = stripe.PaymentIntent.modify(
                        stripe_payment_intent_id,
                        metadata=metadata,
                    )
                elif intent is not None and (
                    needs_metadata_sync or draft.get("metadata_sync_key") != metadata_sync_key
                ):
                    intent = stripe.PaymentIntent.modify(intent.id, metadata=metadata)

                if intent is not None:
                    stripe_client_secret = intent.client_secret

                draft["payment_intent_id"] = stripe_payment_intent_id
                draft["payment_status"] = draft_record.payment_status
                draft["stripe_client_secret"] = stripe_client_secret
                draft["payment_signature"] = current_payment_signature
                draft["metadata_sync_key"] = metadata_sync_key
                draft["payment_element_version"] = payment_element_version
                _save_private_draft_data(request, draft)

                logger.info("Stripe PaymentIntent ready: %s", stripe_payment_intent_id)
            except Exception as exc:
                logger.exception("Stripe PaymentIntent error for private draft")
                if settings.DEBUG:
                    user_message = getattr(exc, "user_message", None) or str(exc) or exc.__class__.__name__
                    messages.error(request, f"Payment service is temporarily unavailable. {user_message}")
                else:
                    messages.error(request, "Payment service is temporarily unavailable. Please try again.")
                stripe_ready = False
    return render(request, "home/checkout.html", {
        "booking": temp_booking,
        "services": services,
        "discount_preview_amount": discount_preview_amount,
        "referral_discount_amount": referral_discount_amount,
        "referral_discount_percent": referral_discount_percent,
        "referral_discount_applied": referral_discount_applied,
        "referral_discount_eligible": referral_discount_eligible,
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
        "stripe_publishable_key": stripe_publishable_key,
        "stripe_client_secret": stripe_client_secret,
        "stripe_payment_intent_id": stripe_payment_intent_id,
        "stripe_ready": stripe_ready,
        "stripe_currency": stripe_currency,
        "payment_complete_url": reverse("home:private_booking_payment_complete"),
        "payment_return_url": request.build_absolute_uri(reverse("home:private_booking_payment_complete")),
        "payment_failed_url": reverse("home:payment_failed"),
    })

@login_required
def private_booking_payment_complete(request):
    if request.method not in ("GET", "POST"):
        return HttpResponse(status=405)

    payment_intent_id = (
        request.POST.get("payment_intent_id")
        or request.GET.get("payment_intent")
        or request.GET.get("payment_intent_id")
        or ""
    ).strip()

    if not payment_intent_id:
        if request.method == "GET":
            messages.error(request, "Missing payment intent.")
            return redirect("home:payment_failed")
        return JsonResponse({"error": "Missing payment intent."}, status=400)

    if not settings.STRIPE_SECRET_KEY:
        if request.method == "GET":
            messages.error(request, "Payment service not configured.")
            return redirect("home:payment_failed")
        return JsonResponse({"error": "Payment service not configured."}, status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id, expand=["payment_method"])
    except Exception:
        logger.exception("Stripe retrieve failed for intent %s", payment_intent_id)
        if request.method == "GET":
            messages.error(request, "Unable to verify payment.")
            return redirect("home:payment_failed")
        return JsonResponse({"error": "Unable to verify payment."}, status=400)

    draft_record = PrivateBookingDraft.objects.filter(
        payment_intent_id=payment_intent_id,
        user=request.user,
    ).first()
    if not draft_record:
        if request.method == "GET":
            messages.error(request, "Draft not found.")
            return redirect("home:payment_failed")
        return JsonResponse({"error": "Draft not found."}, status=400)

    session_draft = _get_private_draft_data(request)
    session_payment_intent_id = (session_draft.get("payment_intent_id") or "").strip()
    if request.method == "POST" and session_payment_intent_id != payment_intent_id:
        return JsonResponse({"error": "Payment session mismatch."}, status=400)
    if request.method == "GET" and session_payment_intent_id and session_payment_intent_id != payment_intent_id:
        messages.error(request, "Payment session mismatch.")
        return redirect("home:payment_failed")

    temp_booking = _build_private_booking_from_draft(draft_record.payload or {}, request.user)
    if draft_record.payload and draft_record.payload.get("discount_code_id"):
        temp_booking.discount_code_id = draft_record.payload.get("discount_code_id")
    payment_summary = _calculate_private_payment_summary(temp_booking, draft_record.payment_currency or settings.STRIPE_CURRENCY or "usd")
    if request.method == "GET" and intent.status in ("processing", "requires_action", "requires_capture"):
        received_amount = intent.get("amount_received") or intent.get("amount") or 0
        intent_currency = (intent.get("currency") or "").lower()
        if int(received_amount) != int(payment_summary["amount_cents"]):
            _mark_private_draft_failed(draft_record, intent.status, "Payment amount mismatch.")
            messages.error(request, "Payment amount mismatch.")
            return redirect("home:payment_failed")
        if intent_currency != payment_summary["currency"]:
            _mark_private_draft_failed(draft_record, intent.status, "Payment currency mismatch.")
            messages.error(request, "Payment currency mismatch.")
            return redirect("home:payment_failed")
        if not _payment_intent_metadata_matches(intent, draft_record, user_id=request.user.id):
            _mark_private_draft_failed(draft_record, intent.status, "Payment metadata mismatch.")
            messages.error(request, "Payment metadata mismatch.")
            return redirect("home:payment_failed")

        draft_record.payment_status = intent.status
        draft_record.save(update_fields=["payment_status"])
        request.session["latest_private_payment_intent_id"] = payment_intent_id
        request.session.pop(DRAFT_SESSION_KEY, None)
        messages.info(request, "Payment submitted. We are waiting for Stripe confirmation.")
        return redirect(f"{reverse('home:payment_success')}?payment_intent_id={payment_intent_id}")

    valid_payment, payment_error = _verify_private_payment_intent(
        intent,
        draft_record,
        payment_summary,
        require_user_id=request.user.id,
    )
    if not valid_payment:
        _mark_private_draft_failed(draft_record, intent.status, payment_error)
        if request.method == "GET":
            messages.error(request, payment_error)
            return redirect("home:payment_failed")
        return JsonResponse({"error": payment_error}, status=400)

    serialized_summary = _serialize_private_payment_summary(payment_summary)
    if draft_record.payment_amount != payment_summary["amount"] or (draft_record.payment_currency or "").lower() != serialized_summary["currency"]:
        _mark_private_draft_failed(draft_record, intent.status, "Draft payment summary mismatch.")
        if request.method == "GET":
            messages.error(request, "Draft payment summary mismatch.")
            return redirect("home:payment_failed")
        return JsonResponse({"error": "Draft payment summary mismatch."}, status=400)

    draft_record.payment_status = intent.status
    draft_record.status = "paid"
    draft_record.save(update_fields=["payment_status", "status"])
    logger.info("Stripe payment verified on client for draft %s", draft_record.id)

    request.session["latest_private_payment_intent_id"] = payment_intent_id
    processing_url = f"{reverse('home:payment_success')}?payment_intent_id={payment_intent_id}"
    request.session.pop(DRAFT_SESSION_KEY, None)

    if request.method == "GET":
        return redirect(processing_url)
    return JsonResponse({"redirect_url": processing_url})


@csrf_exempt
def stripe_webhook(request):
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    except Exception:
        return HttpResponse(status=400)

    event_type = event.get("type")
    event_id = event.get("id")
    data = event.get("data", {}).get("object", {})
    payment_intent_id = data.get("id")

    if not event_id:
        logger.error("Stripe webhook received without event id.")
        return HttpResponse(status=400)

    try:
        with transaction.atomic():
            webhook_event, created = StripeWebhookEvent.objects.select_for_update().get_or_create(
                event_id=event_id,
                defaults={
                    "event_type": event_type,
                    "payment_intent_id": payment_intent_id,
                },
            )
            if not created:
                webhook_event.event_type = event_type
                webhook_event.payment_intent_id = payment_intent_id
                webhook_event.save(update_fields=["event_type", "payment_intent_id", "updated_at"])
                if webhook_event.processed_at:
                    logger.info("Stripe webhook duplicate ignored: %s", event_id)
                    return HttpResponse(status=200)
    except IntegrityError:
        logger.info("Stripe webhook duplicate ignored after integrity error: %s", event_id)
        return HttpResponse(status=200)

    draft_record = None
    if payment_intent_id:
        draft_record = PrivateBookingDraft.objects.filter(payment_intent_id=payment_intent_id).first()

    if not draft_record:
        logger.warning("Stripe webhook: draft not found for intent %s", payment_intent_id)
        return HttpResponse(status=200)

    if event_type == "payment_intent.succeeded":
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id, expand=["payment_method"])
            payload = draft_record.payload or {}
            with transaction.atomic():
                draft_record = PrivateBookingDraft.objects.select_for_update().get(pk=draft_record.pk)
                if PrivateBooking.objects.filter(payment_intent_id=payment_intent_id).exists():
                    booking = PrivateBooking.objects.filter(payment_intent_id=payment_intent_id).first()
                    draft_record.payment_status = data.get("status")
                    draft_record.status = "completed"
                    draft_record.save(update_fields=["payment_status", "status"])
                    _sync_private_booking_invoice(booking, intent)
                else:
                    temp_booking = _build_private_booking_from_draft(payload)
                    if payload.get("user_id"):
                        temp_booking.user_id = payload.get("user_id")
                    if payload.get("discount_code_id"):
                        temp_booking.discount_code_id = payload.get("discount_code_id")
                    payment_summary = _calculate_private_payment_summary(
                        temp_booking,
                        draft_record.payment_currency or settings.STRIPE_CURRENCY or "usd",
                    )
                    valid_payment, payment_error = _verify_private_payment_intent(
                        intent,
                        draft_record,
                        payment_summary,
                        require_user_id=draft_record.user_id,
                    )
                    if not valid_payment:
                        _mark_private_draft_failed(draft_record, intent.status, payment_error)
                        raise ValueError(payment_error)

                    booking = _create_private_booking_from_draft_payload(payload)
                    _apply_private_booking_payment(booking, intent, payment_summary=payment_summary)
                    _sync_private_booking_invoice(booking, intent, payment_summary=payment_summary)
                    draft_record.payment_status = intent.status
                    draft_record.status = "completed"
                    draft_record.save(update_fields=["payment_status", "status"])
                    logger.info("Private booking created from draft %s (booking_id=%s)", draft_record.id, booking.id)

            StripeWebhookEvent.objects.filter(event_id=event_id).update(
                processed_at=timezone.now(),
                last_error="",
            )
        except Exception:
            logger.exception("Stripe webhook processing failed for intent %s event %s", payment_intent_id, event_id)
            StripeWebhookEvent.objects.filter(event_id=event_id).update(last_error=f"Fulfillment failed for {payment_intent_id}")
            return HttpResponse(status=500)
    elif event_type in ("payment_intent.payment_failed", "payment_intent.canceled"):
        draft_record.payment_status = data.get("status")
        draft_record.status = "expired"
        draft_record.save(update_fields=["payment_status", "status"])
        logger.info("Stripe payment not completed for draft %s (status=%s)", draft_record.id, draft_record.payment_status)
        StripeWebhookEvent.objects.filter(event_id=event_id).update(
            processed_at=timezone.now(),
            last_error="",
        )
    else:
        StripeWebhookEvent.objects.filter(event_id=event_id).update(
            processed_at=timezone.now(),
            last_error="",
        )

    return HttpResponse(status=200)

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
        "stripe_currency": (settings.STRIPE_CURRENCY or "sek").lower(),
    })

def private_thank_you(request):
    return render(request, "home/thank_you_page.html")

@login_required
def payment_success(request):
    payment_intent_id = (
        request.GET.get("payment_intent_id")
        or request.session.get("latest_private_payment_intent_id")
        or ""
    ).strip()
    booking = None
    draft_record = None
    fallback_url = (
        reverse("accounts:my_bookimg")
        if request.user.is_authenticated
        else reverse("home:all_services_private")
    )

    if payment_intent_id:
        booking = PrivateBooking.objects.filter(
            payment_intent_id=payment_intent_id,
            user=request.user,
        ).first()
        draft_record = PrivateBookingDraft.objects.filter(
            payment_intent_id=payment_intent_id,
            user=request.user,
        ).first()

    if booking is not None:
        return render(
            request,
            "home/payment_success.html",
            {
                "booking": booking,
                "payment_intent_id": payment_intent_id,
                "fallback_url": reverse(
                    "accounts:view_service_details",
                    args=["private", booking.id],
                ),
            },
        )

    if draft_record and draft_record.status in ("failed", "expired"):
        messages.error(request, "Payment could not be completed.")
        return redirect("home:payment_failed")

    return render(
        request,
        "home/payment_processing.html",
        {
            "payment_intent_id": payment_intent_id,
            "fallback_url": fallback_url,
        },
    )

def payment_failed(request):
    return render(request, "home/payment_failed.html")

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

    cart = request.session.get("private_cart", [])
    selected_services = cart or [service.slug]

    draft = _get_private_draft_data(request)
    draft.update({
        "booking_method": "online",
        "main_category": service.category.slug,
        "selected_services": selected_services,
        "is_urgent": bool(urgent_flag),
        "user_id": request.user.id if request.user.is_authenticated else None,
    })

    if urgent_flag:
        request.session.pop("urgent_booking", None)

    _save_private_draft_data(request, draft)
    return redirect("home:private_booking_services")

def private_booking_services(request):
    draft = _get_private_draft_data(request)

    selected_slugs = draft.get("selected_services") or []
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
        service_answers = draft.get("service_answers") or {}

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

        draft["service_answers"] = service_answers

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
            temp_booking = _build_private_booking_from_draft(draft, request.user)
            pricing = calculate_booking_price(temp_booking)
            return render(request, "home/YourServicesBooking.html", {
                "booking": temp_booking,
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

        draft["addons_selected"] = final_addons


        # ⭐⭐⭐ 2.5) تخزين الـ schedule لو وصل من الصفحة ⭐⭐⭐
        schedules_json = request.POST.get("schedules_json")
        if schedules_json:
            try:
                draft["service_schedules"] = json.loads(schedules_json)
            except:
                draft["service_schedules"] = {}

        # 3) حساب السعر
        temp_booking = _build_private_booking_from_draft(draft, request.user)
        pricing = calculate_booking_price(temp_booking)

        duration_seconds = int(pricing.get("duration_seconds", 0) or 0)
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        draft["duration_hours"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        draft["quoted_duration_minutes"] = int(pricing.get("duration_minutes") or 0)
        draft["pricing_details"] = pricing
        draft["subtotal"] = pricing.get("subtotal", 0) or 0
        draft["rot_discount"] = pricing.get("rot", 0) or 0
        draft["total_price"] = pricing.get("final", 0) or 0
        _save_private_draft_data(request, draft)

        # لو الطلب AJAX → رجّع JSON
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            from django.http import JsonResponse
            return JsonResponse(pricing)

        return redirect("home:private_booking_schedule")

    # GET
    temp_booking = _build_private_booking_from_draft(draft, request.user)
    pricing = calculate_booking_price(temp_booking)
    return render(request, "home/YourServicesBooking.html", {
        "booking": temp_booking,
        "services": services,
        "saved_addons": json.dumps(draft.get("addons_selected") or {}),
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

def private_booking_schedule(request):
    draft = _get_private_draft_data(request)

    if not draft.get("selected_services"):
        cart = request.session.get("private_cart", [])
        if cart:
            draft["selected_services"] = cart
            _save_private_draft_data(request, draft)

    services = PrivateService.objects.filter(slug__in=(draft.get("selected_services") or []))

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
    min_booking_date = timezone.localdate()

    def _render_schedule_page(temp_booking, pricing):
        initial_schedule_state = {
            "mode": temp_booking.schedule_mode or ("same" if len(services) <= 1 else ""),
            "appointment_date": temp_booking.appointment_date.isoformat() if hasattr(temp_booking.appointment_date, "isoformat") else (temp_booking.appointment_date or ""),
            "appointment_time_window": temp_booking.appointment_time_window or "",
            "frequency_type": temp_booking.frequency_type or "",
            "day_work_best": temp_booking.day_work_best or [],
            "special_timing_requests": temp_booking.special_timing_requests or "",
            "end_date": temp_booking.End_Date or "",
            "service_schedules": temp_booking.service_schedules or {},
        }
        return render(request, "home/Private_scheduale.html", {
            "booking": temp_booking,
            "services": services,
            "date_rules": date_rules_json,
            "schedule_rules": schedule_rules_json,
            "pricing": pricing,
            "initial_schedule_state": json.dumps(initial_schedule_state, cls=DjangoJSONEncoder),
            "min_booking_date": min_booking_date.isoformat(),
        })

    # -----------------------------
    # 2) POST – تخزين البيانات
    # -----------------------------
    if request.method == "POST":
        print(1)
        # MODE
        mode = request.POST.get("schedule_mode")
        draft["schedule_mode"] = mode

        # ---------------- SAME MODE ----------------
        if mode == "same":
            print(2)
            # تاريخ
            date = request.POST.get("appointment_date")
            date_obj = parse_date(date) if date else None
            draft["appointment_date"] = date_obj.isoformat() if date_obj else None
            print(draft.get("appointment_date"))
            if date_obj and _date_is_before_today(date_obj):
                messages.error(request, "Booking date cannot be before today. Please choose today or a future date.")
                temp_booking = _build_private_booking_from_draft(draft, request.user)
                pricing = calculate_booking_price(temp_booking)
                return _render_schedule_page(temp_booking, pricing)
            # وقت
            time_window = request.POST.get("appointment_time_window")
            draft["appointment_time_window"] = time_window
            print(draft.get("appointment_time_window"))
            # Frequency
            frequency = request.POST.get("frequency_type")
            draft["frequency_type"] = frequency
            print(draft.get("frequency_type"))
            # أيام العمل
            days_json = request.POST.get("day_work_best")
            draft["day_work_best"] = json.loads(days_json) if days_json else []
            print(draft.get("day_work_best"))
            # Special timing
            special = request.POST.get("special_timing_requests")
            draft["special_timing_requests"] = special
            
            # End Date
            end_date = request.POST.get("End_Date")
            draft["End_Date"] = end_date if end_date else None
            end_date_obj = parse_date(end_date) if end_date else None
            if end_date_obj and _date_is_before_today(end_date_obj):
                messages.error(request, "End date must be today or a future date.")
                temp_booking = _build_private_booking_from_draft(draft, request.user)
                pricing = calculate_booking_price(temp_booking)
                return _render_schedule_page(temp_booking, pricing)
            if date_obj and end_date_obj and end_date_obj < date_obj:
                messages.error(request, "End date cannot be earlier than your booking date.")
                temp_booking = _build_private_booking_from_draft(draft, request.user)
                pricing = calculate_booking_price(temp_booking)
                return _render_schedule_page(temp_booking, pricing)

            # تفريغ الجدول المنفصل
            draft["service_schedules"] = {}

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

            for service_schedule in schedules.values():
                if not isinstance(service_schedule, dict):
                    continue
                service_date = parse_date(service_schedule.get("date") or "")
                if service_date and _date_is_before_today(service_date):
                    messages.error(request, "Each service must be scheduled for today or a future date.")
                    draft["service_schedules"] = schedules
                    temp_booking = _build_private_booking_from_draft(draft, request.user)
                    pricing = calculate_booking_price(temp_booking)
                    return _render_schedule_page(temp_booking, pricing)
                service_end_date_raw = service_schedule.get("end_date") or ""
                service_end_date = parse_date(service_end_date_raw) if service_end_date_raw else None
                if service_end_date and _date_is_before_today(service_end_date):
                    messages.error(request, "Each end date must be today or a future date.")
                    draft["service_schedules"] = schedules
                    temp_booking = _build_private_booking_from_draft(draft, request.user)
                    pricing = calculate_booking_price(temp_booking)
                    return _render_schedule_page(temp_booking, pricing)
                if service_date and service_end_date and service_end_date < service_date:
                    messages.error(request, "A service end date cannot be earlier than its booking date.")
                    draft["service_schedules"] = schedules
                    temp_booking = _build_private_booking_from_draft(draft, request.user)
                    pricing = calculate_booking_price(temp_booking)
                    return _render_schedule_page(temp_booking, pricing)

            draft["service_schedules"] = schedules

            # تفريغ قيم المود "same"
            draft["appointment_date"] = None
            draft["appointment_time_window"] = None
            draft["frequency_type"] = None
            draft["day_work_best"] = []
            draft["special_timing_requests"] = None
            draft["End_Date"] = None

        # -----------------------------
        # 3) إعادة حساب السعر
        # -----------------------------
        temp_booking = _build_private_booking_from_draft(draft, request.user)
        pricing = calculate_booking_price(temp_booking)
        duration_minutes = int(pricing.get("duration_minutes") or 0)

        invalid_price = any((service.price or 0) <= 0 for service in services)
        if invalid_price:
            messages.error(request, "This service is not bookable yet. Please choose another service.")
            return _render_schedule_page(temp_booking, pricing)

        if duration_minutes <= 0:
            messages.error(request, "Please complete required options to calculate a valid duration.")
            return _render_schedule_page(temp_booking, pricing)

        if mode == "same":
            if not draft.get("appointment_date"):
                messages.error(request, "Please select a valid appointment date.")
                return _render_schedule_page(temp_booking, pricing)
            appointment_date_obj = parse_date(draft.get("appointment_date")) if draft.get("appointment_date") else None
            if appointment_date_obj and _date_is_before_today(appointment_date_obj):
                messages.error(request, "Please choose today or a future date for your booking.")
                return _render_schedule_page(temp_booking, pricing)
            end_date_obj = parse_date(draft.get("End_Date")) if draft.get("End_Date") else None
            if end_date_obj and _date_is_before_today(end_date_obj):
                messages.error(request, "End date must be today or a future date.")
                return _render_schedule_page(temp_booking, pricing)
            if appointment_date_obj and end_date_obj and end_date_obj < appointment_date_obj:
                messages.error(request, "End date cannot be earlier than your booking date.")
                return _render_schedule_page(temp_booking, pricing)
            time_hint = draft.get("appointment_time_window") or ""
            time_candidates = temp_booking._parse_time_candidates(time_hint)
            if not time_candidates:
                messages.error(request, "Please select a valid time window.")
                return _render_schedule_page(temp_booking, pricing)
            start_time = time_candidates[0]
            tz = timezone.get_current_timezone()
            if appointment_date_obj:
                scheduled_at = timezone.make_aware(
                    datetime.combine(appointment_date_obj, start_time),
                    tz
                )
                draft["scheduled_at"] = scheduled_at.isoformat()
            else:
                draft["scheduled_at"] = None
        elif mode == "per_service":
            schedules = draft.get("service_schedules") or {}
            for service in services:
                schedule = schedules.get(service.slug) or {}
                service_date_raw = schedule.get("date")
                service_date = parse_date(service_date_raw) if service_date_raw else None
                if not service_date:
                    messages.error(request, f"Please choose a valid date for {service.title}.")
                    return _render_schedule_page(temp_booking, pricing)
                if _date_is_before_today(service_date):
                    messages.error(request, f"{service.title} must be scheduled for today or a future date.")
                    return _render_schedule_page(temp_booking, pricing)
                service_end_date_raw = schedule.get("end_date") or ""
                service_end_date = parse_date(service_end_date_raw) if service_end_date_raw else None
                if service_end_date and _date_is_before_today(service_end_date):
                    messages.error(request, f"End date for {service.title} must be today or a future date.")
                    return _render_schedule_page(temp_booking, pricing)
                if service_end_date and service_end_date < service_date:
                    messages.error(request, f"End date for {service.title} cannot be earlier than its booking date.")
                    return _render_schedule_page(temp_booking, pricing)
        else:
            draft["scheduled_at"] = None

        draft["quoted_duration_minutes"] = duration_minutes
        draft["pricing_details"] = pricing
        draft["total_price"] = pricing["final"]
        draft["subtotal"] = pricing["subtotal"]
        draft["rot_discount"] = pricing["rot"]

        _save_private_draft_data(request, draft)

        return redirect("home:private_booking_checkout")

    # -----------------------------
    # 3) Render
    # -----------------------------
    print(4)
    temp_booking = _build_private_booking_from_draft(draft, request.user)
    return _render_schedule_page(temp_booking, calculate_booking_price(temp_booking))


def private_price_api(request):
    draft = _get_private_draft_data(request)

    if not draft.get("selected_services"):
        cart = request.session.get("private_cart", [])
        if cart:
            draft["selected_services"] = cart
            _save_private_draft_data(request, draft)

    booking = _build_private_booking_from_draft(draft, request.user)

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
        "currency": pricing.get("currency", (settings.STRIPE_CURRENCY or "sek").lower()),
        "duration_hours": pricing.get("duration_hours", 0),
        "duration_seconds": pricing.get("duration_seconds", 0),
    })


def private_provider_availability_api(request):
    date_str = request.GET.get("date")
    if not date_str:
        return JsonResponse({"error": "Missing date"}, status=400)

    date_obj = parse_date(date_str)
    if not date_obj:
        return JsonResponse({"error": "Invalid date"}, status=400)

    draft = _get_private_draft_data(request)
    if not draft.get("selected_services"):
        return JsonResponse({"error": "Missing booking details"}, status=400)

    booking = _build_private_booking_from_draft(draft, request.user)
    booking.appointment_date = date_obj

    duration_minutes = int(booking.quoted_duration_minutes or 0)
    if duration_minutes <= 0:
        temp_booking = _build_private_booking_from_draft(draft, request.user)
        pricing = calculate_booking_price(temp_booking)
        duration_minutes = int(pricing.get("duration_minutes") or 0)

    if duration_minutes <= 0:
        return JsonResponse({"error": "Invalid duration"}, status=400)

    booking.quoted_duration_minutes = duration_minutes

    try:
        slot_size = int(request.GET.get("slot_size", 30))
    except ValueError:
        slot_size = 30
    slot_size = max(5, min(slot_size, 120))

    providers = select_nearest_provider(booking, date_obj, slot_size_minutes=slot_size)

    data = []
    for provider, earliest in providers:
        slots = generate_slots(
            provider,
            date_obj,
            duration_minutes,
            slot_size_minutes=slot_size,
        )
        data.append({
            "provider_id": provider.id,
            "provider_name": provider.get_full_name() or provider.username,
            "earliest_slot": earliest.isoformat() if earliest else None,
            "slots": [s.isoformat() for s in slots],
            "available_after_minutes": provider_available_after_minutes(provider, timezone.now()),
        })

    return JsonResponse({
        "date": date_str,
        "duration_minutes": duration_minutes,
        "slot_size_minutes": slot_size,
        "providers": data,
    })


@csrf_exempt
def private_update_answer_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    draft = _get_private_draft_data(request)

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

    answers = draft.get("service_answers") or {}
    answers.setdefault(service_slug, {})
    answers[service_slug][field] = parsed_value

    draft["service_answers"] = answers
    temp_booking = _build_private_booking_from_draft(draft, request.user)
    pricing = calculate_booking_price(temp_booking)
    duration_seconds = int(pricing.get("duration_seconds", 0) or 0)
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    draft["duration_hours"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    draft["quoted_duration_minutes"] = int(pricing.get("duration_minutes") or 0)
    draft["pricing_details"] = pricing
    _save_private_draft_data(request, draft)

    return JsonResponse({"success": True})



@csrf_exempt
def private_update_addons_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    draft = _get_private_draft_data(request)

    raw = request.POST.get("addons_json", "{}")

    try:
        addons = json.loads(raw)
    except:
        addons = {}

    draft["addons_selected"] = addons
    temp_booking = _build_private_booking_from_draft(draft, request.user)
    pricing = calculate_booking_price(temp_booking)
    duration_seconds = int(pricing.get("duration_seconds", 0) or 0)
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    draft["duration_hours"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    draft["quoted_duration_minutes"] = int(pricing.get("duration_minutes") or 0)
    draft["subtotal"] = pricing.get("subtotal", 0) or 0
    draft["total_price"] = pricing.get("final", 0) or 0
    draft["rot_discount"] = pricing.get("rot", 0) or 0
    draft["pricing_details"] = pricing
    _save_private_draft_data(request, draft)

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
