from django.utils import timezone
from django.utils.translation import gettext as _
import datetime
from typing import Counter
from django.db.models import Q
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date

from django.shortcuts import render, redirect , get_object_or_404
from .forms import CustomerForm , CustomerBasicInfoForm , CustomerLocationForm ,IncidentForm , CustomerNoteForm , PaymentMethodForm ,CommunicationPreferenceForm, ServiceCommentForm, ServiceReviewForm, PasswordResetRequestForm, OTPVerifyForm, SetNewPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.contrib.auth import logout
from accounts.models import PointsTransaction

from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.urls import reverse_lazy, reverse
from urllib.parse import urlencode
from django.contrib.auth.forms import PasswordChangeForm
from django.urls import reverse
from django.contrib.auth import logout, get_user_model
from django.contrib.auth.decorators import login_required
from .models import (
    Customer,
    CustomerLocation,
    CustomerPreferences,
    Incident,
    CustomerNote,
    LoyaltyTier,
    PaymentMethod,
    Invoice,
    CommunicationPreference,
    BookingNote,
    PointsTransaction,
    Promotion,
    Referral,
    Reward,
    ServiceComment,
    ServiceReview,
    Subscription,
    BookingRequestFix,
    BookingRequestFixAttachment,
    BookingChecklistItem,
    CustomerNotification,
    ProviderAdminMessage,
    ProviderProfile,
    PasswordResetOTP,
)
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import logging
from smtplib import SMTPException
import stripe
from .email_utils import verification_email_connection, verification_from_email
from home.models import (
    BookingStatusHistory,
    BookingTimeline,
    BusinessBooking,
    BusinessService,
    BookingMedia,
    PrivateBooking,
    PrivateService,
)
from .models import Customer, CustomerLocation, Incident  , ChatThread, ChatMessage ,BookingChecklist
from .forms import (
    CustomerForm,
    CustomerBasicInfoForm,
    CustomerLocationForm,
    IncidentForm,
    BookingChecklistForm,
    PasswordResetRequestForm,
    OTPVerifyForm,
    SetNewPasswordForm,
)
from django.http import HttpResponse, JsonResponse
import json
from django.db.models import Avg, Count
User = get_user_model()
from .forms import ProviderProfileForm, ProviderLocationForm
logger = logging.getLogger(__name__)


def _pdf_escape(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def _wrap_pdf_text(text, max_chars=78):
    words = str(text or "").split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _build_invoice_pdf(title, meta_rows, section_rows, footer_lines=None):
    page_width = 612
    page_height = 792
    margin_left = 52
    margin_right = 560
    top_y = 748
    line_height = 18
    row_gap = 8
    section_gap = 18

    pages = []
    current_page = []
    current_y = top_y

    def push_page():
        nonlocal current_page, current_y
        pages.append(current_page)
        current_page = []
        current_y = top_y

    def ensure_space(height_needed):
        nonlocal current_y
        if current_y - height_needed < 70:
            push_page()

    def add_text(text, x, y, font_key="F1", font_size=12):
        safe_text = _pdf_escape(text)
        current_page.append(f"BT /{font_key} {font_size} Tf 1 0 0 1 {x} {y} Tm ({safe_text}) Tj ET")

    def add_rule(y):
        current_page.append(f"{margin_left} {y} m {margin_right} {y} l S")

    title_lines = _wrap_pdf_text(title, max_chars=30)
    ensure_space(56)
    for idx, line in enumerate(title_lines):
        add_text(line, margin_left, current_y - (idx * 26), font_key="F2", font_size=24 if idx == 0 else 20)
    current_y -= 38 + (max(0, len(title_lines) - 1) * 24)
    add_rule(current_y)
    current_y -= 24

    for label, value in meta_rows:
        wrapped_value = _wrap_pdf_text(value, max_chars=46)
        row_height = max(line_height * len(wrapped_value), line_height) + row_gap
        ensure_space(row_height)
        add_text(label, margin_left, current_y, font_key="F2", font_size=11)
        for idx, line in enumerate(wrapped_value):
            add_text(line, 220, current_y - (idx * line_height), font_key="F1", font_size=11)
        current_y -= row_height

    current_y -= 6
    add_rule(current_y)
    current_y -= 22
    add_text("Details", margin_left, current_y, font_key="F2", font_size=14)
    current_y -= 24

    for label, value in section_rows:
        wrapped_value = _wrap_pdf_text(value, max_chars=58)
        row_height = max(line_height * len(wrapped_value), line_height)
        ensure_space(row_height + row_gap)
        add_text(label, margin_left, current_y, font_key="F2", font_size=11)
        for idx, line in enumerate(wrapped_value):
            add_text(line, margin_left + 130, current_y - (idx * line_height), font_key="F1", font_size=11)
        current_y -= row_height + row_gap

    if footer_lines:
        current_y -= 8
        add_rule(current_y)
        current_y -= 22
        for footer_line in footer_lines:
            wrapped_footer = _wrap_pdf_text(footer_line, max_chars=82)
            ensure_space((len(wrapped_footer) * line_height) + 6)
            for idx, line in enumerate(wrapped_footer):
                add_text(line, margin_left, current_y - (idx * line_height), font_key="F1", font_size=10)
            current_y -= (len(wrapped_footer) * line_height) + 6

    if current_page:
        push_page()

    objects = []

    def add_object(payload):
        objects.append(payload)
        return len(objects)

    font_regular_obj = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold_obj = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    page_ids = []

    for page_commands in pages:
        content_stream = ("\n".join(page_commands)).encode("latin-1", "replace")
        content_obj = add_object(
            f"<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1")
            + content_stream
            + b"\nendstream"
        )
        page_obj = add_object(
            (
                "<< /Type /Page /Parent {parent} 0 R /MediaBox [0 0 "
                f"{page_width} {page_height}] /Resources << /Font << /F1 {font_regular_obj} 0 R /F2 {font_bold_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("latin-1")
        )
        page_ids.append(page_obj)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_obj = add_object(
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1")
    )
    catalog_obj = add_object(
        f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode("latin-1")
    )

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]

    for index, payload in enumerate(objects, start=1):
        payload = payload.replace(b"{parent}", f"{pages_obj}".encode("latin-1"))
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("latin-1"))
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_obj} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("latin-1")
    )
    return bytes(pdf)
# ======================================================
# AUTH
# ======================================================
BOOKING_NEXT_SESSION_KEY = "post_auth_redirect_url"


class RememberMeLoginView(LoginView):
    def dispatch(self, request, *args, **kwargs):
        next_url = request.GET.get("next") or request.POST.get("next") or ""
        if next_url:
            request.session[BOOKING_NEXT_SESSION_KEY] = next_url
            request.session.modified = True
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        next_url = (
            self.request.POST.get("next")
            or self.request.GET.get("next")
            or self.request.session.pop(BOOKING_NEXT_SESSION_KEY, "")
        )
        if next_url:
            self.request.session.modified = True
            return next_url
        return super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = self.request.POST.get("remember_me") == "on"
        if remember:
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            self.request.session.set_expiry(0)
        return response


def _humanize_service_name(value):
    text = (value or "").strip()
    if not text:
        return ""
    if "-" in text or "_" in text:
        return text.replace("-", " ").replace("_", " ").strip().title()
    return text


def _get_private_service_title_map(bookings):
    service_slugs = {
        slug
        for booking in bookings
        for slug in (booking.selected_services or [])
        if isinstance(slug, str) and slug.strip()
    }
    return dict(
        PrivateService.objects.filter(slug__in=service_slugs).values_list("slug", "title")
    )


def _get_private_booking_title(booking, private_service_titles):
    resolved_titles = [
        private_service_titles.get(slug, _humanize_service_name(slug))
        for slug in (booking.selected_services or [])
        if isinstance(slug, str) and slug.strip()
    ]
    return ", ".join(resolved_titles) or "Private Service"


def _booking_table_status_label(status_value):
    return "Scheduled" if status_value == "upcoming" else status_value.title()


def _build_private_booking_checklist_templates(booking):
    selected_slugs = booking.selected_services or []
    services = {
        service.slug: service
        for service in PrivateService.objects.filter(slug__in=selected_slugs).prefetch_related("cards")
    }
    templates = []

    for service_order, service_slug in enumerate(selected_slugs):
        service = services.get(service_slug)
        if service is None:
            continue

        service_templates = []
        for group_order, card in enumerate(service.cards.all()):
            for sort_order, item_label in enumerate(card.items()):
                service_templates.append({
                    "service_slug": service.slug,
                    "service_title": service.title,
                    "service_order": service_order,
                    "group_title": card.title or service.title,
                    "group_order": group_order,
                    "item_label": item_label,
                    "sort_order": sort_order,
                })

        if not service_templates:
            service_templates.append({
                "service_slug": service.slug,
                "service_title": service.title,
                "service_order": service_order,
                "group_title": service.title,
                "group_order": 0,
                "item_label": f"Complete {service.title}",
                "sort_order": 0,
            })

        templates.extend(service_templates)

    return templates


def _build_business_booking_checklist_templates(booking):
    requested_titles = []
    if booking.selected_service:
        requested_titles.append(str(booking.selected_service).strip())
    elif booking.selected_bundle and booking.selected_bundle.title:
        requested_titles.append(str(booking.selected_bundle.title).strip())
    for value in (booking.services_needed or []):
        text = str(value).strip()
        if text:
            requested_titles.append(text)

    deduped_titles = []
    seen = set()
    for title in requested_titles:
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped_titles.append(title)

    if not deduped_titles:
        deduped_titles.append("Business Service")

    services = {
        service.title.lower(): service
        for service in BusinessService.objects.filter(title__in=deduped_titles).prefetch_related("cards")
    }
    templates = []

    for service_order, raw_title in enumerate(deduped_titles):
        service = services.get(raw_title.lower())
        service_title = service.title if service else raw_title
        service_templates = []

        if service is not None:
            for group_order, card in enumerate(service.cards.all()):
                for sort_order, item_label in enumerate(card.items()):
                    service_templates.append({
                        "service_slug": "",
                        "service_title": service_title,
                        "service_order": service_order,
                        "group_title": card.title or service_title,
                        "group_order": group_order,
                        "item_label": item_label,
                        "sort_order": sort_order,
                    })

        if not service_templates:
            service_templates.append({
                "service_slug": "",
                "service_title": service_title or "Business Service",
                "service_order": service_order,
                "group_title": service_title or "Business Service",
                "group_order": 0,
                "item_label": f"Complete {service_title or 'business service'}",
                "sort_order": 0,
            })

        templates.extend(service_templates)

    return templates


def _ensure_booking_checklist_items(booking, booking_type):
    filter_kwargs = {
        "booking_private": booking,
    } if booking_type == "private" else {
        "booking_business": booking,
    }

    items = list(
        BookingChecklistItem.objects.filter(**filter_kwargs)
        .select_related("completed_by")
        .order_by("service_order", "group_order", "sort_order", "id")
    )
    if items:
        return items

    templates = (
        _build_private_booking_checklist_templates(booking)
        if booking_type == "private"
        else _build_business_booking_checklist_templates(booking)
    )
    if not templates:
        return items

    BookingChecklistItem.objects.bulk_create([
        BookingChecklistItem(
            booking_private=booking if booking_type == "private" else None,
            booking_business=booking if booking_type == "business" else None,
            service_slug=item["service_slug"],
            service_title=item["service_title"],
            service_order=item["service_order"],
            group_title=item["group_title"],
            group_order=item["group_order"],
            item_label=item["item_label"],
            sort_order=item["sort_order"],
        )
        for item in templates
    ])
    return list(
        BookingChecklistItem.objects.filter(**filter_kwargs)
        .select_related("completed_by")
        .order_by("service_order", "group_order", "sort_order", "id")
    )


def _group_checklist_items(items):
    service_sections = []
    service_map = {}

    for item in items:
        service_key = item.service_title or "Checklist"
        if service_key not in service_map:
            service_map[service_key] = {
                "service_title": service_key,
                "groups": [],
                "_group_map": {},
            }
            service_sections.append(service_map[service_key])

        section = service_map[service_key]
        group_key = item.group_title or service_key
        if group_key not in section["_group_map"]:
            section["_group_map"][group_key] = {
                "group_title": group_key,
                "items": [],
            }
            section["groups"].append(section["_group_map"][group_key])

        section["_group_map"][group_key]["items"].append(item)

    for section in service_sections:
        section.pop("_group_map", None)

    return service_sections


OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_LOCK_MINUTES = 15
OTP_RESEND_COOLDOWN_SECONDS = 60
RESET_SESSION_TTL_SECONDS = 15 * 60


def _normalize_email(email):
    return (email or "").strip().lower()


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _get_or_create_stripe_customer(customer):
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


def _get_latest_active_otp(email):
    now = timezone.now()
    return (
        PasswordResetOTP.objects.filter(
            email=email,
            is_used=False,
            expires_at__gt=now,
        ).filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now))
        .order_by("-created_at")
        .first()
    )


