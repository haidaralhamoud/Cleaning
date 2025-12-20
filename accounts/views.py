from django.shortcuts import render, redirect
from .forms import CustomerForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from .models import Customer
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

    context = {
        "customer": customer,
    }

    return render(request,"accounts/sidebar/customer_profile_view.html",context)

def Address_and_Locations_view(request):

    return render(request , 'accounts/sidebar/Address_and_Locations_view.html',) 

def Add_Address_and_Locations(request):

    return render(request , 'accounts/subpages/Add_Address_and_Locations.html',) 


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

    return render(request , 'accounts/sidebar/incident.html',) 

def Incident_Report_order(request):

    return render(request , 'accounts/subpages/Incident_Report_order.html',) 

def Report_Incident(request):

    return render(request , 'accounts/subpages/Report_Incident.html',) 


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
