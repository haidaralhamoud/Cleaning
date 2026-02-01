from django.utils import timezone
import datetime
from typing import Counter
from django.db.models import Q
from django.db import IntegrityError
from django.utils.dateparse import parse_date

from django.shortcuts import render, redirect , get_object_or_404
from .forms import CustomerForm , CustomerBasicInfoForm , CustomerLocationForm ,IncidentForm , CustomerNoteForm , PaymentMethodForm ,CommunicationPreferenceForm, ServiceCommentForm, ServiceReviewForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth import logout
from accounts.models import PointsTransaction

from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.urls import reverse_lazy, reverse
from urllib.parse import urlencode
from django.contrib.auth.forms import PasswordChangeForm
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
    CustomerNotification,
    ProviderAdminMessage,
)
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from home.models import (
    BookingStatusHistory,
    BookingTimeline,
    BusinessBooking,
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
    BookingChecklistForm 
)
from django.http import HttpResponse, JsonResponse
import json
from django.db.models import Avg, Count
User = get_user_model()
from .forms import ProviderProfileForm
# ======================================================
# SIGN UP
# ======================================================
def sign_up(request):
    ref_code = request.GET.get("ref")

    if request.method == "POST":
        form = CustomerForm(request.POST, request.FILES)

        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            # 1️⃣ إنشاء User
            if User.objects.filter(username=email).exists():
                form.add_error("email", "Email is already registered.")
                return render(request, "registration/sign_up.html", {"form": form})

            try:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                )
            except IntegrityError:
                form.add_error("email", "Email is already registered.")
                return render(request, "registration/sign_up.html", {"form": form})

            # 2️⃣ إنشاء Customer
            customer = form.save(commit=False)
            customer.user = user
            customer.primary_address = (
                f"{customer.full_address}, "
                f"{customer.house_num}, "
                f"{customer.city}, "
                f"{customer.postal_code}"
            )
            customer.save()
            form.save_m2m()

            region = form.cleaned_data.get("region", "")
            contact_name = form.cleaned_data.get("contact_name", "")
            contact_phone = form.cleaned_data.get("contact_phone", "") or customer.phone
            entry_code = form.cleaned_data.get("entry_code", "")
            parking_notes = form.cleaned_data.get("parking_notes", "")

            street_address = customer.full_address or ""
            if customer.house_num and customer.house_num not in street_address:
                street_address = f"{street_address} {customer.house_num}".strip()

            allowed_countries = [c[0] for c in CustomerLocation.COUNTRY]
            location_country = customer.country if customer.country in allowed_countries else "other"

            CustomerLocation.objects.create(
                customer=customer,
                address_type="home",
                street_address=street_address or "-",
                city=customer.city,
                region=region or "-",
                postal_code=customer.postal_code,
                country=location_country,
                contact_name=contact_name,
                contact_phone=contact_phone,
                entry_code=entry_code,
                parking_notes=parking_notes,
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

                    user.has_referral_discount = True
                    user.save()

            login_url = reverse("login")
            query = urlencode({"email": email})
            return redirect(f"{login_url}?{query}")
    else:
        form = CustomerForm()

    return render(request, "registration/sign_up.html", {"form": form})




# ======================================================
# CUSTOMER PROFILE
# ======================================================
@login_required
def customer_profile_view(request):
    customer = get_object_or_404(Customer, user=request.user)

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

    def build_order_item(booking, booking_type):
        if booking_type == "private":
            title = ", ".join(booking.selected_services or []) or "Private Service"
            when = booking.appointment_date or booking.scheduled_at or booking.created_at
            order_code = f"PB-{booking.id}"
        else:
            title = (
                booking.selected_service
                or (booking.selected_bundle.title if booking.selected_bundle else "Business Service")
            )
            when = booking.start_date or booking.scheduled_at or booking.created_at
            order_code = f"BB-{booking.id}"

        if booking.status in ["ON_THE_WAY", "STARTED", "PAUSED", "RESUMED"]:
            status_label = "In Progress"
            status_class = "pill-info"
            date_label = "In Progress since"
        else:
            status_label = "Scheduled"
            status_class = "pill-warn"
            date_label = "Next Service"

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

    private_qs = PrivateBooking.objects.filter(
        user=request.user,
        status__in=active_statuses
    )

    business_qs = BusinessBooking.objects.filter(
        user=request.user,
        status__in=active_statuses
    )

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
        street_address = customer.full_address or ""
        if customer.house_num and customer.house_num not in street_address:
            street_address = f"{street_address} {customer.house_num}".strip()

        allowed_countries = [c[0] for c in CustomerLocation.COUNTRY]
        location_country = customer.country if customer.country in allowed_countries else "other"

        CustomerLocation.objects.create(
            customer=customer,
            address_type="home",
            street_address=street_address or "-",
            city=customer.city,
            region="-",
            postal_code=customer.postal_code,
            country=location_country,
            contact_name=f"{customer.first_name} {customer.last_name}".strip(),
            contact_phone=customer.phone,
            entry_code=customer.entry_code,
            parking_notes=customer.parking_notes,
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

    private_bookings = PrivateBooking.objects.filter(user=user)
    business_bookings = BusinessBooking.objects.filter(user=user)

    bookings = []
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
            "service": ", ".join(b.selected_services or []),
            "date": b.appointment_date,
            "location": b.address or b.area,
            "status": b.table_status,   # 👈 هون
        })

    for b in business_bookings:
        bookings.append({
            "id": b.id,
            "type": "Business",
            "customer_name": full_name,
            "service": b.selected_service or (
                b.selected_bundle.title if b.selected_bundle else ""
            ),
            "date": b.start_date,
            "location": b.office_address,
            "status": b.table_status,   # 👈 وهون
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
    can_rate = booking.provider is not None and not has_review
    rating_form = ServiceReviewForm()

    if request.method == "POST" and request.POST.get("form_type") == "rating":
        if not can_rate:
            messages.error(request, "You already rated this service.")
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
    if booking_type == "private":
        checklist, _ = BookingChecklist.objects.get_or_create(
            booking_private=booking
        )
    else:
        checklist, _ = BookingChecklist.objects.get_or_create(
            booking_business=booking
        )

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
# 💾 SAVE CHECKLIST (ONLY WHEN USER CLICKS SAVE)
# ===============================
    if request.method == "POST" and request.POST.get("form_type") == "checklist":

        print("POST RECEIVED ✅")
        print(request.POST)   # 🔥 هون لازم يكون فيه البيانات

        checklist_form = BookingChecklistForm(request.POST, instance=checklist)
        if checklist_form.is_valid():
            checklist_form.save()
            messages.success(request, "Checklist saved successfully.")
            return redirect(request.path)

    else:
        checklist_form = BookingChecklistForm(instance=checklist)

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

        if booking.refund_amount and booking.refund_amount > 0:
            refund_amount_text = f"Refunded amount: {booking.refund_amount} $"

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
        if quoted_time == "?":
            quoted_time = None

    if not quoted_time:
        pricing = getattr(booking, "pricing_details", None) or {}
        duration_seconds = int(pricing.get("duration_seconds", 0) or 0)
        duration_minutes = int(pricing.get("duration_minutes", 0) or 0)
        quoted_time = _format_seconds(duration_seconds) or booking.format_minutes(duration_minutes)
        quoted_seconds = max(quoted_seconds, duration_seconds, duration_minutes * 60)

    if not quoted_time:
        quoted_time = "?"



    
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
            "checklist_form": checklist_form,
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
        form = IncidentForm(request.POST, request.FILES)
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
        form = IncidentForm()

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
            return redirect(request.path + f"?booking_type={booking_type}&booking_id={booking_id}")

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
        return redirect(request.path + f"?booking_type={booking_type}&booking_id={booking_id}")

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
    customer = request.user.customer
    prefs, _ = CustomerPreferences.objects.get_or_create(customer=customer)

    # =====================================
    # 🔹 AJAX SAVE (Save صغير لكل حقل)
    # =====================================
    if request.method == "POST" and request.headers.get("Content-Type") == "application/json":
        data = json.loads(request.body)

        field = data.get("field")
        value = data.get("value", "").strip()

        if field == "preferred_products":
            if value and value not in prefs.preferred_products:
                prefs.preferred_products.append(value)

        elif field == "frequency":
            prefs.frequency = value or None

        elif field == "priorities":
            if value and value not in prefs.priorities:
                prefs.priorities.append(value)

        elif field == "cleaning_types":
            if value and value not in prefs.cleaning_types:
                prefs.cleaning_types.append(value)

        elif field == "lifestyle_addons":
            if value and value not in prefs.lifestyle_addons:
                prefs.lifestyle_addons.append(value)

        elif field == "assembly_services":
            if value and value not in prefs.assembly_services:
                prefs.assembly_services.append(value)

        prefs.save()
        return JsonResponse({"status": "ok"})

    # =====================================
    # 🔹 SAVE الكبير (يحفظ كل الصفحة)
    # =====================================
    if request.method == "POST":

        if request.POST.get("save_custom"):
            target = request.POST.get("save_custom")
            if target == "products":
                value = request.POST.get("products_custom", "").strip()
                if value:
                    prefs.products_custom = value
            elif target == "frequency":
                value = request.POST.get("frequency_custom", "").strip()
                if value:
                    prefs.frequency_custom = value
            elif target == "priorities":
                value = request.POST.get("priorities_custom", "").strip()
                if value:
                    prefs.priorities_custom = value
            prefs.save()
            return redirect("accounts:Service_Preferences")

        if "cleaning_types" in request.POST:
            prefs.cleaning_types = request.POST.getlist("cleaning_types")

        if "preferred_products" in request.POST:
            prefs.preferred_products = request.POST.getlist("preferred_products")

        if "excluded_products" in request.POST:
            prefs.excluded_products = request.POST.getlist("excluded_products")

        if "frequency" in request.POST:
            prefs.frequency = request.POST.get("frequency") or None

        if "priorities" in request.POST:
            prefs.priorities = request.POST.getlist("priorities")

        if "lifestyle_addons" in request.POST:
            prefs.lifestyle_addons = request.POST.getlist("lifestyle_addons")

        if "assembly_services" in request.POST:
            prefs.assembly_services = request.POST.getlist("assembly_services")

        products_custom = request.POST.get("products_custom", "").strip()
        frequency_custom = request.POST.get("frequency_custom", "").strip()
        priorities_custom = request.POST.get("priorities_custom", "").strip()

        if products_custom:
            prefs.products_custom = products_custom
        if frequency_custom:
            prefs.frequency_custom = frequency_custom
        if priorities_custom:
            prefs.priorities_custom = priorities_custom

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

    return render(request, "accounts/sidebar/Communication.html")


def Customer_Notes(request):
    # آخر ملاحظة للزبون الحالي (إذا في)
    notes = CustomerNote.objects.filter(
        customer=request.user
    ).order_by("-id").first()

    context = {
        "notes": notes
    }
    return render(request, "accounts/sidebar/Customer_Notes.html", context)

    return render(request, "accounts/sidebar/Customer_Notes.html")


def add_Customer_Notes(request):
    note, _ = CustomerNote.objects.get_or_create(customer=request.user)

    if request.method == "POST":
        form = CustomerNoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            # بعد الحفظ رجّع لنفس الصفحة أو لأي صفحة بدك
            return redirect("accounts:Customer_Notes")
    else:
        form = CustomerNoteForm(instance=note)

    return render(request , 'accounts/subpages/add_Customer_Notes.html',{"form": form}) 
    return render(request, "accounts/subpages/add_Customer_Notes.html")

@login_required
def Payment_and_Billing(request):
    customer = request.user.customer

    payment_methods = PaymentMethod.objects.filter(
        customer=customer
    ).order_by( "-created_at")

    invoices = Invoice.objects.filter(
        customer=customer
    ).select_related("payment_method").order_by("-issued_at")[:20]

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
def set_payment_default(request, pk):
    customer = request.user.customer

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
def delete_payment_method(request, pk):
    customer = request.user.customer

    payment = get_object_or_404(
        PaymentMethod,
        pk=pk,
        customer=customer
    )
    payment.delete()

    return redirect("accounts:Payment_and_Billing")
    return render(request, "accounts/sidebar/Payment_and_Billing.html")


def Add_Payment_Method(request):
    customer = request.user.customer

    if request.method == "POST":
        form = PaymentMethodForm(request.POST)

        if form.is_valid():
            payment = form.save(commit=False)
            payment.customer = customer

            # استخراج آخر 4 أرقام فقط
            card_number = request.POST.get("card_number", "")
            payment.card_last4 = card_number[-4:] if len(card_number) >= 4 else ""

            # إذا اختارها افتراضية → نلغي الافتراضية عن الباقي
            if payment.is_default:
                PaymentMethod.objects.filter(
                    customer=customer,
                    is_default=True
                ).update(is_default=False)

            payment.save()
            return redirect("accounts:Payment_and_Billing")
    else:
        form = PaymentMethodForm()

    return render(
        request,
        "accounts/subpages/Add_Payment_Method.html",
        {"form": form}
    )
    return render(request, "accounts/subpages/Add_Payment_Method.html")


@login_required
def Change_Password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # مهم حتى ما يطلع Logout
            return render(
                request,
                "accounts/sidebar/Change_Password.html",
                {
                    "form": PasswordChangeForm(request.user),
                    "show_popup": True,  # ⭐ هون السر
                }
            )
    else:
        form = PasswordChangeForm(request.user)

    return render(
        request,
        "accounts/sidebar/Change_Password.html",
        {"form": form}
    )
    return render(request, "accounts/sidebar/Change_Password.html")

@login_required
def Service_History_and_Ratings(request):
    user = request.user

    # ======================================================
    # 1️⃣ Past Services (COMPLETED only)
    # ======================================================
    private_done = PrivateBooking.objects.filter(user=user, status="COMPLETED")
    business_done = BusinessBooking.objects.filter(user=user, status="COMPLETED")

    past_services = []

    for b in private_done:
        past_services.append({
            "booking_type": "private",
            "booking_id": b.id,
            "service_title": ", ".join(b.selected_services or []) or "Private Service",
            "provider": b.provider,
            "date": b.completed_at or b.created_at,
        })

    for b in business_done:
        past_services.append({
            "booking_type": "business",
            "booking_id": b.id,
            "service_title": (
                b.selected_service
                or (b.selected_bundle.title if b.selected_bundle else "Business Service")
            ),
            "provider": b.provider,
            "date": b.completed_at or b.created_at,
        })

    past_services.sort(
        key=lambda x: (x["date"] is None, x["date"]),
        reverse=True
    )

    # ======================================================
    # 2️⃣ Filters
    # ======================================================
    q = request.GET.get("q")
    service_filter = request.GET.get("service")
    provider_filter = request.GET.get("provider")
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    filtered = []

    for s in past_services:
        if q and q.lower() not in s["service_title"].lower():
            continue

        if service_filter and s["service_title"] != service_filter:
            continue

        if provider_filter and s["provider"]:
            if str(s["provider"].id) != provider_filter:
                continue

        if date_from and s["date"]:
            if s["date"].date() < parse_date(date_from):
                continue

        if date_to and s["date"]:
            if s["date"].date() > parse_date(date_to):
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
        .filter(received_service_reviews__isnull=False)
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

        booking_type = request.POST.get("booking_type")
        booking_id = request.POST.get("booking_id")

        if ServiceReview.objects.filter(
            customer=user,
            booking_type=booking_type,
            booking_id=booking_id
        ).exists():
            messages.error(request, "You already rated this service.")
            return redirect(request.path)

        booking = (
            get_object_or_404(PrivateBooking, id=booking_id)
            if booking_type == "private"
            else get_object_or_404(BusinessBooking, id=booking_id)
        )

        form = ServiceReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.customer = user
            review.booking_type = booking_type
            review.booking_id = booking_id
            review.service_title = ", ".join(
                booking.selected_services or []
            )
            review.provider = booking.provider
            review.save()

            messages.success(request, "Your rating has been saved ⭐")
            return redirect(request.path)

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
        "past_services": past_services,
        "summary": summary,
        "star_distribution": star_distribution,
        "reviews": reviews_qs,
        "top_providers": top_providers,
        "rating_form": ServiceReviewForm(),
        "service_types": service_types,
        "providers": providers,
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
from home.models import PrivateBooking, BusinessBooking




from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import PointsTransaction

@login_required
def Loyalty_and_Rewards(request):

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
        }
    )

