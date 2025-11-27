from django.shortcuts import render, redirect, get_object_or_404
from .forms import (
    ContactForm, ApplicationForm, BusinessCompanyInfoForm, OfficeSetupForm
)
from .models import (
    Job, Application, BusinessBooking, BusinessService,
    BusinessBundle, BusinessAddon
)
from django.http import JsonResponse
import json


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
    booking = BusinessBooking.objects.create(selected_service=service)
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

    return render(request, "home/business_thank_you.html", {
        "booking": booking,
        "step": step_number,
        "total_steps": total_steps,
        "range_total_steps": range_steps,
    })
