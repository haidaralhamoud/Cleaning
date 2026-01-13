from decimal import Decimal
from .pricing_utils import calculate_booking_price
from django.shortcuts import render, redirect, get_object_or_404
from .forms import (
    ContactForm, ApplicationForm, BusinessCompanyInfoForm, OfficeSetupForm , ZipCheckForm, NotAvailableZipForm,CallRequestForm
)
from .models import (
    Job, Application, BusinessBooking, BusinessService,DateSurcharge,PrivateAddon,
    BusinessBundle, BusinessAddon ,PrivateService, AvailableZipCode,PrivateBooking,CallRequest,EmailRequest,PrivateMainCategory

)
from django.http import JsonResponse
import json
from django.contrib import messages
import json
from datetime import datetime  # فوق
from .pricing_utils import calculate_booking_price
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder

# ================================
# STATIC PAGES
# ================================
def home(request):
    return render(request, "home/home.html")

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
    booking = BusinessBooking.objects.create()
    return redirect("home:business_company_info", booking_id=booking.id)


def business_start_booking(request):
    service = request.GET.get("service")
    booking = BusinessBooking.objects.create(
    selected_service=service,
    user=request.user if request.user.is_authenticated else None
)
    booking.log_status(
    user=request.user,
    note="Order placed"
)
    return redirect("home:business_company_info", booking_id=booking.id)


