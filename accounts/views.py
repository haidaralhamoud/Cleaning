from django.utils import timezone
from django.shortcuts import render, redirect , get_object_or_404
from .forms import CustomerForm , CustomerBasicInfoForm , CustomerLocationForm ,IncidentForm , CustomerNoteForm , PaymentMethodForm ,CommunicationPreferenceForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth import logout
from accounts.models import PointsTransaction

from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.urls import reverse_lazy
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import logout, get_user_model
from django.contrib.auth.decorators import login_required
from .models import Customer , CustomerLocation, CustomerPreferences , Incident , CustomerNote, LoyaltyTier , PaymentMethod,CommunicationPreference ,BookingNote, PointsTransaction, Promotion, Referral, Reward
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from home.models import BookingStatusHistory, BookingTimeline
from django.contrib import messages
from home.models import BusinessBooking, PrivateBooking , BookingStatusHistory
from .models import Customer, CustomerLocation, Incident  , ChatThread, ChatMessage ,BookingChecklist
from .forms import (
    CustomerForm,
    CustomerBasicInfoForm,
    CustomerLocationForm,
    IncidentForm,
    BookingChecklistForm 
)
from django.http import HttpResponse

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
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
            )

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

            return redirect("login")
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
        basic_form = CustomerBasicInfoForm(request.POST, instance=customer)
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

    return render(
        request,
        "accounts/sidebar/customer_profile_view.html",
        {
            "customer": customer,
            "basic_form": basic_form,
            "primary_location": primary_location,
            "other_locations": other_locations,
        },
    )


# ======================================================
# ADDRESS & LOCATIONS
# ======================================================
@login_required
def Address_and_Locations_view(request):
    customer = get_object_or_404(Customer, user=request.user)

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
        {"bookings": bookings},
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
    elif booking_type == "business":
        booking = BusinessBooking.objects.filter(
            id=booking_id,
            user=request.user
        ).first()
    else:
        raise Http404("Invalid booking type")

    if not booking:
        raise Http404("Booking not found")

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


    quoted_time = booking.format_minutes(
        booking.quoted_duration_minutes
    )

    actual_time = booking.format_timedelta(
        booking.actual_duration
    )


    
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
    # ===============================
    # 1️⃣1️⃣ RENDER
    # ===============================
    return render(
        request,
        "accounts/subpages/view_service_details.html",
        {
            "booking": booking,
            "booking_type": booking_type,
            "note": booking.note.all(),
            "timeline": timeline,
            "hide_actions": hide_actions,
            "customer_unread_messages": customer_unread_messages,
            "checklist_form": checklist_form,
            "notes": notes,   # 🔥
            "quoted_time": quoted_time,
            "actual_time": actual_time,
            "actual_duration": actual_duration,
            "start_time": start_time,
            "end_time": end_time,
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
    return render(request, "accounts/subpages/Media.html")


def chat(request):
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

    return render(request, "accounts/sidebar/Communication.html", {
        "form": form,
        "pref": pref,
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

    context = {
        "payment_methods": payment_methods
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


def Service_History_and_Ratings(request):
    return render(request, "accounts/sidebar/Service_History_and_Ratings.html")


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


@login_required
def provider_bookings(request):
    # OPTIONAL (إذا بدك تمنعي أي User عادي)
    if not request.user.is_staff:
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
def provider_booking_detail(request, booking_type, booking_id):
    if not request.user.is_staff:
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
    if not request.user.is_staff:
        return redirect("accounts:provider_bookings")

    if request.method == "POST":
        form = ProviderProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully")
            return redirect("accounts:provider_profile")
    else:
        form = ProviderProfileForm(instance=request.user)

    return render(request, "accounts/provider/provider_profile.html", {
        "form": form
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
    return render(request, "accounts/chat/chat_base.html", {
        "thread": thread,
        "messages": messages,
        "booking": booking,
        "booking_type": booking_type,
        "emojis": EMOJIS,
    })