def _is_locked_for(email, ip_address):
    now = timezone.now()
    email_lock = PasswordResetOTP.objects.filter(email=email, locked_until__gt=now).exists()
    if email_lock:
        return True
    if ip_address:
        ip_lock = PasswordResetOTP.objects.filter(ip_address=ip_address, locked_until__gt=now).exists()
        return ip_lock
    return False


def _send_reset_code(email, user, request):
    now = timezone.now()
    ip_address = _get_client_ip(request)
    if _is_locked_for(email, ip_address):
        return False
    latest_email = PasswordResetOTP.objects.filter(email=email).order_by("-created_at").first()
    latest_ip = (
        PasswordResetOTP.objects.filter(ip_address=ip_address).order_by("-created_at").first()
        if ip_address
        else None
    )
    if latest_email and latest_email.last_sent_at and (now - latest_email.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
        return False
    if latest_ip and latest_ip.last_sent_at and (now - latest_ip.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
        return False

    PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)
    otp_obj, code = PasswordResetOTP.create_otp(
        email=email,
        user=user,
        ip_address=ip_address,
        ttl_minutes=OTP_TTL_MINUTES,
    )

    subject = _("رمز إعادة تعيين كلمة المرور")
    context = {"code": code, "ttl": OTP_TTL_MINUTES}
    text_body = render_to_string("accounts/emails/password_reset_code.txt", context)
    html_body = render_to_string("accounts/emails/password_reset_code.html", context)
    message = EmailMultiAlternatives(
        subject,
        text_body,
        verification_from_email(),
        [email],
        connection=verification_email_connection(),
    )
    message.attach_alternative(html_body, "text/html")
    try:
        connection = verification_email_connection()
        connection.open()
        connection.close()
        message.send(fail_silently=False)
    except SMTPException:
        logger.exception("SMTP error while sending password reset code to %s", email)
        raise
    return True


def _send_signup_code(email, user, request):
    now = timezone.now()
    ip_address = _get_client_ip(request)
    if _is_locked_for(email, ip_address):
        return False

    latest_email = PasswordResetOTP.objects.filter(email=email).order_by("-created_at").first()
    latest_ip = (
        PasswordResetOTP.objects.filter(ip_address=ip_address).order_by("-created_at").first()
        if ip_address
        else None
    )
    if latest_email and latest_email.last_sent_at and (now - latest_email.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
        return False
    if latest_ip and latest_ip.last_sent_at and (now - latest_ip.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
        return False

    PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)
    otp_obj, code = PasswordResetOTP.create_otp(
        email=email,
        user=user,
        ip_address=ip_address,
        ttl_minutes=OTP_TTL_MINUTES,
    )

    subject = _("Email verification code")
    context = {"code": code, "ttl": OTP_TTL_MINUTES}
    text_body = render_to_string("accounts/emails/signup_verification_code.txt", context)
    html_body = render_to_string("accounts/emails/signup_verification_code.html", context)
    message = EmailMultiAlternatives(
        subject,
        text_body,
        verification_from_email(),
        [email],
        connection=verification_email_connection(),
    )
    message.attach_alternative(html_body, "text/html")
    try:
        connection = verification_email_connection()
        connection.open()
        connection.close()
        message.send(fail_silently=False)
    except SMTPException:
        logger.exception("SMTP error while sending signup verification code to %s", email)
        raise
    return True


def password_reset_request(request):
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = _normalize_email(form.cleaned_data["email"])
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            form.add_error("email", _("No account found with this email."))
            return render(
                request,
                "accounts/password_reset_request.html",
                {"form": form},
            )
        _send_reset_code(email, user, request)

        request.session["password_reset_email"] = email
        messages.success(request, _("We sent a verification code to your email."))
        return redirect("password_reset_verify")

    return render(
        request,
        "accounts/password_reset_request.html",
        {"form": form},
    )


def password_reset_verify(request):
    email = _normalize_email(request.session.get("password_reset_email"))
    if not email:
        return redirect("password_reset")

    form = OTPVerifyForm(request.POST or None)
    if request.method == "POST":
        if _is_locked_for(email, _get_client_ip(request)):
            form.add_error("code", _("تم تجاوز عدد المحاولات. حاول لاحقاً."))
            return render(
                request,
                "accounts/password_reset_verify.html",
                {"form": form, "email": email, "cooldown_seconds": 0},
            )

        if request.POST.get("resend") == "1":
            user = User.objects.filter(email__iexact=email).first()
            if user:
                _send_reset_code(email, user, request)
            messages.success(request, _("We sent a verification code to your email."))
            return redirect("password_reset_verify")

        if form.is_valid():
            otp = _get_latest_active_otp(email)
            if not otp:
                latest = (
                    PasswordResetOTP.objects.filter(email=email, is_used=False)
                    .order_by("-created_at")
                    .first()
                )
                if latest and latest.is_locked():
                    form.add_error("code", _("تم تجاوز عدد المحاولات. حاول لاحقاً."))
                elif latest and latest.is_expired():
                    latest.is_used = True
                    latest.save(update_fields=["is_used"])
                    form.add_error("code", _("رمز غير صالح أو منتهي."))
                else:
                    form.add_error("code", _("رمز غير صالح أو منتهي."))
            elif not otp.check_code(form.cleaned_data["code"]):
                otp.attempts += 1
                if otp.attempts >= OTP_MAX_ATTEMPTS:
                    otp.locked_until = timezone.now() + datetime.timedelta(minutes=OTP_LOCK_MINUTES)
                otp.save(update_fields=["attempts", "locked_until"])
                form.add_error("code", _("رمز غير صحيح. حاول مرة أخرى."))
            else:
                otp.is_used = True
                otp.save(update_fields=["is_used"])
                PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)
                request.session["password_reset_verified_email"] = email
                request.session["password_reset_verified_at"] = int(timezone.now().timestamp())
                return redirect("password_reset_new")

    latest = PasswordResetOTP.objects.filter(email=email).order_by("-created_at").first()
    cooldown_seconds = 0
    if latest and latest.last_sent_at:
        elapsed = (timezone.now() - latest.last_sent_at).total_seconds()
        cooldown_seconds = max(0, OTP_RESEND_COOLDOWN_SECONDS - int(elapsed))

    return render(
        request,
        "accounts/password_reset_verify.html",
        {"form": form, "email": email, "cooldown_seconds": cooldown_seconds},
    )


def password_reset_new(request):
    email = _normalize_email(request.session.get("password_reset_verified_email"))
    verified_at = request.session.get("password_reset_verified_at")
    if not email or not verified_at:
        return redirect("password_reset")

    age = timezone.now().timestamp() - int(verified_at)
    if age > RESET_SESSION_TTL_SECONDS:
        request.session.pop("password_reset_verified_email", None)
        request.session.pop("password_reset_verified_at", None)
        messages.error(request, _("انتهت مدة التحقق. اطلب رمزاً جديداً."))
        return redirect("password_reset")

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        messages.error(request, _("لا يوجد حساب لهذا البريد."))
        return redirect("password_reset")

    form = SetNewPasswordForm(request.POST or None, user=user)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password1"])
        user.save()
        PasswordResetOTP.objects.filter(email=email).update(is_used=True)

        request.session.pop("password_reset_email", None)
        request.session.pop("password_reset_verified_email", None)
        request.session.pop("password_reset_verified_at", None)

        query = urlencode({"email": email})
        return redirect(f"{reverse('password_reset_success')}?{query}")

    return render(
        request,
        "accounts/password_reset_new.html",
        {"form": form, "email": email},
    )


def password_reset_success(request):
    return render(request, "accounts/password_reset_success.html")


def google_login_start(request):
    next_url = request.GET.get("next") or ""
    if next_url:
        request.session[BOOKING_NEXT_SESSION_KEY] = next_url
        request.session.modified = True

    try:
        from allauth.socialaccount.models import SocialApp
        has_google = SocialApp.objects.filter(provider="google").exists()
    except Exception:
        has_google = False

    if not has_google:
        messages.error(request, "Google login is not configured yet.")
        return redirect("login")

    try:
        from allauth.socialaccount.providers.google.views import oauth2_login
    except Exception:
        messages.error(request, "Google login is not available right now.")
        return redirect("login")

    return oauth2_login(request)
# ======================================================
# SIGN UP
# ======================================================
def sign_up(request):
    ref_code = request.GET.get("ref")
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url:
        request.session[BOOKING_NEXT_SESSION_KEY] = next_url
        request.session.modified = True
    locked_email = None
    if request.user.is_authenticated and request.user.email:
        locked_email = request.user.email

    if request.method == "POST":
        form = CustomerForm(request.POST, request.FILES, locked_email=locked_email)

        if form.is_valid():
            email = _normalize_email(form.cleaned_data["email"])
            password = form.cleaned_data["password"]

            # 1️⃣ إنشاء User
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user and existing_user.is_active:
                form.add_error("email", "Email is already registered.")
                return render(request, "registration/sign_up.html", {"form": form, "next": next_url})

            if existing_user and not existing_user.is_active:
                existing_user.delete()

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        is_active=False,
                    )
            except IntegrityError:
                form.add_error("email", "Email is already registered.")
                return render(request, "registration/sign_up.html", {"form": form, "next": next_url})

            # 2️⃣ إنشاء Customer
            customer = form.save(commit=False)
            customer.user = user
            customer.email = email
            customer.save()
            form.save_m2m()

            region = form.cleaned_data.get("region", "")
            contact_name = form.cleaned_data.get("contact_name", "")
            contact_phone = form.cleaned_data.get("contact_phone", "") or customer.phone
            entry_code = form.cleaned_data.get("entry_code", "")
            parking_notes = form.cleaned_data.get("parking_notes", "")

            street_address = customer.display_address() or customer.full_address or ""
            if customer.house_num and customer.house_num not in street_address:
                street_address = f"{street_address} {customer.house_num}".strip()

            location_country = CustomerLocation.normalize_country_choice(customer.country)

            CustomerLocation.objects.create(
                customer=customer,
                address_type="home",
                street_address=street_address or "-",
                city=customer.display_city(),
                region=region or "-",
                postal_code=customer.display_postal_code(),
                country=location_country,
                contact_name=contact_name,
                contact_phone=contact_phone,
                entry_code=entry_code or customer.display_entry_code(),
                parking_notes=parking_notes or customer.display_parking_notes(),
                is_primary=True,
            )

            # 3️⃣ REFERRAL LOGIC
            if ref_code:
                referral = Referral.objects.filter(
                    code=ref_code,
                    referred_user__isnull=True
                ).first()

                if referral:
                    referral.referred_user = user
                    referral.save()

                    customer.has_referral_discount = True
                    customer.save(update_fields=["has_referral_discount"])

            try:
                _send_signup_code(email, user, request)
            except SMTPException:
                user.delete()
                messages.error(request, "Could not send the verification code right now. Please try again.")
                return render(request, "registration/sign_up.html", {"form": form, "next": next_url})

            request.session["signup_verification_email"] = email
            request.session["signup_next_url"] = next_url
            messages.success(request, _("We sent a verification code to your email."))
            return redirect("accounts:signup_verify")
    else:
        form = CustomerForm(locked_email=locked_email)

    return render(request, "registration/sign_up.html", {"form": form, "next": next_url})


def signup_verify(request):
    email = _normalize_email(request.session.get("signup_verification_email"))
    next_url = request.session.get("signup_next_url") or ""
    if not email:
        return redirect("accounts:sign_up")

    user = User.objects.filter(email__iexact=email, is_active=False).first()
    if not user:
        request.session.pop("signup_verification_email", None)
        request.session.pop("signup_next_url", None)
        messages.info(request, "This account is already verified. Please sign in.")
        login_url = reverse("login")
        query_data = {"email": email}
        if next_url:
            query_data["next"] = next_url
        return redirect(f"{login_url}?{urlencode(query_data)}")

    form = OTPVerifyForm(request.POST or None)
    if request.method == "POST":
        if _is_locked_for(email, _get_client_ip(request)):
            form.add_error("code", _("Too many attempts. Please try again later."))
            return render(
                request,
                "accounts/signup_verify.html",
                {"form": form, "email": email, "cooldown_seconds": 0},
            )

        if request.POST.get("resend") == "1":
            try:
                _send_signup_code(email, user, request)
            except SMTPException:
                messages.error(request, _("Could not send the verification code right now."))
            else:
                messages.success(request, _("We sent a verification code to your email."))
            return redirect("accounts:signup_verify")

        if form.is_valid():
            otp = _get_latest_active_otp(email)
            if not otp:
                latest = PasswordResetOTP.objects.filter(email=email, is_used=False).order_by("-created_at").first()
                if latest and latest.is_locked():
                    form.add_error("code", _("Too many attempts. Please try again later."))
                elif latest and latest.is_expired():
                    latest.is_used = True
                    latest.save(update_fields=["is_used"])
                    form.add_error("code", _("Code is invalid or expired."))
                else:
                    form.add_error("code", _("Code is invalid or expired."))
            elif not otp.check_code(form.cleaned_data["code"]):
                otp.attempts += 1
                if otp.attempts >= OTP_MAX_ATTEMPTS:
                    otp.locked_until = timezone.now() + datetime.timedelta(minutes=OTP_LOCK_MINUTES)
                otp.save(update_fields=["attempts", "locked_until"])
                form.add_error("code", _("Incorrect code. Please try again."))
            else:
                otp.is_used = True
                otp.save(update_fields=["is_used"])
                PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)
                user.is_active = True
                user.save(update_fields=["is_active"])
                request.session.pop("signup_verification_email", None)
                request.session.pop("signup_next_url", None)
                messages.success(request, _("Your email has been verified. You can sign in now."))
                login_url = reverse("login")
                query_data = {"email": email}
                if next_url:
                    query_data["next"] = next_url
                return redirect(f"{login_url}?{urlencode(query_data)}")

    latest = PasswordResetOTP.objects.filter(email=email).order_by("-created_at").first()
    cooldown_seconds = 0
    if latest and latest.last_sent_at:
        elapsed = (timezone.now() - latest.last_sent_at).total_seconds()
        cooldown_seconds = max(0, OTP_RESEND_COOLDOWN_SECONDS - int(elapsed))

    return render(
        request,
        "accounts/signup_verify.html",
        {"form": form, "email": email, "cooldown_seconds": cooldown_seconds},
    )