# ================================
# STEP 1 — COMPANY INFO
# ================================
def business_company_info(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    if booking.path_type not in ["bundle", "custom"]:
        booking.path_type = "bundle"
        booking.save()

    total_steps = 6 if booking.path_type == "bundle" else 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        form = BusinessCompanyInfoForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            return redirect("home:business_office_setup", booking_id=booking.id)
    else:
        form = BusinessCompanyInfoForm(instance=booking)

    return render(request, "home/company_info.html", {
        "booking": booking,
        "form": form,
        "step": 1,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })


# ================================
# STEP 2 — OFFICE SETUP
# ================================
def business_office_setup(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    total_steps = 6 if booking.path_type == "bundle" else 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        form = OfficeSetupForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            return redirect("home:business_bundles", booking_id=booking.id)
    else:
        form = OfficeSetupForm(instance=booking)

    return render(request, "home/business_office_setup.html", {
        "booking": booking,
        "form": form,
        "step": 2,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })


# ================================
# STEP 3 — BUNDLES (BUNDLE PATH)
# ================================
def business_bundles(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    booking.path_type = "bundle"
    booking.save()

    total_steps = 6
    range_steps = range(1, total_steps + 1)
    bundles = BusinessBundle.objects.all()

    if request.method == "POST":
        bundle_id = request.POST.get("bundle_id")
        selected = get_object_or_404(BusinessBundle, id=bundle_id)
        booking.selected_bundle = selected
        booking.save()
        return redirect("home:business_frequency", booking_id=booking.id)

    return render(request, "home/business_bundles.html", {
        "booking": booking,
        "bundles": bundles,
        "step": 3,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })


# ================================
# STEP 3 CUSTOM — SERVICES NEEDED
# ================================
def business_services_needed(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    booking.path_type = "custom"
    booking.save()

    total_steps = 7
    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        selected_services = request.POST.get("selected_services")
        if selected_services:
            booking.services_needed = json.loads(selected_services)
            booking.save()
        return redirect("home:business_addons", booking_id=booking.id)

    return render(request, "home/business_services_needed.html", {
        "booking": booking,
        "services": BusinessService.objects.all(),
        "step": 4,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })


# ================================
# STEP 4 — ADDONS (CUSTOM PATH)
# ================================
def business_addons(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

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

        booking.addons = selected_addons
        booking.save()

        return redirect("home:business_frequency", booking_id=booking.id)

    return render(request, "home/business_addons.html", {
        "booking": booking,
        "addons": BusinessAddon.objects.all(),
        "step": 5,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })

# ================================
# STEP 4 OR 5 — FREQUENCY
# ================================
def business_frequency(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    if booking.path_type == "bundle":
        total_steps = 5
        step_number = 4
    else:
        total_steps = 7
        step_number = 6

    range_steps = range(1, total_steps + 1)

    if request.method == "POST":
        freq_raw = request.POST.get("frequency_data")
        if freq_raw:
            booking.frequency = json.loads(freq_raw)
            booking.save()
        return redirect("home:business_scheduling", booking_id=booking.id)

    return render(request, "home/business_frequency.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })


# ================================
# STEP 5 OR 6 — SCHEDULING
# ================================
def business_scheduling(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    if booking.path_type == "bundle":
        total_steps = 5
        step_number = 5
    else:
        total_steps = 7
        step_number = 7

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

        booking.start_date = start_date
        booking.preferred_time = preferred_time
        booking.days_type = request.POST.get("days_type")
        booking.custom_date = request.POST.get("custom_date") or None
        booking.custom_time = request.POST.get("custom_time") or None
        booking.notes = request.POST.get("notes")
        booking.save()

        return redirect("home:business_thank_you", booking_id=booking.id)

    return render(request, "home/SchedulingNotes.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })

# ================================
# STEP 6 OR 7 — THANK YOU
# ================================
def business_thank_you(request, booking_id):
    booking = get_object_or_404(BusinessBooking, id=booking_id)

    if booking.path_type == "bundle":
        total_steps = 6
        step_number = 6
    else:
        total_steps = 7
        step_number = 7

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
    return render(request, "home/AllServicesPrivate.html", {"services": services})





AVAILABLE_ZIPS = ["123", "111", "325", "777"]  # مؤقتاً

def private_zip_step1(request, service_slug):
    service = get_object_or_404(PrivateService, slug=service_slug)

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
                    "Thank you! We’ll contact you as soon as we expand to your area."
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




def private_booking_checkout(request, booking_id):
    booking = get_object_or_404(PrivateBooking, id=booking_id)
    services = PrivateService.objects.filter(slug__in=booking.selected_services)

    if request.method == "POST":
        booking.payment_method = request.POST.get("payment_method")
        booking.card_number = request.POST.get("card_number")
        booking.card_expiry = request.POST.get("card_expiry")
        booking.card_cvv = request.POST.get("card_cvv")
        booking.card_name = request.POST.get("card_name")
        booking.accepted_terms = True
    if booking.user is None and request.user.is_authenticated:
        booking.user = request.user

        booking.save()


        return redirect("home:thank_you_page")  # صفحة بعد الدفع
    print("ADDONS SELECTED:", booking.addons_selected)

    return render(request, "home/checkout.html", {
        "booking": booking,
        "services": services,
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

    booking = PrivateBooking.objects.create(
    booking_method="online",
    main_category=service.category.slug,
    selected_services=[service.slug],
    user=request.user if request.user.is_authenticated else None
)
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
                    service_answers[s_key][q_key] = request.POST.get(field_name, "")

        booking.service_answers = service_answers

        # 2) الـ Add-ons
        addons_json = request.POST.get("addons_selected") or "{}"

        try:
            raw_addons = json.loads(addons_json)
        except:
            raw_addons = {}

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
    return render(request, "home/YourServicesBooking.html", {
        "booking": booking,
        "services": services,
        "saved_addons": json.dumps(booking.addons_selected or {}),
        "pricing": booking.pricing_details or {},
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

    return JsonResponse({
        "status": "ok",
        "count": len(cart)
    })


def private_cart_count(request):
    cart = request.session.get("private_cart", [])
    return JsonResponse({"count": len(cart)})

def private_booking_schedule(request, booking_id):
    booking = get_object_or_404(PrivateBooking, id=booking_id)

    services = PrivateService.objects.filter(slug__in=booking.selected_services)

    # -----------------------------
    # 1) تجهيز قوانين الزيادة للـ JS
    # -----------------------------
    raw_rules = list(DateSurcharge.objects.values(
        "rule_type", "weekday", "date", "surcharge_type", "amount"
    ))
    date_rules_json = json.dumps(raw_rules, cls=DjangoJSONEncoder)

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
        "pricing": calculate_booking_price(booking),
    })


def private_price_api(request, booking_id):

    booking = get_object_or_404(PrivateBooking, id=booking_id)

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
    if days:
        try:
            booking.day_work_best = json.loads(days)
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
    if weekday:
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

    answers = booking.service_answers or {}
    answers.setdefault(service_slug, {})
    answers[service_slug][field] = value

    booking.service_answers = answers
    booking.save()

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
    booking.save()

    return JsonResponse({"success": True})    




