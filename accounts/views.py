from django.shortcuts import render, redirect
from .forms import CustomerForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

def sign_up(request):
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


def customer_profile_view(request):

    return render(request , 'accounts/customer_profile_view.html',) 

def Address_and_Locations_view(request):

    return render(request , 'accounts/Address_and_Locations_view.html',) 

def my_bookimg(request):

    return render(request , 'accounts/my_bookimg.html',) 

def incident(request):

    return render(request , 'accounts/incident.html',) 


def Service_Preferences(request):

    return render(request , 'accounts/Service_Preferences.html',) 


def Communication(request):

    return render(request , 'accounts/Communication.html',) 


def Customer_Notes(request):

    return render(request , 'accounts/Customer_Notes.html',) 

def Payment_and_Billing(request):

    return render(request , 'accounts/Payment_and_Billing.html',) 