# ======================================================
# CUSTOMER PROFILE
# ======================================================
@login_required
def customer_profile_view(request):
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        messages.error(request, "Please complete your profile to access this page.")
        return redirect("accounts:sign_up")

    if request.method == "POST":
        basic_form = CustomerBasicInfoForm(
            request.POST,
            request.FILES,
            instance=customer
        )
        if basic_form.is_valid():
            customer = basic_form.save(commit=False)

            customer.emergency_first_name = request.POST.get("emergency_first_name", "")
            customer.emergency_last_name = request.POST.get("emergency_last_name", "")
            customer.emergency_phone = request.POST.get("emergency_phone", "")
            customer.emergency_relation = request.POST.get("emergency_relation", "")

            customer.save()
    else:
        basic_form = CustomerBasicInfoForm(instance=customer)

    primary_location = CustomerLocation.objects.filter(
        customer=customer, is_primary=True
    ).first()
    if primary_location is None:
        customer.sync_location_cache(save=True)

    other_locations = CustomerLocation.objects.filter(
        customer=customer, is_primary=False
    )

    subscription, _ = Subscription.objects.get_or_create(
        customer=customer,
        defaults={
            "plan_name": "Weekly Cleaning",
            "duration_hours": 2,
            "price_per_session": 150,
            "frequency": "weekly",
            "next_billing_date": timezone.now().date(),
            "next_service_date": timezone.now().date(),
        },
    )

    payment_methods = customer.payment_methods.all().order_by("-is_default", "-created_at")

    active_statuses = [
        "ORDERED",
        "SCHEDULED",
        "ASSIGNED",
        "ON_THE_WAY",
        "STARTED",
        "PAUSED",
        "RESUMED",
    ]

    private_qs = list(
        PrivateBooking.objects.filter(
            user=request.user,
            status__in=active_statuses,
        )
    )
    business_qs = list(
        BusinessBooking.objects.filter(
            user=request.user,
            status__in=active_statuses,
        ).select_related("selected_bundle")
    )

    private_service_titles = _get_private_service_title_map(private_qs)

    def build_order_item(booking, booking_type):
        if booking_type == "private":
            title = _get_private_booking_title(booking, private_service_titles)
            order_code = f"PB-{booking.id}"
        else:
            raw_title = (
                booking.selected_service
                or (booking.selected_bundle.title if booking.selected_bundle else "Business Service")
            )
            title = _humanize_service_name(raw_title) or "Business Service"
            order_code = f"BB-{booking.id}"

        if booking.status == "ORDERED":
            status_label = _booking_table_status_label(booking.table_status)
            status_class = "pill-warn"
            date_label = "Booked on"
            when = booking.created_at
        elif booking.status == "ASSIGNED":
            status_label = _booking_table_status_label(booking.table_status)
            status_class = "pill-warn"
            date_label = "Next Service"
            when = (
                getattr(booking, "appointment_date", None)
                or getattr(booking, "start_date", None)
                or booking.scheduled_at
                or booking.created_at
            )
        elif booking.status == "ON_THE_WAY":
            status_label = _booking_table_status_label(booking.table_status)
            status_class = "pill-info"
            date_label = "On the way since"
            when = booking.provider_on_way_at or booking.scheduled_at or booking.created_at
        elif booking.status in ["STARTED", "PAUSED", "RESUMED"]:
            status_label = _booking_table_status_label(booking.table_status)
            status_class = "pill-info"
            date_label = "In Progress since"
            when = booking.started_at or booking.provider_on_way_at or booking.scheduled_at or booking.created_at
        else:
            status_label = _booking_table_status_label(booking.table_status)
            status_class = "pill-warn"
            date_label = "Next Service"
            when = (
                getattr(booking, "appointment_date", None)
                or getattr(booking, "start_date", None)
                or booking.scheduled_at
                or booking.created_at
            )

        return {
            "id": booking.id,
            "type": booking_type,
            "title": title,
            "when": when,
            "order_code": order_code,
            "status_label": status_label,
            "status_class": status_class,
            "date_label": date_label,
        }

    ongoing_orders = [
        build_order_item(b, "private") for b in private_qs
    ] + [
        build_order_item(b, "business") for b in business_qs
    ]

    def _sort_key(item):
        when = item["when"]
        if when is None:
            return timezone.now()
        if isinstance(when, datetime.date) and not isinstance(when, datetime.datetime):
            # Date object, normalize to start of day (aware).
            return timezone.make_aware(
                datetime.datetime.combine(when, datetime.time.min),
                timezone.get_current_timezone(),
            )
        if timezone.is_naive(when):
            return timezone.make_aware(when, timezone.get_current_timezone())
        return when

    ongoing_orders.sort(key=_sort_key)
    ongoing_orders = ongoing_orders[:4]

    return render(
        request,
        "accounts/sidebar/customer_profile_view.html",
        {
            "customer": customer,
            "basic_form": basic_form,
            "primary_location": primary_location,
            "other_locations": other_locations,
            "ongoing_orders": ongoing_orders,
            "subscription": subscription,
            "payment_methods": payment_methods,
        },
    )


@require_POST
@login_required
def manage_subscription(request):
    customer = get_object_or_404(Customer, user=request.user)
    subscription, _ = Subscription.objects.get_or_create(
        customer=customer,
        defaults={
            "plan_name": "Weekly Cleaning",
            "duration_hours": 2,
            "price_per_session": 150,
            "frequency": "weekly",
            "next_billing_date": timezone.now().date(),
            "next_service_date": timezone.now().date(),
        },
    )

    action = request.POST.get("action", "save")

    if action == "cancel":
        subscription.status = "cancelled"
        subscription.cancellation_reason = request.POST.get("cancel_reason", "")
        subscription.cancelled_at = timezone.now()
        subscription.save()
        return JsonResponse({
            "ok": True,
            "status": "cancelled",
        })

    subscription.skip_next_service = request.POST.get("skip_next_service") == "on"

    pause_flag = request.POST.get("pause_subscription") == "on"
    subscription.is_paused = pause_flag
    if pause_flag:
        subscription.pause_until = parse_date(request.POST.get("pause_until") or "")
        subscription.resume_on = parse_date(request.POST.get("resume_on") or "")
    else:
        subscription.pause_until = None
        subscription.resume_on = None

    payment_method_id = request.POST.get("payment_method")
    if payment_method_id:
        subscription.payment_method = PaymentMethod.objects.filter(
            id=payment_method_id,
            customer=customer
        ).first()
    else:
        subscription.payment_method = None

    subscription.save()

    return JsonResponse({
        "ok": True,
        "status": "active",
        "summary": {
            "skip_next_service": subscription.skip_next_service,
            "is_paused": subscription.is_paused,
            "pause_until": subscription.pause_until,
            "resume_on": subscription.resume_on,
            "payment_method": (
                f"{subscription.payment_method.get_card_type_display()} •••• {subscription.payment_method.card_last4}"
                if subscription.payment_method else ""
            ),
        }
    })


# ======================================================
# ADDRESS & LOCATIONS
# ======================================================
@login_required
def Address_and_Locations_view(request):
    customer = get_object_or_404(Customer, user=request.user)

    if not CustomerLocation.objects.filter(customer=customer).exists():
        street_address = customer.display_address() or customer.full_address or ""
        if customer.house_num and customer.house_num not in street_address:
            street_address = f"{street_address} {customer.house_num}".strip()

        location_country = CustomerLocation.normalize_country_choice(customer.country)

        CustomerLocation.objects.create(
            customer=customer,
            address_type="home",
            street_address=street_address or "-",
            city=customer.display_city(),
            region="-",
            postal_code=customer.display_postal_code(),
            country=location_country,
            contact_name=f"{customer.first_name} {customer.last_name}".strip(),
            contact_phone=customer.phone,
            entry_code=customer.display_entry_code(),
            parking_notes=customer.display_parking_notes(),
            is_primary=True,
        )

    locations = CustomerLocation.objects.filter(
        customer=customer
    ).order_by("-is_primary", "-created_at")

    return render(
        request,
        "accounts/sidebar/Address_and_Locations_view.html",
        {"customer": customer, "locations": locations},
    )


@login_required
def set_location_primary(request, location_id):
    customer = get_object_or_404(Customer, user=request.user)

    location = get_object_or_404(
        CustomerLocation, id=location_id, customer=customer
    )

    CustomerLocation.objects.filter(
        customer=customer, is_primary=True
    ).update(is_primary=False)

    location.is_primary = True
    location.save()

    return redirect("accounts:Address_and_Locations_view")


@login_required
def delete_location(request, location_id):
    customer = get_object_or_404(Customer, user=request.user)

    location = get_object_or_404(
        CustomerLocation, id=location_id, customer=customer
    )
    location.delete()

    return redirect("accounts:Address_and_Locations_view")


@login_required
def edit_address_and_locations(request, location_id):
    customer = get_object_or_404(Customer, user=request.user)

    location = get_object_or_404(
        CustomerLocation, id=location_id, customer=customer
    )

    if request.method == "POST":
        form = CustomerLocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            return redirect("accounts:Address_and_Locations_view")
    else:
        form = CustomerLocationForm(instance=location)

    return render(
        request,
        "accounts/subpages/Add_Address_and_Locations.html",
        {
            "customer": customer,
            "form": form,
            "location": location,
            "is_edit": True,
        },
    )


@login_required
def Add_Address_and_Locations(request):
    customer = get_object_or_404(Customer, user=request.user)

    if request.method == "POST":
        form = CustomerLocationForm(request.POST)
        if form.is_valid():
            location = form.save(commit=False)
            location.customer = customer

            if not CustomerLocation.objects.filter(customer=customer).exists():
                location.is_primary = True

            location.save()
            return redirect("accounts:Address_and_Locations_view")
    else:
        form = CustomerLocationForm()

    return render(
        request,
        "accounts/subpages/Add_Address_and_Locations.html",
        {"customer": customer, "form": form},
    )


# ======================================================
# MY BOOKINGS
# ======================================================
@login_required
def my_bookimg(request):
    user = request.user
    customer = Customer.objects.filter(user=user).first()

    private_bookings = list(PrivateBooking.objects.filter(user=user))
    business_bookings = list(BusinessBooking.objects.filter(user=user).select_related("selected_bundle"))
    private_service_titles = _get_private_service_title_map(private_bookings)

    bookings = []

    def booking_status_group(status_value):
        status_value = (status_value or "").upper()
        if status_value in {"COMPLETED", "REFUNDED"}:
            return "completed"
        if status_value in {"CANCELLED_BY_CUSTOMER", "CANCELLED_BY_ADMIN", "NO_SHOW"}:
            return "cancelled"
        if status_value in {"ON_THE_WAY", "STARTED", "PAUSED", "RESUMED"}:
            return "ongoing"
        return "upcoming"

    full_name = (
        f"{customer.first_name} {customer.last_name}"
        if customer
        else user.username
    )
    for b in private_bookings:
        bookings.append({
            "id": b.id,
            "type": "Private",
            "customer_name": full_name,
            "service": _get_private_booking_title(b, private_service_titles),
            "date": b.appointment_date,
            "location": b.address or b.area,
            "status": b.table_status,
            "status_label": _booking_table_status_label(b.table_status),
            "status_group": booking_status_group(b.status),
        })

    for b in business_bookings:
        bookings.append({
            "id": b.id,
            "type": "Business",
            "customer_name": full_name,
            "service": _humanize_service_name(
                b.selected_service or (b.selected_bundle.title if b.selected_bundle else "")
            ),
            "date": b.start_date,
            "location": b.office_address,
            "status": b.table_status,
            "status_label": _booking_table_status_label(b.table_status),
            "status_group": booking_status_group(b.status),
        })

    return render(
        request,
        "accounts/sidebar/my_bookimg.html",
        {"bookings": bookings, "customer": customer},
    )


# ======================================================
# BOOKING DETAILS
# ======================================================
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from home.models import PrivateBooking, BusinessBooking, BookingStatusHistory

