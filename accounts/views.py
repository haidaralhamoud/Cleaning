from django.shortcuts import render, redirect , get_object_or_404
from .forms import CustomerForm , CustomerBasicInfoForm , CustomerLocationForm ,IncidentForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth import logout
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Customer , CustomerLocation , Incident
def sign_up(request):

    if request.method == "POST":
        form = CustomerForm(request.POST, request.FILES)

        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            # 1) إنشاء User بالطريقة الصحيحة
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password
            )

            # 2) إنشاء Customer وربطه
            customer = form.save(commit=False)
            customer.user = user
            
            customer.primary_address = (
                f"{customer.full_address}, "
                f"{customer.house_num}, "
                f"{customer.city}, "
                f"{customer.postal_code}"
            )
            # 3) حفظ علاقات ManyToMany
            customer.save()
            form.save_m2m()

            return redirect("login")
    else:
        form = CustomerForm()

    return render(request, "registration/sign_up.html", {"form": form})
    if request.method == "POST":
        form = CustomerForm(request.POST, request.FILES)

        if form.is_valid():
            # 1) إنشاء User تبع Django
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            user = User.objects.create(
                username=email,
                email=email,
                password=make_password(password)
            )

            # 2) إنشاء Customer وربطه بالمستخدم
            customer = form.save(commit=False)
            customer.user = user
            customer.save()

            # 3) حفظ العلاقات (ManyToMany)
            form.save_m2m()

            return redirect('login')

    else:
        form = CustomerForm()

    return render(request, "registration/sign_up.html", {"form": form})

    # Sidebar


@login_required
def customer_profile_view(request):
    customer = Customer.objects.get(user=request.user)

    if request.method == "POST":
        basic_form = CustomerBasicInfoForm(
            request.POST,
            instance=customer
        )

        if basic_form.is_valid():
            # نحفظ Basic Information
            customer = basic_form.save(commit=False)

            # نحفظ Emergency Contact
            customer.emergency_first_name = request.POST.get(
                "emergency_first_name", ""
            )
            customer.emergency_last_name = request.POST.get(
                "emergency_last_name", ""
            )
            customer.emergency_phone = request.POST.get(
                "emergency_phone", ""
            )
            customer.emergency_relation = request.POST.get(
                "emergency_relation", ""
            )

            customer.save()
    else:
        basic_form = CustomerBasicInfoForm(instance=customer)

    # ===== Address & Locations (NEW) =====
    primary_location = CustomerLocation.objects.filter(
        customer=customer,
        is_primary=True
    ).first()

    other_locations = CustomerLocation.objects.filter(
        customer=customer,
        is_primary=False
    )

    context = {
        "customer": customer,
        "basic_form": basic_form,

        # new context
        "primary_location": primary_location,
        "other_locations": other_locations,
    }

    return render(
        request,
        "accounts/sidebar/customer_profile_view.html",
        context
    )

#  Start Address_and_Locations
@login_required
def Address_and_Locations_view(request):
    customer = Customer.objects.get(user=request.user)

    locations = CustomerLocation.objects.filter(
        customer=customer
    ).order_by("-is_primary", "-created_at")

    context = {
        "customer": customer,
        "locations": locations,
    }

    return render(request,"accounts/sidebar/Address_and_Locations_view.html",context)

@login_required
def set_location_primary(request, location_id):
    customer = Customer.objects.get(user=request.user)

    location = get_object_or_404(
        CustomerLocation,
        id=location_id,
        customer=customer
    )

    # شيل primary عن الكل
    CustomerLocation.objects.filter(
        customer=customer,
        is_primary=True
    ).update(is_primary=False)

    # خلي المختار primary
    location.is_primary = True
    location.save()

    return redirect("accounts:Address_and_Locations_view")

@login_required
def delete_location(request, location_id):
    customer = Customer.objects.get(user=request.user)

    location = get_object_or_404(
        CustomerLocation,
        id=location_id,
        customer=customer
    )

    location.delete()
    return redirect("accounts:Address_and_Locations_view")

@login_required
def edit_address_and_locations(request, location_id):
    customer = Customer.objects.get(user=request.user)

    location = get_object_or_404(
        CustomerLocation,
        id=location_id,
        customer=customer
    )

    if request.method == "POST":
        form = CustomerLocationForm(
            request.POST,
            instance=location
        )

        if form.is_valid():
            form.save()
            return redirect("accounts:Address_and_Locations_view")
    else:
        form = CustomerLocationForm(instance=location)

    context = {
        "customer": customer,
        "form": form,
        "location": location,
        "is_edit": True,
    }

    return render(request, "accounts/subpages/Add_Address_and_Locations.html", context)

@login_required
def Add_Address_and_Locations(request):
    customer = Customer.objects.get(user=request.user)

    if request.method == "POST":
        form = CustomerLocationForm(request.POST)

        if form.is_valid():
            location = form.save(commit=False)
            location.customer = customer

            # إذا ما عندو ولا Location قبل => خلي هادي Primary
            if not CustomerLocation.objects.filter(customer=customer).exists():
                location.is_primary = True

            location.save()
            return redirect("accounts:Address_and_Locations_view")
    else:
        form = CustomerLocationForm()

    context = {
        "customer": customer,
        "form": form,
    }
    return render(request, "accounts/subpages/Add_Address_and_Locations.html", context)

#  End Address_and_Locations


def my_bookimg(request):

    return render(request , 'accounts/sidebar/my_bookimg.html',) 

def view_service_details(request):

    return render(request , 'accounts/subpages/view_service_details.html',) 

def Add_on_Service_Request(request):

    return render(request , 'accounts/subpages/Add_on_Service_Request.html',) 

def Media(request):

    return render(request , 'accounts/subpages/Media.html',) 



def chat(request):

    return render(request , 'accounts/subpages/chat.html',) 


def incident(request):
    incidents = Incident.objects.filter(customer=request.user).order_by("-created_at")

    return render(request , 'accounts/sidebar/incident.html',{"incidents": incidents}) 

def Incident_Report_order(request,incident_id):
    incident = Incident.objects.get(id=incident_id, customer=request.user)

    return render(request , 'accounts/subpages/Incident_Report_order.html',{"incident": incident}) 

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
                }
            )
    else:
        form = IncidentForm()

    return render(
        request,
        "accounts/subpages/Report_Incident.html",
        {"form": form}
    )



def Service_Preferences(request):

    return render(request , 'accounts/sidebar/Service_Preferences.html',) 


def Communication(request):

    return render(request , 'accounts/sidebar/Communication.html',) 



def Customer_Notes(request):

    return render(request , 'accounts/sidebar/Customer_Notes.html',) 

def add_Customer_Notes(request):

    return render(request , 'accounts/subpages/add_Customer_Notes.html',) 


def Payment_and_Billing(request):

    return render(request , 'accounts/sidebar/Payment_and_Billing.html',) 

def Add_Payment_Method(request):

    return render(request , 'accounts/subpages/Add_Payment_Method.html',) 

def Change_Password(request):

    return render(request , 'accounts/sidebar/Change_Password.html',)

def Service_History_and_Ratings(request):

    return render(request , 'accounts/sidebar/Service_History_and_Ratings.html',)

def Loyalty_and_Rewards(request):

    return render(request , 'accounts/sidebar/Loyalty_and_Rewards.html',)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home:home")