@login_required
def redeem_reward(request, reward_id):
    reward = get_object_or_404(Reward, id=reward_id, is_active=True)

    user = request.user
    balance = sum(t.amount for t in user.points_transactions.all())

    if balance < reward.points_required:
        messages.error(request, "Not enough points")
        return redirect("accounts:Loyalty_and_Rewards")

    PointsTransaction.objects.create(
        user=user,
        amount=-reward.points_required,
        reason="REWARD",
        note=f"Redeemed reward: {reward.title}"
    )

    messages.success(request, "Reward redeemed successfully 🎉")
    return redirect("accounts:Loyalty_and_Rewards")

    transactions = PointsTransaction.objects.filter(
        user=request.user
    ).order_by("-created_at")

    points_balance = sum(t.amount for t in transactions)

    # =========================
    # TIER LOGIC (SIMPLE)
    # =========================
    if points_balance >= 3000:
        current_tier = "Gold"
        next_tier_name = None
        next_tier_points = 0
    elif points_balance >= 1000:
        current_tier = "Silver"
        next_tier_name = "Gold"
        next_tier_points = 3000 - points_balance
    else:
        current_tier = "Bronze"
        next_tier_name = "Silver"
        next_tier_points = 1000 - points_balance

    # =========================
    # REWARDS (STATIC FOR NOW)
    # =========================
    rewards = [
        {
            "title": "50% Off Deep Cleaning",
            "description": "Get a deep cleaning service at half price.",
            "points_required": 1000,
            "can_redeem": points_balance >= 1000,
            "missing_points": max(0, 1000 - points_balance),
        },
        {
            "title": "Free Standard Cleaning",
            "description": "Enjoy a complimentary standard cleaning.",
            "points_required": 2000,
            "can_redeem": points_balance >= 2000,
            "missing_points": max(0, 2000 - points_balance),
        },
        {
            "title": "Free Babysitting Hour",
            "description": "One free babysitting hour from our partners.",
            "points_required": 1500,
            "can_redeem": points_balance >= 1500,
            "missing_points": max(0, 1500 - points_balance),
        },
    ]

    return render(
        request,
        "accounts/sidebar/Loyalty_and_Rewards.html",
        {
            "points_balance": points_balance,
            "transactions": transactions[:10],
            "current_tier": current_tier,
            "next_tier_name": next_tier_name,
            "next_tier_points": next_tier_points,
            "rewards": rewards,
        }
    )