@login_required
def view_service_details(request, booking_type, booking_id):

    # ===============================
    # 1️⃣ GET BOOKING
    # ===============================
    if booking_type == "private":
        booking = PrivateBooking.objects.filter(
            id=booking_id,
            user=request.user
        ).first()
        service_title = ", ".join(booking.selected_services or []) or "Private Service" if booking else "Private Service"
        booking_date = getattr(booking, "appointment_date", None)
        booking_time = getattr(booking, "appointment_time_window", "") or ""
        location_text = getattr(booking, "address", None) or getattr(booking, "area", None) or "-"
        payment_method = getattr(booking, "payment_method", "") or "-"
        order_type_label = "Private"
    elif booking_type == "business":
        booking = BusinessBooking.objects.filter(
            id=booking_id,
            user=request.user
        ).first()
        service_title = (
            booking.selected_service
            or (booking.selected_bundle.title if booking and booking.selected_bundle else "Business Service")
        ) if booking else "Business Service"
        booking_date = getattr(booking, "start_date", None)
        booking_time = getattr(booking, "preferred_time", "") or ""
        location_text = getattr(booking, "office_address", None) or "-"
        payment_method = "-"
        order_type_label = "Business"
    else:
        raise Http404("Invalid booking type")

    if not booking:
        raise Http404("Booking not found")

    # ===============================
    # 2) Rating (optional)
    # ===============================
    existing_review = ServiceReview.objects.filter(
        customer=request.user,
        booking_type=booking_type,
        booking_id=booking.id,
    ).first()
    has_review = existing_review is not None
    can_rate = booking.provider is not None and booking.status == "COMPLETED" and not has_review
    rating_form = ServiceReviewForm()

    if request.method == "POST" and request.POST.get("form_type") == "rating":
        if not can_rate:
            messages.error(request, "Rating is only available after the service is completed.")
            return redirect(request.path)

        if booking_type == "private":
            service_title = ", ".join(booking.selected_services or []) or "Private Service"
        else:
            service_title = (
                booking.selected_service
                or (booking.selected_bundle.title if booking.selected_bundle else "Business Service")
            )

        rating_form = ServiceReviewForm(request.POST)
        if rating_form.is_valid():
            review = rating_form.save(commit=False)
            review.customer = request.user
            review.booking_type = booking_type
            review.booking_id = booking.id
            review.service_title = service_title
            review.provider = booking.provider
            review.save()
            messages.success(request, "Your rating has been saved.")
            return redirect(request.path)

    # ===============================
    # 2️⃣ CHECKLIST (ONE TO ONE) - NO AUTO CHECK ✅
    # ===============================
    checklist_items = _ensure_booking_checklist_items(booking, booking_type)
    checklist_sections = _group_checklist_items(checklist_items)
    checklist_total_count = len(checklist_items)
    checklist_completed_count = sum(1 for item in checklist_items if item.is_completed)
    checklist_progress_percent = int(
        (checklist_completed_count / checklist_total_count) * 100
    ) if checklist_total_count else 0

    available_addons_json = "{}"
    saved_addons_json = "{}"
    if booking_type == "private":
        selected_services = booking.selected_services or []
        services = PrivateService.objects.filter(slug__in=selected_services).prefetch_related("addons_list")
        saved_addons = booking.addons_selected or {}
        available_addons = {}
        for service in services:
            service_addons = {}
            for addon in service.addons_list.all():
                if saved_addons.get(service.slug, {}).get(addon.slug):
                    continue
                service_addons[addon.slug] = {
                    "label": addon.title,
                    "icon": addon.icon.url if addon.icon else "",
                    "form": addon.form_html or "",
                    "price": float(addon.price or 0),
                    "price_per_unit": float(addon.price_per_unit or 0),
                }
            if service_addons:
                available_addons[service.slug] = {
                    "title": service.title,
                    "addons": service_addons,
                }
        available_addons_json = json.dumps(available_addons)
        saved_addons_json = json.dumps(saved_addons)

    # ===============================
    # 2.5) REQUEST FIX
    # ===============================
    if request.method == "POST" and request.POST.get("form_type") == "request_fix":
        message_text = request.POST.get("message", "").strip()
        if not message_text:
            messages.error(request, "Please describe the issue.")
            return redirect(request.path)

        request_fix = BookingRequestFix.objects.create(
            booking_type=booking_type,
            booking_id=booking.id,
            customer=request.user,
            message=message_text,
        )

        for file in request.FILES.getlist("files"):
            BookingRequestFixAttachment.objects.create(
                request_fix=request_fix,
                file=file,
            )

        sender_name = request.user.get_full_name() or request.user.username
        CustomerNotification.objects.create(
            user=request.user,
            title="Request Fix Submitted",
            body=f"Request Fix sent by {sender_name} for booking #{booking.id}.",
            notification_type="request_fix",
            booking_type=booking_type,
            booking_id=booking.id,
            request_fix=request_fix,
        )

        messages.success(request, "Your request has been sent.")
        return redirect(request.path)

    # ===============================
    # 3️⃣ HISTORY
    # ===============================
    history = list(
        BookingStatusHistory.objects.filter(
            booking_type=booking_type,
            booking_id=booking.id
        ).order_by("created_at")
    )

    # ===============================
    # 4️⃣ UI FLAGS
    # ===============================
    hide_actions = booking.status in [
        "CANCELLED_BY_CUSTOMER",
        "NO_SHOW",
        "REFUNDED",
    ]

    # ===============================
    # 5️⃣ FLOW & EXCEPTIONS
    # ===============================
    FLOW = [
        ("ORDERED", "Order Placed"),
        ("SCHEDULED", "Confirmed / Scheduled"),
        ("ON_THE_WAY", "Provider On The Way"),
        ("STARTED", "Check in / Service Started"),
        ("PAUSED", "Service Paused"),
        ("COMPLETED", "Service Completed"),
    ]

    EXCEPTIONS = {
        "CANCELLED_BY_CUSTOMER": "Cancelled by Customer",
        "NO_SHOW": "No Show",
        "INCIDENT_REPORTED": "Incident Reported",
        "REFUNDED": "Refunded",
    }

    # ===============================
    # 6️⃣ LAST DATE / NOTE PER STATUS
    # ===============================
    last_date = {}
    last_note = {}

    for h in history:
        last_date[h.status] = h.created_at
        last_note[h.status] = getattr(h, "note", "") or ""

    latest_raw = history[-1].status if history else booking.status

    # ===============================
    # 7️⃣ BUILD NORMAL FLOW
    # ===============================
    timeline = []
    print(request.POST)

    for code, label in FLOW:
        timeline.append({
            "code": code,
            "label": label,
            "date": last_date.get(code),
            "note": last_note.get(code),
            "active": code in last_date,
            "latest": False,
            "is_exception": False,
        })

    # ===============================
    # 8️⃣ ADD EXCEPTION
    # ===============================
    if latest_raw in EXCEPTIONS and latest_raw != "REFUNDED":
        timeline.append({
            "code": latest_raw,
            "label": EXCEPTIONS[latest_raw],
            "date": last_date.get(latest_raw),
            "note": last_note.get(latest_raw),
            "active": True,
            "latest": False,
            "is_exception": True,
        })

    # ===============================
    # 9️⃣ FORCE REFUND
    # ===============================
    if booking.is_refunded:

        for t in timeline:
            t["latest"] = False

        refund_note = booking.refund_reason or ""
        refund_amount_text = ""
        charge_currency = (
            getattr(booking, "payment_currency", None)
            or getattr(settings, "STRIPE_CURRENCY", "usd")
            or "usd"
        ).upper()

        if booking.refund_amount and booking.refund_amount > 0:
            refund_amount_text = f"Refunded amount: {booking.refund_amount} {charge_currency}"

        timeline.append({
            "code": "REFUNDED",
            "label": "Refunded",
            "date": booking.refunded_at,
            "note": f"{refund_amount_text}\n{refund_note}".strip(),
            "active": True,
            "latest": True,
            "is_exception": True,
        })

    # ===============================
    # 🔟 CHAT – UNREAD MESSAGES
    # ===============================
    try:
        thread = ChatThread.objects.get(
            booking_type=booking_type,
            booking_id=booking.id
        )

        customer_unread_messages = ChatMessage.objects.filter(
            thread=thread,
            is_read=False
        ).exclude(sender=request.user).count()

    except ChatThread.DoesNotExist:
        customer_unread_messages = 0


    # ===============================
    # 📝 BOOKING NOTES
    # ===============================
    notes = BookingNote.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id
    )



    # ===============================
    # ➕ ADD NOTE
    # ===============================
    if request.method == "POST" and request.POST.get("form_type") == "note":
        note_text = request.POST.get("note_text", "").strip()

        if note_text:
            BookingNote.objects.create(
                booking_type=booking_type,
                booking_id=booking.id,
                text=note_text,
                created_by=request.user
            )

        return redirect(request.path)


    def _format_seconds(total_seconds):
        if not total_seconds or total_seconds <= 0:
            return None
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    quoted_seconds = 0
    quoted_time = None

    duration_str = str(getattr(booking, "duration_hours", "") or "").strip()
    if duration_str:
        quoted_time = duration_str
        if ":" in duration_str:
            try:
                parts = duration_str.split(":")
                if len(parts) >= 2:
                    h = int(parts[0])
                    m = int(parts[1])
                    s = int(parts[2]) if len(parts) > 2 else 0
                    quoted_seconds = max(quoted_seconds, h * 3600 + m * 60 + s)
            except ValueError:
                pass
        else:
            try:
                hours = float(duration_str)
                minutes = int(round(hours * 60))
                quoted_time = booking.format_minutes(minutes)
                quoted_seconds = max(quoted_seconds, minutes * 60)
            except ValueError:
                quoted_time = None

    if not quoted_time and booking.quoted_duration_minutes:
        quoted_seconds = int(booking.quoted_duration_minutes) * 60
        quoted_time = booking.format_minutes(
            booking.quoted_duration_minutes
        )
        if quoted_time == "":
            quoted_time = None

    if not quoted_time:
        pricing = getattr(booking, "pricing_details", None) or {}
        duration_seconds = int(pricing.get("duration_seconds", 0) or 0)
        duration_minutes = int(pricing.get("duration_minutes", 0) or 0)
        quoted_time = _format_seconds(duration_seconds) or booking.format_minutes(duration_minutes)
        quoted_seconds = max(quoted_seconds, duration_seconds, duration_minutes * 60)

    if not quoted_time:
        quoted_time = ""



    
    actual_duration = None

    started = BookingStatusHistory.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id,
        status="STARTED"
    ).order_by("created_at").first()

    completed = BookingStatusHistory.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id,
        status="COMPLETED"
    ).order_by("created_at").first()

    if started and completed:
        delta = completed.created_at - started.created_at
        total_minutes = int(delta.total_seconds() // 60)

        hours = total_minutes // 60
        minutes = total_minutes % 60

        actual_duration = f"{hours} hours {minutes} minutes"


        started = BookingStatusHistory.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id,
        status="STARTED"
    ).order_by("created_at").first()

    completed = BookingStatusHistory.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id,
        status="COMPLETED"
    ).order_by("created_at").first()

    start_time = started.created_at if started else None
    end_time = completed.created_at if completed else None

    media_items = BookingMedia.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id
    ).order_by("-created_at")[:8]

    latest_request_fix = BookingRequestFix.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id,
        customer=request.user,
    ).order_by("-created_at").first()
    # ===============================
    # 1️⃣1️⃣ RENDER
    # ===============================
    return render(
        request,
        "accounts/subpages/view_service_details.html",
        {
            "booking": booking,
            "booking_type": booking_type,
            "service_title": service_title,
            "booking_date": booking_date,
            "booking_time": booking_time,
            "location_text": location_text,
            "payment_method": payment_method,
            "order_type_label": order_type_label,
            "note": booking.note.all(),
            "timeline": timeline,
            "hide_actions": hide_actions,
            "customer_unread_messages": customer_unread_messages,
            "rating_form": rating_form,
            "can_rate": can_rate,
            "has_review": has_review,
            "checklist_sections": checklist_sections,
            "checklist_total_count": checklist_total_count,
            "checklist_completed_count": checklist_completed_count,
            "checklist_progress_percent": checklist_progress_percent,
            "notes": notes,   # 🔥
            "quoted_time": quoted_time,
            "quoted_seconds": quoted_seconds,
            "actual_duration": actual_duration,
            "start_time": start_time,
            "end_time": end_time,
            "media_items": media_items,
            "latest_request_fix": latest_request_fix,
            "available_addons_json": available_addons_json,
            "saved_addons_json": saved_addons_json,
            "charge_currency": (
                getattr(booking, "payment_currency", None)
                or getattr(settings, "STRIPE_CURRENCY", "usd")
                or "usd"
            ).upper(),
        },
    )



@require_POST
@login_required
def cancel_booking(request, booking_type, booking_id):

    reason = request.POST.get("reason", "")

    if booking_type == "private":
        booking = get_object_or_404(
            PrivateBooking,
            id=booking_id,
            user=request.user
        )
    elif booking_type == "business":
        booking = get_object_or_404(
            BusinessBooking,
            id=booking_id,
            user=request.user
        )
    else:
        raise Http404("Invalid booking type")

    # تحقق إنو مسموح الإلغاء
    if not booking.can_cancel:
        messages.error(request, "This booking can no longer be cancelled.")
        return redirect(
            "accounts:view_service_details",
            booking_type=booking_type,
            booking_id=booking.id
        )

    # ✅ الإلغاء الصح (زبون)
    booking.cancel_by_customer(
        user=request.user,
        note=reason or "Cancelled by customer"
    )

    messages.success(request, "Your booking has been cancelled.")

    return redirect(
        "accounts:view_service_details",
        booking_type=booking_type,
        booking_id=booking.id
    )

# ======================================================
# INCIDENTS
# ======================================================
@login_required
def incident(request):
    incidents = Incident.objects.filter(
        customer=request.user
    ).order_by("-created_at")

    return render(
        request,
        "accounts/sidebar/incident.html",
        {"incidents": incidents},
    )


@login_required
def Incident_Report_order(request, incident_id):
    incident = get_object_or_404(
        Incident, id=incident_id, customer=request.user
    )

    return render(
        request,
        "accounts/subpages/Incident_Report_order.html",
        {"incident": incident},
    )


@login_required
def Report_Incident(request):
    if request.method == "POST":
        form = IncidentForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.customer = request.user
            incident.save()
            CustomerNotification.objects.create(
                user=request.user,
                title="Incident Report Received",
                body=(
                    f"Incident #{incident.id} for order #{incident.order} "
                    f"({incident.incident_type}, {incident.get_severity_display()} severity) "
                    f"was logged for {incident.location}."
                ),
                notification_type="incident",
            )

            return render(
                request,
                "accounts/subpages/Report_Incident.html",
                {
                    "form": IncidentForm(),
                    "show_popup": True,
                    "incident": incident,
                },
            )
    else:
        form = IncidentForm(user=request.user)

    return render(
        request,
        "accounts/subpages/Report_Incident.html",
        {"form": form},
    )


# ======================================================
# STATIC PAGES
# ======================================================
def Add_on_Service_Request(request):
    return render(request, "accounts/subpages/Add_on_Service_Request.html")


def Media(request):
    booking_type = request.GET.get("booking_type")
    booking_id = request.GET.get("booking_id")

    booking = None
    if booking_type and booking_id:
        if booking_type == "private":
            booking = PrivateBooking.objects.filter(id=booking_id, user=request.user).first()
        elif booking_type == "business":
            booking = BusinessBooking.objects.filter(id=booking_id, user=request.user).first()

    if request.method == "POST":
        if not booking:
            return redirect(request.path)
        action = request.POST.get("action", "upload")
        if action == "delete":
            media_id = request.POST.get("media_id")
            media = BookingMedia.objects.filter(
                id=media_id,
                booking_type=booking_type,
                booking_id=booking.id
            ).first()
            if media:
                media.delete()
            return redirect(request.path + f"booking_type={booking_type}&booking_id={booking_id}")

        phase = request.POST.get("phase", "before")
        file = request.FILES.get("file")
        if file and phase in ["before", "during", "after", "issue"]:
            BookingMedia.objects.create(
                booking_type=booking_type,
                booking_id=booking.id,
                phase=phase,
                file=file,
                uploaded_by=request.user,
            )
        return redirect(request.path + f"booking_type={booking_type}&booking_id={booking_id}")

    media_qs = BookingMedia.objects.none()
    if booking:
        media_qs = BookingMedia.objects.filter(
            booking_type=booking_type,
            booking_id=booking.id
        ).order_by("-created_at")

    media_by_phase = {
        "before": [m for m in media_qs if m.phase == "before"],
        "during": [m for m in media_qs if m.phase == "during"],
        "after": [m for m in media_qs if m.phase == "after"],
        "issue": [m for m in media_qs if m.phase == "issue"],
    }

    return render(
        request,
        "accounts/subpages/Media.html",
        {
            "booking": booking,
            "booking_type": booking_type,
            "booking_id": booking_id,
            "media_by_phase": media_by_phase,
        }
    )


@login_required
def chat(request):
    if request.user.is_staff and not request.user.is_superuser:
        return redirect("accounts:provider_inbox")
    return render(request, "accounts/subpages/chat.html")


CLEANING_CHOICES = [
    ("Standard Clean", "Standard Clean"),
    ("Deep Clean", "Deep Clean"),
    ("Move-in/Move-out", "Move-in/Move-out"),
    ("Event/Party (before & after)", "Event/Party (before & after)"),
    ("Airbnb/Short-stay", "Airbnb/Short-stay"),
    ("Emergency/Urgent", "Emergency/Urgent"),
]



@login_required
def Service_Preferences(request):
    customer = Customer.objects.filter(user=request.user).first()
    if customer is None:
        raise Http404("Customer profile not found")
    prefs, _ = CustomerPreferences.objects.get_or_create(customer=customer)

    # =====================================
    # 🔹 AJAX SAVE (Save صغير لكل حقل)
    # =====================================
    if request.method == "POST" and (request.content_type or "").startswith("application/json"):
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON payload."}, status=400)

        field = (data.get("field") or "").strip()
        raw_value = data.get("value")

        list_fields = {
            "preferred_products",
            "excluded_products",
            "priorities",
            "cleaning_types",
            "lifestyle_addons",
            "assembly_services",
        }
        custom_text_fields = {
            "products_custom",
            "frequency_custom",
            "priorities_custom",
        }
        scalar_fields = {"frequency"}

        if field in list_fields:
            if isinstance(raw_value, list):
                cleaned_values = []
                for item in raw_value:
                    item_text = str(item).strip()
                    if item_text and item_text not in cleaned_values:
                        cleaned_values.append(item_text)
                setattr(prefs, field, cleaned_values)
            else:
                value = str(raw_value or "").strip()
                current_values = list(getattr(prefs, field) or [])
                if value and value not in current_values:
                    current_values.append(value)
                setattr(prefs, field, current_values)

        elif field in scalar_fields:
            prefs.frequency = str(raw_value or "").strip() or None

        elif field in custom_text_fields:
            setattr(prefs, field, str(raw_value or "").strip())

        else:
            return JsonResponse({"status": "error", "message": "Unsupported field."}, status=400)

        prefs.save()
        return JsonResponse({
            "status": "ok",
            "field": field,
            "value": getattr(prefs, field),
            "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else "",
        })

    # =====================================
    # 🔹 SAVE الكبير (يحفظ كل الصفحة)
    # =====================================
    if request.method == "POST":

        if request.POST.get("save_custom"):
            target = request.POST.get("save_custom")
            if target == "products":
                prefs.products_custom = request.POST.get("products_custom", "").strip()
            elif target == "frequency":
                prefs.frequency_custom = request.POST.get("frequency_custom", "").strip()
            elif target == "priorities":
                prefs.priorities_custom = request.POST.get("priorities_custom", "").strip()
            prefs.save()
            return redirect("accounts:Service_Preferences")

        # Always overwrite lists so unchecking clears values
        prefs.cleaning_types = request.POST.getlist("cleaning_types")
        prefs.preferred_products = request.POST.getlist("preferred_products")
        prefs.excluded_products = request.POST.getlist("excluded_products")
        prefs.priorities = request.POST.getlist("priorities")
        prefs.lifestyle_addons = request.POST.getlist("lifestyle_addons")
        prefs.assembly_services = request.POST.getlist("assembly_services")

        prefs.frequency = request.POST.get("frequency") or None

        # Allow clearing custom fields
        prefs.products_custom = request.POST.get("products_custom", "").strip()
        prefs.frequency_custom = request.POST.get("frequency_custom", "").strip()
        prefs.priorities_custom = request.POST.get("priorities_custom", "").strip()

        prefs.save()
        return redirect("accounts:Service_Preferences")

    # =====================================
    # 🔹 CONTEXT (للعرض + Summary)
    # =====================================
    context = {
        "prefs": prefs,

        "selected_cleaning": prefs.cleaning_types or [],
        "selected_products": prefs.preferred_products or [],
        "excluded_products": prefs.excluded_products or [],
        "selected_frequency": prefs.frequency or "",

        "selected_priorities": prefs.priorities or [],
        "selected_lifestyle": prefs.lifestyle_addons or [],
        "selected_assembly": prefs.assembly_services or [],
        "products_custom": prefs.products_custom or "",
        "frequency_custom": prefs.frequency_custom or "",
        "priorities_custom": prefs.priorities_custom or "",

        "customer_name": f"{customer.first_name} {customer.last_name}".strip(),
        "customer_id": customer.id,
        "pref_id": prefs.id,
    }

    return render(request, "accounts/sidebar/Service_Preferences.html", context)

@login_required
def Communication(request):
    pref, created = CommunicationPreference.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":
        form = CommunicationPreferenceForm(request.POST, instance=pref)
        if form.is_valid():
            form.save()
            return redirect("accounts:Communication")
    else:
        form = CommunicationPreferenceForm(instance=pref)

    notifications = CustomerNotification.objects.filter(
        user=request.user
    ).exclude(
        notification_type="request_fix"
    ).order_by("-created_at")[:20]

    return render(request, "accounts/sidebar/Communication.html", {
        "form": form,
        "pref": pref,
        "notifications": notifications,
    })


@login_required
def Customer_Notes(request):
    customer = get_object_or_404(Customer, user=request.user)
    notes = CustomerNote.objects.filter(customer=request.user).first()

    context = {
        "customer": customer,
        "notes": notes,
    }
    return render(request, "accounts/sidebar/Customer_Notes.html", context)


@login_required
def add_Customer_Notes(request):
    customer = get_object_or_404(Customer, user=request.user)
    note, _ = CustomerNote.objects.get_or_create(customer=request.user)

    if request.method == "POST":
        form = CustomerNoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            return redirect("accounts:Customer_Notes")
    else:
        form = CustomerNoteForm(instance=note)

    return render(
        request,
        "accounts/subpages/add_Customer_Notes.html",
        {
            "customer": customer,
            "form": form,
        },
    )


def _backfill_missing_private_invoices(customer):
    bookings_with_payments = (
        PrivateBooking.objects.filter(
            user=customer.user,
        )
        .exclude(payment_intent_id__isnull=True)
        .exclude(payment_intent_id__exact="")
        .order_by("-created_at")
    )

    for booking in bookings_with_payments:
        if booking.payment_status != "succeeded" and not booking.is_refunded:
            continue

        payment_method = None
        if booking.payment_last4 and booking.payment_brand:
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
                "amount": booking.refund_amount if booking.is_refunded else (booking.payment_amount or booking.total_price or 0),
                "currency": (booking.payment_currency or "USD").upper(),
                "status": "REFUNDED" if booking.is_refunded else "PAID",
                "payment_method": payment_method,
                "paid_at": getattr(booking, "refunded_at", None) if booking.is_refunded else (getattr(booking, "updated_at", None) or timezone.now()),
                "note": (
                    f"Refunded. {booking.refund_reason or ''}".strip()
                    if booking.is_refunded
                    else f"Stripe PaymentIntent {booking.payment_intent_id}"
                ),
            },
        )


@login_required
def Payment_and_Billing(request):
    customer = get_object_or_404(Customer, user=request.user)
    logger.info("[Payment & Billing] user=%s customer=%s", request.user, customer.id)

    _backfill_missing_private_invoices(customer)

    payment_methods = PaymentMethod.objects.filter(
        customer=customer
    ).order_by("-is_default", "-created_at")
    logger.info("[Payment & Billing] payment methods count=%s", payment_methods.count())

    invoices = Invoice.objects.filter(
        customer=customer
    ).select_related("payment_method").order_by("-issued_at")[:20]
    private_booking_brands = {
        booking.id: (booking.payment_brand or "").strip().title()
        for booking in PrivateBooking.objects.filter(
            user=request.user,
            id__in=[
                invoice.booking_id
                for invoice in invoices
                if invoice.booking_type == "private" and invoice.booking_id
            ],
        ).only("id", "payment_brand")
    }
    for invoice in invoices:
        if invoice.payment_method:
            invoice.display_payment_label = invoice.payment_method.get_card_type_display()
        elif invoice.booking_type == "private" and invoice.booking_id:
            invoice.display_payment_label = private_booking_brands.get(invoice.booking_id, "")
        else:
            invoice.display_payment_label = ""

    subscription, _ = Subscription.objects.get_or_create(
        customer=customer,
        defaults={
            "plan_name": "Weekly Cleaning",
            "duration_hours": 2,
            "price_per_session": 150,
            "frequency": "weekly",
            "next_billing_date": timezone.now().date(),
            "next_service_date": timezone.now().date(),
        },
    )

    context = {
        "customer": customer,
        "payment_methods": payment_methods,
        "subscription": subscription,
        "invoices": invoices,
    }

    return render(
        request,
        "accounts/sidebar/Payment_and_Billing.html",
        context
    )