# ======================================================
# LOGOUT
# ======================================================
@require_POST
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
    private_qs = PrivateBooking.objects.filter(provider=request.user).exclude(status__in=["COMPLETED", "CANCELLED"])
    business_qs = BusinessBooking.objects.filter(provider=request.user).exclude(status__in=["COMPLETED", "CANCELLED"])


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

    timeline = BookingStatusHistory.objects.filter(
        booking_type=booking_type,
        booking_id=booking.id
    ).order_by("created_at")

    # =========================
    # 🔔 unread messages count
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

    return render(
        request,
        "accounts/provider/provider_booking_detail.html",
        {
            "booking": booking,
            "booking_type": booking_type,
            "timeline": timeline,
            "unread_messages_count": unread_messages_count,  # 🔥 مهم
        }
    )



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

    if request.method == "POST":
        form = ProviderProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully")
            return redirect("accounts:provider_profile")
    else:
        form = ProviderProfileForm(instance=request.user)

    active_private = PrivateBooking.objects.filter(
        provider=request.user
    ).exclude(status__in=["COMPLETED", "CANCELLED"]).count()
    active_business = BusinessBooking.objects.filter(
        provider=request.user
    ).exclude(status__in=["COMPLETED", "CANCELLED"]).count()
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
    booking.start_date = new_date
    booking.preferred_time = new_time

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
            "eco_promise",
        ).prefetch_related(
            "cards",
            "eco_promise__points",
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
        "title": getattr(pricing_obj, "title", "Transparent Pricing"),
        "subtitle": getattr(
            pricing_obj,
            "subtitle",
            "Our pricing is straightforward. Get a personalized quote based on your home's size and needs.",
        )
        or "",
        "card_title": getattr(pricing_obj, "card_title", "") or service.title,
        "price_label": getattr(pricing_obj, "price_label", "Starting from"),
        "price_value": getattr(pricing_obj, "price_value", "") or service.starting_price,
        "price_note": getattr(pricing_obj, "price_note", ""),
        "description": getattr(pricing_obj, "description", "") or "",
        "cta_text": getattr(pricing_obj, "cta_text", "Start Your Booking"),
        "cta_url": getattr(pricing_obj, "cta_url", "") or start_booking_url,
    }

    eco_obj = getattr(service, "eco_promise", None)
    eco_points = []
    if eco_obj:
        eco_points = [
            {
                "icon": point.icon or "",
                "title": point.title,
                "body": point.body,
            }
            for point in eco_obj.points.all()
        ]
    if not eco_points:
        eco_points = [
            {
                "icon": "",
                "title": "Environmentally Safe Products",
                "body": "We use high-quality, plant-based cleaning solutions that are biodegradable and free from harsh chemicals. Safe for your family, pets, and the earth.",
            },
            {
                "icon": "",
                "title": "Sustainable Methods",
                "body": "We use high-quality, plant-based cleaning solutions that are biodegradable and free from harsh chemicals. Safe for your family, pets, and the earth.",
            },
        ]

    eco = {
        "title": getattr(eco_obj, "title", "Our Eco-Friendly Promise"),
        "subtitle": getattr(eco_obj, "subtitle", ""),
        "cta_text": getattr(eco_obj, "cta_text", "Add To Cart"),
        "points": eco_points,
    }

    context = {
        "service": service,
        "hero": hero,
        "intro_text": service.intro_text or "",
        "checklist_title": f"Complete {service.title} Checklist",
        "checklist_cards": checklist_cards,
        "pricing": pricing,
        "eco": eco,
    }
    return render(request, "accounts/services/service_detail.html", context)