@login_required
def download_invoice_pdf(request, invoice_id):
    customer = get_object_or_404(Customer, user=request.user)
    invoice = get_object_or_404(
        Invoice.objects.select_related("payment_method"),
        id=invoice_id,
        customer=customer,
    )

    booking_summary = ""
    if invoice.booking_type == "private" and invoice.booking_id:
        booking = PrivateBooking.objects.filter(id=invoice.booking_id, user=request.user).first()
        if booking:
            services = booking.selected_services or []
            service_title_map = _get_private_service_title_map([booking])
            booking_summary = ", ".join(
                filter(
                    None,
                    [
                        service_title_map.get(service, _humanize_service_name(service))
                        for service in services
                    ],
                )
            )
    elif invoice.booking_type == "business" and invoice.booking_id:
        booking = BusinessBooking.objects.filter(id=invoice.booking_id, user=request.user).first()
        if booking:
            booking_summary = booking.selected_service or booking.company_name or ""

    payment_method_label = "Not available"
    if invoice.payment_method:
        payment_method_label = (
            f"{invoice.payment_method.get_card_type_display()} **** {invoice.payment_method.card_last4}"
        )

    customer_name = f"{customer.first_name} {customer.last_name}".strip() or customer.email or "Customer"
    meta_rows = [
        ("Invoice Number", invoice.invoice_number),
        ("Customer", customer_name),
        ("Issued At", timezone.localtime(invoice.issued_at).strftime("%Y-%m-%d %H:%M")),
        ("Status", invoice.get_status_display()),
        ("Amount", f"{invoice.amount:.2f} {invoice.currency}"),
    ]
    section_rows = [
        ("Payment Method", payment_method_label),
        ("Booking Type", invoice.get_booking_type_display() if invoice.booking_type else "N/A"),
        ("Booking ID", invoice.booking_id or "N/A"),
    ]

    if booking_summary:
        section_rows.append(("Service Summary", booking_summary))
    if invoice.paid_at:
        section_rows.append(("Paid At", timezone.localtime(invoice.paid_at).strftime("%Y-%m-%d %H:%M")))

    footer_lines = []
    if invoice.note:
        footer_lines.append(f"Reference: {invoice.note}")
    footer_lines.append("Thank you for choosing Hembla Experten.")

    pdf_bytes = _build_invoice_pdf("Invoice", meta_rows, section_rows, footer_lines=footer_lines)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.pdf"'
    return response

@login_required
@require_POST
def set_payment_default(request, pk):
    customer = get_object_or_404(Customer, user=request.user)

    PaymentMethod.objects.filter(
        customer=customer,
        is_default=True
    ).update(is_default=False)

    payment = get_object_or_404(
        PaymentMethod,
        pk=pk,
        customer=customer
    )
    payment.is_default = True
    payment.save()

    return redirect("accounts:Payment_and_Billing")

@login_required
@require_POST
def delete_payment_method(request, pk):
    customer = get_object_or_404(Customer, user=request.user)

    payment = get_object_or_404(
        PaymentMethod,
        pk=pk,
        customer=customer
    )
    was_default = payment.is_default
    payment.delete()

    if was_default:
        fallback_payment = PaymentMethod.objects.filter(customer=customer).order_by("-created_at").first()
        if fallback_payment:
            fallback_payment.is_default = True
            fallback_payment.save(update_fields=["is_default"])

    return redirect("accounts:Payment_and_Billing")


@login_required
def Add_Payment_Method(request):
    customer = get_object_or_404(Customer, user=request.user)
    form = PaymentMethodForm()
    stripe_ready = bool(settings.STRIPE_PUBLISHABLE_KEY and settings.STRIPE_SECRET_KEY)
    client_secret = ""

    if not stripe_ready:
        logger.warning("Stripe keys are missing for Add_Payment_Method view.")
    else:
        stripe.api_key = settings.STRIPE_SECRET_KEY

    return render(
        request,
        "accounts/subpages/Add_Payment_Method.html",
        {
            "customer": customer,
            "form": form,
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "stripe_client_secret": client_secret,
            "stripe_ready": stripe_ready,
        },
    )


@login_required
@require_POST
def create_setup_intent(request):
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return JsonResponse({"ok": False, "error": "Customer profile missing"}, status=400)
    if not settings.STRIPE_SECRET_KEY:
        return JsonResponse({"ok": False, "error": "Stripe is not configured."}, status=500)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        stripe_customer_id = _get_or_create_stripe_customer(customer)
        setup_intent = stripe.SetupIntent.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            metadata={
                "context": "add_payment_method",
                "user_id": str(request.user.id),
                "customer_id": str(customer.id),
            },
        )
    except Exception as exc:
        logger.exception("Failed to create Stripe SetupIntent")
        return JsonResponse({"ok": False, "error": f"Failed to create setup intent: {exc}"}, status=500)

    return JsonResponse(
        {
            "ok": True,
            "client_secret": setup_intent.client_secret,
            "setup_intent_id": setup_intent.id,
        }
    )


@login_required
@require_POST
def save_payment_method(request):
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return JsonResponse({"ok": False, "error": "Customer profile missing"}, status=400)

    payload_data = {}
    if (request.content_type or "").startswith("application/json"):
        try:
            payload_data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            logger.error("[Stripe save] invalid JSON payload: %s", exc)
    form = PaymentMethodForm(payload_data or request.POST)
    if not form.is_valid():
        return JsonResponse(
            {"ok": False, "error": "Invalid form data.", "details": form.errors},
            status=400,
        )

    setup_intent_id = (
        payload_data.get("setup_intent_id")
        or request.POST.get("setup_intent_id")
        or ""
    ).strip()
    if not setup_intent_id:
        return JsonResponse({"ok": False, "error": "Missing setup_intent_id."}, status=400)

    if not settings.STRIPE_SECRET_KEY:
        return JsonResponse({"ok": False, "error": "Stripe is not configured."}, status=500)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
    except Exception as exc:
        logger.exception("Failed to retrieve Stripe SetupIntent")
        return JsonResponse(
            {"ok": False, "error": f"Could not verify setup intent: {exc}"},
            status=400,
        )

    if getattr(setup_intent, "status", None) != "succeeded":
        return JsonResponse({"ok": False, "error": "Setup intent is not completed."}, status=400)

    stripe_customer_id = None
    for attr_name in ("stripe_customer_id", "stripe_customer"):
        value = getattr(customer, attr_name, None)
        if value:
            stripe_customer_id = str(value)
            break
    if not stripe_customer_id:
        user_value = getattr(request.user, "stripe_customer_id", None)
        if user_value:
            stripe_customer_id = str(user_value)

    setup_intent_customer = getattr(setup_intent, "customer", None)
    if stripe_customer_id and str(setup_intent_customer or "") != stripe_customer_id:
        return JsonResponse({"ok": False, "error": "Setup intent customer mismatch."}, status=400)

    payment_method_id = (getattr(setup_intent, "payment_method", None) or "").strip()
    if not payment_method_id:
        return JsonResponse({"ok": False, "error": "Setup intent missing payment method."}, status=400)

    try:
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
    except Exception as exc:
        logger.exception("Failed to retrieve Stripe PaymentMethod")
        return JsonResponse(
            {"ok": False, "error": f"Could not verify payment method: {exc}"},
            status=400,
        )

    card = getattr(pm, "card", None)
    if not card:
        return JsonResponse({"ok": False, "error": "Invalid card data."}, status=400)

    try:
        brand = (card.brand or "").lower()
        last4 = card.last4 or ""
        exp_month = card.exp_month
        exp_year = card.exp_year
    except Exception:
        logger.exception("Unexpected card payload for PaymentMethod")
        return JsonResponse({"ok": False, "error": "Invalid card data."}, status=400)

    brand_map = {
        "visa": "visa",
        "mastercard": "mastercard",
        "amex": "amex",
        "american_express": "amex",
        "discover": "discover",
    }
    card_type = brand_map.get(brand)
    if not card_type:
        return JsonResponse(
            {"ok": False, "error": f"Unsupported card brand: {brand or 'unknown'}."},
            status=400,
        )

    expiry_date = ""
    if exp_month and exp_year:
        expiry_date = f"{int(exp_month):02d}/{str(exp_year)[-2:]}"

    is_default = form.cleaned_data.get("is_default", False) or not PaymentMethod.objects.filter(customer=customer).exists()
    if is_default:
        PaymentMethod.objects.filter(customer=customer, is_default=True).update(is_default=False)

    existing = PaymentMethod.objects.filter(
        customer=customer,
        stripe_payment_method_id=payment_method_id,
    ).first()

    try:
        if existing:
            existing.cardholder_name = form.cleaned_data["cardholder_name"]
            existing.card_last4 = last4
            existing.expiry_date = expiry_date
            existing.card_type = card_type
            existing.exp_month = exp_month
            existing.exp_year = exp_year
            existing.is_default = is_default or existing.is_default
            existing.save()
        else:
            PaymentMethod.objects.create(
                customer=customer,
                cardholder_name=form.cleaned_data["cardholder_name"],
                card_last4=last4,
                expiry_date=expiry_date,
                card_type=card_type,
                is_default=is_default,
                stripe_payment_method_id=payment_method_id,
                exp_month=exp_month,
                exp_year=exp_year,
            )
    except Exception as exc:
        logger.exception("Failed to save payment method")
        return JsonResponse({"ok": False, "error": f"Failed to save card: {exc}"}, status=500)
    return JsonResponse({"ok": True})


@login_required
def Change_Password(request):
    customer = get_object_or_404(Customer, user=request.user)
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # ?????? ?????? ???? ???????? Logout
            return render(
                request,
                "accounts/sidebar/Change_Password.html",
                {
                    "form": PasswordChangeForm(request.user),
                    "customer": customer,
                    "show_popup": True,
                }
            )
    else:
        form = PasswordChangeForm(request.user)

    return render(
        request,
        "accounts/sidebar/Change_Password.html",
        {"form": form, "customer": customer}
    )

@login_required
def Service_History_and_Ratings(request):
    user = request.user
    customer = get_object_or_404(Customer, user=user)

    # ======================================================
    # 1️⃣ Past Services (COMPLETED only)
    # ======================================================
    private_done = PrivateBooking.objects.filter(user=user, status="COMPLETED").select_related("provider")
    business_done = BusinessBooking.objects.filter(user=user, status="COMPLETED").select_related("provider", "selected_bundle")
    private_title_map = _get_private_service_title_map(private_done)

    past_services = []

    for b in private_done:
        service_title = ", ".join(
            [
                private_title_map.get(service, _humanize_service_name(service))
                for service in (b.selected_services or [])
                if service
            ]
        ) or "Private Service"
        past_services.append({
            "booking_type": "private",
            "booking_id": b.id,
            "service_title": service_title,
            "provider": b.provider,
            "provider_name": (
                b.provider.get_full_name() or b.provider.username
                if b.provider else "Provider unavailable"
            ),
            "date": b.completed_at or b.created_at,
        })

    for b in business_done:
        service_title = (
            b.selected_service
            or (b.selected_bundle.title if b.selected_bundle else "")
            or "Business Service"
        )
        past_services.append({
            "booking_type": "business",
            "booking_id": b.id,
            "service_title": _humanize_service_name(service_title),
            "provider": b.provider,
            "provider_name": (
                b.provider.get_full_name() or b.provider.username
                if b.provider else "Provider unavailable"
            ),
            "date": b.completed_at or b.created_at,
        })

    past_services.sort(
        key=lambda x: (x["date"] is None, x["date"]),
        reverse=True
    )

    # ======================================================
    # 2️⃣ Filters
    # ======================================================
    q = (request.GET.get("q") or "").strip()
    service_filter = (request.GET.get("service") or "").strip()
    provider_filter = (request.GET.get("provider") or "").strip()
    date_from = (request.GET.get("from") or "").strip()
    date_to = (request.GET.get("to") or "").strip()
    parsed_from = parse_date(date_from) if date_from else None
    parsed_to = parse_date(date_to) if date_to else None
    service_types = sorted(set(s["service_title"] for s in past_services))
    providers = User.objects.filter(
        id__in=[s["provider"].id for s in past_services if s["provider"]]
    ).distinct()

    filtered = []

    for s in past_services:
        if q and q.lower() not in s["service_title"].lower():
            continue

        if service_filter and s["service_title"] != service_filter:
            continue

        if provider_filter and s["provider"]:
            if str(s["provider"].id) != provider_filter:
                continue

        if parsed_from and s["date"]:
            if s["date"].date() < parsed_from:
                continue

        if parsed_to and s["date"]:
            if s["date"].date() > parsed_to:
                continue

        filtered.append(s)

    past_services = filtered

    # ======================================================
    # 3️⃣ Reviews (ALL USER REVIEWS)
    # ======================================================
    reviews_qs = ServiceReview.objects.filter(customer=user)

    # ======================================================
    # 4️⃣ Dashboard Summary
    # ======================================================
    summary = reviews_qs.aggregate(
        avg_overall=Avg("overall_rating"),
        avg_punctuality=Avg("punctuality"),
        avg_quality=Avg("quality"),
        avg_professionalism=Avg("professionalism"),
        avg_value=Avg("value"),
        total=Count("id"),
    )

    # ======================================================
    # 5️⃣ Star Distribution
    # ======================================================
    total_reviews = summary["total"] or 0
    star_distribution = []

    for star in [5, 4, 3, 2, 1]:
        count = reviews_qs.filter(overall_rating=star).count()
        percent = int((count / total_reviews) * 100) if total_reviews else 0
        star_distribution.append({
            "star": star,
            "percent": percent,
        })

    # ======================================================
    # 6️⃣ Top Rated Providers (REAL PROVIDERS)
    # ======================================================
    top_providers = (
        User.objects
        .filter(received_service_reviews__isnull=False, provider_profile__isnull=False)
        .annotate(
            avg_rating=Avg("received_service_reviews__overall_rating"),
            total_reviews=Count("received_service_reviews"),
        )
        .select_related("provider_profile")
        .order_by("-avg_rating", "-total_reviews")[:4]
    )

    # ======================================================
    # 7️⃣ Review Status per Booking
    # ======================================================
    for item in past_services:
        review = ServiceReview.objects.filter(
            customer=user,
            booking_type=item["booking_type"],
            booking_id=item["booking_id"]
        ).first()

        item["review"] = review
        item["can_leave_comment"] = review is None

    # ======================================================
    # 8️⃣ POST – Submit Rating
    # ======================================================
    if request.method == "POST" and request.POST.get("form_type") == "rating":

        booking_type = (request.POST.get("booking_type") or "").strip()
        booking_id = (request.POST.get("booking_id") or "").strip()

        if ServiceReview.objects.filter(
            customer=user,
            booking_type=booking_type,
            booking_id=booking_id
        ).exists():
            messages.error(request, "You already rated this service.")
            return redirect(request.path)

        if booking_type == "private":
            booking = get_object_or_404(PrivateBooking, id=booking_id, user=user, status="COMPLETED")
            review_service_title = ", ".join(
                [
                    private_title_map.get(service, _humanize_service_name(service))
                    for service in (booking.selected_services or [])
                    if service
                ]
            ) or "Private Service"
        elif booking_type == "business":
            booking = get_object_or_404(BusinessBooking, id=booking_id, user=user, status="COMPLETED")
            review_service_title = _humanize_service_name(
                booking.selected_service
                or (booking.selected_bundle.title if booking.selected_bundle else "")
                or "Business Service"
            )
        else:
            messages.error(request, "Invalid booking type.")
            return redirect(request.path)

        form = ServiceReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.customer = user
            review.booking_type = booking_type
            review.booking_id = booking_id
            review.service_title = review_service_title
            review.provider = booking.provider
            review.save()

            messages.success(request, "Your rating has been saved ⭐")
            return redirect(request.path)

        messages.error(request, "Please correct the rating form and try again.")

    # ======================================================
    # 9️⃣ Filters dropdown data
    # ======================================================
    service_types = sorted(
        set(s["service_title"] for s in past_services)
    )

    providers = User.objects.filter(
        id__in=[s["provider"].id for s in past_services if s["provider"]]
    ).distinct()

    # ======================================================
    # 🔟 CONTEXT
    # ======================================================
    context = {
        "customer": customer,
        "past_services": past_services,
        "summary": summary,
        "star_distribution": star_distribution,
        "reviews": reviews_qs,
        "top_providers": top_providers,
        "rating_form": ServiceReviewForm(),
        "service_types": service_types,
        "providers": providers,
        "selected_service": service_filter,
        "selected_provider": provider_filter,
        "selected_from": date_from,
        "selected_to": date_to,
        "search_query": q,
    }

    return render(
        request,
        "accounts/sidebar/Service_History_and_Ratings.html",
        context
    )

from django.contrib.auth.decorators import login_required
from accounts.models import (
    PointsTransaction,
    Referral,
    LoyaltyTier,
)
from accounts.utils import generate_referral_code
from home.models import PrivateBooking, BusinessBooking




from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import PointsTransaction

@login_required
def Loyalty_and_Rewards(request):
    customer = get_object_or_404(Customer, user=request.user)

    # ==================================================
    # POINTS
    # ==================================================
    transactions = PointsTransaction.objects.filter(
        user=request.user
    ).order_by("-created_at")

    points_balance = sum(t.amount for t in transactions)

    # ==================================================
    # TIERS (FROM DATABASE)
    # ==================================================
    tiers = LoyaltyTier.objects.filter(is_active=True).order_by("order")

    current_tier = None
    next_tier = None
    next_tier_points = 0

    for tier in tiers:
        if tier.max_points is not None:
            if tier.min_points <= points_balance <= tier.max_points:
                current_tier = tier
                break
        else:
            if points_balance >= tier.min_points:
                current_tier = tier
                break

    if current_tier:
        next_tier = tiers.filter(order__gt=current_tier.order).first()
        if next_tier:
            next_tier_points = max(
                0,
                next_tier.min_points - points_balance
            )

    # ==================================================
    # MILESTONE 1: BOOK 5 CLEANINGS
    # ==================================================
    completed_private = PrivateBooking.objects.filter(
        user=request.user,
        status="COMPLETED"
    ).count()

    completed_business = BusinessBooking.objects.filter(
        user=request.user,
        status="COMPLETED"
    ).count()

    total_completed_bookings = completed_private + completed_business

    book_5_target = 5
    book_5_done = min(total_completed_bookings, book_5_target)
    book_5_percent = int((book_5_done / book_5_target) * 100)

    # ==================================================
    # MILESTONE 2: REFER 3 FRIENDS
    # ==================================================
    refer_target = 3

    refer_done = Referral.objects.filter(
        referrer=request.user,
        is_completed=True
    ).count()

    refer_done = min(refer_done, refer_target)
    refer_percent = int((refer_done / refer_target) * 100)

    # ==================================================
    # REFERRAL LINK
    # ==================================================
    referral = Referral.objects.filter(
        referrer=request.user,
        referred_user__isnull=True,
    ).order_by("-created_at").first()
    if not referral:
        code = generate_referral_code()
        while Referral.objects.filter(code=code).exists():
            code = generate_referral_code()
        referral = Referral.objects.create(referrer=request.user, code=code)

    referral_link = request.build_absolute_uri(
        f"{reverse('accounts:sign_up')}?ref={referral.code}"
    )

    # ==================================================
    # REWARDS (STATIC FOR NOW)
    # ==================================================

    rewards_qs = Reward.objects.filter(is_active=True)

    rewards = []
    for r in rewards_qs:
        rewards.append({
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "points_required": r.points_required,
            "can_redeem": points_balance >= r.points_required,
            "missing_points": max(0, r.points_required - points_balance),
        })

    promotion = Promotion.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).first()
    # ==================================================
    # RENDER
    # ==================================================
    return render(
        request,
        "accounts/sidebar/Loyalty_and_Rewards.html",
        {
            "customer": customer,
            "points_balance": points_balance,
            "transactions": transactions[:10],

            # tiers
            "tiers": tiers,
            "current_tier": current_tier,
            "next_tier": next_tier,
            "next_tier_points": next_tier_points,

            # milestones
            "book_5_done": book_5_done,
            "book_5_target": book_5_target,
            "book_5_percent": book_5_percent,

            "refer_done": refer_done,
            "refer_target": refer_target,
            "refer_percent": refer_percent,

            # rewards
            "rewards": rewards,  # ✅ هون

            "promotion": promotion,
            "referral_code": referral.code,
            "referral_link": referral_link,
        }
    )

@login_required
@require_POST
def redeem_reward(request, reward_id):
    reward = get_object_or_404(Reward, id=reward_id, is_active=True)

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        balance = sum(t.amount for t in user.points_transactions.all())

        if balance < reward.points_required:
            messages.error(request, "Not enough points.")
            return redirect("accounts:Loyalty_and_Rewards")

        PointsTransaction.objects.create(
            user=user,
            amount=-reward.points_required,
            reason="REWARD",
            note=f"Redeemed reward: {reward.title}"
        )

    messages.success(request, "Reward redeemed successfully.")
    return redirect("accounts:Loyalty_and_Rewards")


def logout_view(request):
    logout(request)
    return redirect("home:home")




def _get_booking_for_provider(request, booking_type, booking_id):
    if booking_type == "private":
        return get_object_or_404(PrivateBooking, id=booking_id, provider=request.user)
    if booking_type == "business":
        return get_object_or_404(BusinessBooking, id=booking_id, provider=request.user)
    raise Http404("Invalid booking type")




def _provider_required(user):
    return user.is_authenticated and (user.is_staff or hasattr(user, "provider_profile"))


@login_required
def provider_bookings(request):
    # OPTIONAL (إذا بدك تمنعي أي User عادي)
    if not _provider_required(request.user):
        raise Http404()
    private_qs = PrivateBooking.objects.filter(provider=request.user).exclude(status__in=PrivateBooking.INACTIVE_STATUSES)
    business_qs = BusinessBooking.objects.filter(provider=request.user).exclude(status__in=BusinessBooking.INACTIVE_STATUSES)


    bookings = []

    for b in private_qs:
        bookings.append({
            "type": "private",
            "id": b.id,
            "title": (b.selected_services[0] if b.selected_services else "Private Service"),
            "status": b.status,
            "when": b.appointment_date,
        })

    for b in business_qs:
        bookings.append({
            "type": "business",
            "id": b.id,
            "title": (b.selected_service or "Business Service"),
            "status": b.status,
            "when": b.start_date,
        })

    return render(request, "accounts/provider/provider_bookings.html", {"bookings": bookings})


@login_required
def provider_inbox(request):
    if request.user.is_superuser:
        return redirect("home:dashboard_home")
    if not _provider_required(request.user):
        messages.warning(request, "You do not have permission to access provider messages.")
        return redirect("accounts:customer_profile_view")

    from accounts.models import ChatThread, ChatMessage
    from home.models import BusinessBooking, PrivateBooking

    threads = ChatThread.objects.filter(provider=request.user).order_by("-created_at")
    items = []

    for thread in threads:
        booking = None
        if thread.booking_type == "private":
            booking = PrivateBooking.objects.filter(id=thread.booking_id).first()
        elif thread.booking_type == "business":
            booking = BusinessBooking.objects.filter(id=thread.booking_id).first()

        last_msg = thread.messages.order_by("-created_at").first()
        unread = ChatMessage.objects.filter(
            thread=thread,
            is_read=False
        ).exclude(sender=request.user).count()

        items.append({
            "booking_type": thread.booking_type,
            "booking_id": thread.booking_id,
            "customer_name": thread.customer.get_full_name() or thread.customer.username,
            "title": (
                booking.selected_services[0] if booking and getattr(booking, "selected_services", None)
                else (booking.selected_service if booking and getattr(booking, "selected_service", None) else "Service")
            ),
            "when": getattr(booking, "appointment_date", None) or getattr(booking, "start_date", None),
            "last_text": last_msg.text if last_msg else "",
            "last_time": last_msg.created_at if last_msg else None,
            "unread": unread,
        })

    return render(request, "accounts/provider/provider_inbox.html", {"threads": items})


@login_required
def provider_booking_detail(request, booking_type, booking_id):
    if not _provider_required(request.user):
        raise Http404()

    booking = _get_booking_for_provider(request, booking_type, booking_id)
    checklist_items = _ensure_booking_checklist_items(booking, booking_type)
    checklist_sections = _group_checklist_items(checklist_items)
    checklist_total_count = len(checklist_items)
    checklist_completed_count = sum(1 for item in checklist_items if item.is_completed)
    checklist_progress_percent = int(
        (checklist_completed_count / checklist_total_count) * 100
    ) if checklist_total_count else 0
    checklist_locked = booking.status == "COMPLETED"

    timeline = BookingStatusHistory.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id
    ).order_by("created_at")

    # =========================
    # unread messages count
    # =========================
    from accounts.models import ChatThread, ChatMessage

    unread_messages_count = 0
    try:
        thread = ChatThread.objects.get(
            booking_type=booking_type,
            booking_id=booking.id
        )

        unread_messages_count = ChatMessage.objects.filter(
            thread=thread,
            is_read=False
        ).exclude(sender=request.user).count()

    except ChatThread.DoesNotExist:
        pass

    preferences_url = ""
    if getattr(booking, "user", None):
        customer = Customer.objects.filter(user=booking.user).first()
        if customer:
            preferences_url = reverse(
                "accounts:provider_customer_preferences",
                args=[booking_type, booking.id]
            )

    return render(
        request,
        "accounts/provider/provider_booking_detail.html",
        {
            "booking": booking,
            "booking_type": booking_type,
            "timeline": timeline,
            "unread_messages_count": unread_messages_count,
            "preferences_url": preferences_url,
            "checklist_sections": checklist_sections,
            "checklist_total_count": checklist_total_count,
            "checklist_completed_count": checklist_completed_count,
            "checklist_progress_percent": checklist_progress_percent,
            "checklist_locked": checklist_locked,
        }
    )


@login_required
@require_POST
def provider_checklist_item_update(request, booking_type, booking_id, item_id):
    if not _provider_required(request.user):
        raise Http404()

    booking = _get_booking_for_provider(request, booking_type, booking_id)
    if booking.status == "COMPLETED":
        return JsonResponse({"ok": False, "error": "Checklist is locked after completion."}, status=400)

    filter_kwargs = {
        "id": item_id,
        "booking_private": booking,
    } if booking_type == "private" else {
        "id": item_id,
        "booking_business": booking,
    }
    item = get_object_or_404(BookingChecklistItem, **filter_kwargs)

    raw_completed = str(request.POST.get("is_completed", "")).strip().lower()
    is_completed = raw_completed in {"1", "true", "yes", "on"}
    item.is_completed = is_completed
    item.completed_at = timezone.now() if is_completed else None
    item.completed_by = request.user if is_completed else None
    item.save(update_fields=["is_completed", "completed_at", "completed_by", "updated_at"])

    checklist_items = _ensure_booking_checklist_items(booking, booking_type)
    total_count = len(checklist_items)
    completed_count = sum(1 for checklist_item in checklist_items if checklist_item.is_completed)
    progress_percent = int((completed_count / total_count) * 100) if total_count else 0

    return JsonResponse({
        "ok": True,
        "item_id": item.id,
        "is_completed": item.is_completed,
        "completed_at": timezone.localtime(item.completed_at).strftime("%b %d, %Y %I:%M %p") if item.completed_at else "",
        "completed_count": completed_count,
        "total_count": total_count,
        "progress_percent": progress_percent,
        "locked": booking.status == "COMPLETED",
    })



@login_required
def provider_customer_preferences(request, booking_type, booking_id):
    if not _provider_required(request.user):
        raise Http404()

    booking = _get_booking_for_provider(request, booking_type, booking_id)
    if not getattr(booking, "user", None):
        raise Http404()

    customer = Customer.objects.filter(user=booking.user).first()
    if not customer:
        raise Http404()

    prefs, _ = CustomerPreferences.objects.get_or_create(customer=customer)

    context = {
        "prefs": prefs,
        "selected_cleaning": prefs.cleaning_types or [],
        "selected_products": prefs.preferred_products or [],
        "excluded_products": prefs.excluded_products or [],
        "selected_frequency": prefs.frequency or "",
        "selected_priorities": prefs.priorities or [],
        "selected_lifestyle": prefs.lifestyle_addons or [],
        "selected_assembly": prefs.assembly_services or [],
        "products_custom": prefs.products_custom or "",
        "frequency_custom": prefs.frequency_custom or "",
        "priorities_custom": prefs.priorities_custom or "",
        "customer_name": f"{customer.first_name} {customer.last_name}".strip() or customer.user.username,
        "customer_id": customer.id,
        "booking": booking,
        "booking_type": booking_type,
    }

    return render(request, "accounts/provider/provider_customer_preferences.html", context)



@require_POST
@login_required
def provider_booking_action(request, booking_type, booking_id):

    if request.method != "POST":
        raise Http404("Invalid request")
    if not _provider_required(request.user):
        raise Http404()

    # =========================
    # GET BOOKING (FOR PROVIDER)
    # =========================
    if booking_type == "private":
        booking = get_object_or_404(
            PrivateBooking,
            id=booking_id,
            provider=request.user
        )
    elif booking_type == "business":
        booking = get_object_or_404(
            BusinessBooking,
            id=booking_id,
            provider=request.user
        )
    else:
        raise Http404("Invalid booking type")

    action = request.POST.get("action")

    try:
        # =========================
        # NORMAL FLOW ACTIONS
        # =========================
        if action == "on_the_way":
            booking.mark_on_the_way(user=request.user)
            messages.success(request, "Marked as on the way.")

        elif action == "started":
            booking.mark_started(user=request.user)
            messages.success(request, "Service started.")

        elif action == "paused":
            booking.mark_paused(user=request.user)
            messages.success(request, "Service paused.")

        elif action == "resume":
            booking.mark_resumed(user=request.user)
            messages.success(request, "Service resumed.")

        elif action == "completed":
            booking.mark_completed(user=request.user)
            messages.success(request, "Service completed.")

        # =========================
        # NO SHOW (PROVIDER REPORT)
        # =========================
        elif action == "report_no_show":
            booking.report_no_show(
                provider_user=request.user,
                note="Customer not available"
            )
            messages.info(
                request,
                "No-show reported. Waiting for admin review."
            )

        else:
            messages.error(request, "Invalid action.")

    except Exception as e:
        messages.error(request, str(e))

    return redirect(
        "accounts:provider_booking_detail",
        booking_type=booking_type,
        booking_id=booking.id
    )
@login_required
def provider_profile(request):
    if request.user.is_superuser:
        return redirect("home:dashboard_home")
    if not _provider_required(request.user):
        return redirect("accounts:customer_profile_view")

    provider_profile, _ = ProviderProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProviderProfileForm(request.POST, instance=request.user)
        location_form = ProviderLocationForm(request.POST, instance=provider_profile)
        if form.is_valid() and location_form.is_valid():
            form.save()
            location_form.save()
            messages.success(request, "Profile updated successfully")
            return redirect("accounts:provider_profile")
    else:
        form = ProviderProfileForm(instance=request.user)
        location_form = ProviderLocationForm(instance=provider_profile)

    active_private = PrivateBooking.objects.filter(
        provider=request.user
    ).exclude(status__in=PrivateBooking.INACTIVE_STATUSES).count()
    active_business = BusinessBooking.objects.filter(
        provider=request.user
    ).exclude(status__in=BusinessBooking.INACTIVE_STATUSES).count()
    completed_private = PrivateBooking.objects.filter(
        provider=request.user,
        status="COMPLETED"
    ).count()
    completed_business = BusinessBooking.objects.filter(
        provider=request.user,
        status="COMPLETED"
    ).count()

    unread_admin = ProviderAdminMessage.objects.filter(
        provider=request.user,
        is_read=False
    ).count()

    recent_admin_messages = ProviderAdminMessage.objects.filter(
        provider=request.user
    ).order_by("-created_at")[:5]

    return render(request, "accounts/provider/provider_profile.html", {
        "form": form,
        "location_form": location_form,
        "active_orders": active_private + active_business,
        "completed_orders": completed_private + completed_business,
        "unread_admin": unread_admin,
        "recent_admin_messages": recent_admin_messages,
    })

@require_POST
@login_required
def reschedule_booking(request, booking_type, booking_id):

    new_date = request.POST.get("new_date")
    new_time = request.POST.get("new_time")

    if not new_date or not new_time:
        messages.error(request, "Invalid date or time.")
        return redirect(
            "accounts:view_service_details",
            booking_type=booking_type,
            booking_id=booking_id
        )

    if booking_type == "business":
        booking = get_object_or_404(
            BusinessBooking,
            id=booking_id,
            user=request.user
        )
    else:
        booking = get_object_or_404(
            PrivateBooking,
            id=booking_id,
            user=request.user
        )

    # 🔁 تحديث الجدولة
    if booking_type == "business":
        booking.start_date = new_date
        booking.preferred_time = new_time
    else:
        booking.appointment_date = new_date
        booking.appointment_time_window = new_time

    # (اختياري) رجّع الحالة Scheduled
    booking.status = "SCHEDULED"
    booking.save()

    # 🧾 سجل بالـ Timeline
    booking.log_status(
        user=request.user,
        note=f"Rescheduled to {new_date} at {new_time}"
    )

    messages.success(request, "Your booking has been rescheduled.")

    return redirect(
        "accounts:view_service_details",
        booking_type=booking_type,
        booking_id=booking.id
    )

@login_required
def booking_chat(request, booking_type, booking_id):
    from .models import ChatThread, ChatMessage
    from home.models import BusinessBooking, PrivateBooking

    # 1️⃣ get booking
    if booking_type == "business":
        booking = get_object_or_404(BusinessBooking, id=booking_id)
    elif booking_type == "private":
        booking = get_object_or_404(PrivateBooking, id=booking_id)
    else:
        raise Http404()

    # 2️⃣ لازم يكون في provider
    if not booking.provider:
        return HttpResponse("Provider not assigned yet", status=400)

    # 3️⃣ get or create thread (صح)
    thread, _ = ChatThread.objects.get_or_create(
        booking_type=booking_type,
        booking_id=booking.id,
        defaults={
            "customer": booking.user,
            "provider": booking.provider,
        }
    )

    # 4️⃣ حماية
    if request.user not in [thread.customer, thread.provider]:
        raise Http404()

    # 5️⃣ mark messages as read
    ChatMessage.objects.filter(
        thread=thread,
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    messages = thread.messages.order_by("created_at")

    # 6️⃣ send message
    if request.method == "POST":
        text = request.POST.get("message", "").strip()
        file = request.FILES.get("file")

        if text or file:
            ChatMessage.objects.create(
                thread=thread,
                sender=request.user,
                text=text,
                file=file
            )

        return redirect(request.path)
    EMOJIS = ["😀","😁","😂","🤣","😍","😎","😭","😡","👍","👎","❤️","🔥","🎉"]
    template_name = "accounts/chat/chat_base.html"
    if request.user.is_staff and not request.user.is_superuser:
        template_name = "accounts/provider/chat/provider_chat.html"

    return render(request, template_name, {
        "thread": thread,
        "messages": messages,
        "booking": booking,
        "booking_type": booking_type,
        "emojis": EMOJIS,
    })


def service_detail(request, slug):
    service = get_object_or_404(
        PrivateService.objects.select_related(
            "category",
            "pricing",
            "estimate",
        ).prefetch_related(
            "cards",
        ),
        slug=slug,
    )

    hero_image_url = ""
    if getattr(service, "hero_image", None):
        hero_image_url = service.hero_image.url
    elif getattr(service, "image", None):
        hero_image_url = service.image.url

    start_booking_url = reverse(
        "home:private_zip_step1",
        kwargs={"service_slug": service.slug},
    )

    hero = {
        "image_url": hero_image_url,
        "title": service.title,
        "subtitle": service.hero_subtitle or "",
        "cta_text": service.hero_cta_text or "Book Your Cleaning Now",
        "cta_url": service.hero_cta_url or start_booking_url,
    }

    def _icon_markup(value):
        if not value:
            return ""
        raw = value.strip()
        if "<" in raw and ">" in raw:
            return raw
        if raw.startswith("bi-"):
            return f'<i class="bi {raw}"></i>'
        if raw.startswith("bi "):
            return f'<i class="{raw}"></i>'
        return raw

    checklist_cards = []
    for card in service.cards.all():
        checklist_cards.append({
            "icon": _icon_markup(card.icon),
            "title": card.title,
            "items": card.items(),
        })

    pricing_obj = getattr(service, "pricing", None)
    pricing = {
        "title": "Transparent Pricing",
        "subtitle": "Our pricing is straightforward. Get a personalized quote based on your home's size and needs.",
        "card_title": service.title,
        "price_label": "Starting from",
        "price_value": getattr(pricing_obj, "price_value", "") or service.starting_price,
        "price_note": getattr(pricing_obj, "price_note", ""),
        "description": "Your final price depends on your selected service and details. You'll always see the full cost before confirming your booking.",
        "cta_text": "BOOK NOW",
        "cta_url": start_booking_url,
    }

    estimate_obj = getattr(service, "estimate", None)
    estimate = {
        "title": getattr(estimate_obj, "title", None) or "Get a Quick Estimate",
        "property_label": "Property Size (m²)",
        "bedrooms_label": getattr(estimate_obj, "bedrooms_label", None) or "Number of Bedrooms",
        "cta_text": getattr(estimate_obj, "cta_text", None) or "Calculate Estimate",
        "note": getattr(estimate_obj, "note", None) or "The estimated price above reflects a 50% RUT tax deduction. Final price may vary depending on property condition.",
        "property_options": getattr(estimate_obj, "property_options", None) or [],
        "bedrooms_options": getattr(estimate_obj, "bedrooms_options", None) or [],
    }
    estimate["property_label"] = getattr(estimate_obj, "property_label", None) or "Property Size (m²)"

    eco = {
        "title": "Our Eco-Friendly Promise",
        "subtitle": (
            "We are committed to protecting our planet while providing a spotless home for you. "
            "Our cleaning methods are kind to the environment as they are tough on dirt."
        ),
        "cta_text": "Add To Cart",
        "points": [
            {
                "icon": "eco-products",
                "title": "Environmentally Safe Products",
                "body": (
                    "We use high-quality, plant-based cleaning solutions that are biodegradable "
                    "and free from harsh chemicals. Safe for your family, pets, and the earth."
                ),
            },
            {
                "icon": "sustainable-methods",
                "title": "Sustainable Methods",
                "body": (
                    "We use high-quality, plant-based cleaning solutions that are biodegradable "
                    "and free from harsh chemicals. Safe for your family, pets, and the earth."
                ),
            },
        ],
    }

    context = {
        "service": service,
        "hero": hero,
        "intro_text": service.intro_text or "",
        "checklist_title": f"Complete {service.title} Checklist",
        "checklist_cards": checklist_cards,
        "pricing": pricing,
        "estimate": estimate,
        "eco": eco,
    }
    return render(request, "accounts/services/service_detail.html", context)
