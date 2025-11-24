from django.shortcuts import render
from django.shortcuts import render, redirect
from .forms import ContactForm , ApplicationForm
from .models import Job,Application

# Create your views here.
def home(request):

    return render(request , 'home/home.html',) 

def about(request):

    return render(request , 'home/about.html',) 



def Privacy_Policy(request):

    return render(request , 'home/Privacy_Policy.html',) 


def faq(request):

    return render(request , 'home/FAQ.html',) 


def Accessibility_Statement(request):

    return render(request , 'home/Accessibility_Statement.html',) 

def Cookies_Policy(request):

    return render(request , 'home/Cookies_Policy.html',) 


def T_C(request):

    return render(request , 'home/T&C.html',) 

def contact(request):
    show_popup = False  # المتغير الافتراضي

    if request.method == "POST":
        form = ContactForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            show_popup = True  # عرض البوب أب بعد الحفظ
    else:
        form = ContactForm()

    return render(request, "home/contact.html", {
        "form": form,
        "show_popup": show_popup
    })

def careers_home(request):
    jobs = Job.objects.filter(is_active=True)

    if jobs.exists():
        return render(request, "home/career_page.html", {"jobs": jobs})

    # لا يوجد وظائف → هنا نستقبل الفورم اليدوي
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        area = request.POST.get("area")
        availability = request.POST.get("availability")
        message = request.POST.get("message")
        cv = request.FILES.get("cv")

        Application.objects.create(
            full_name=full_name,
            email=email,
            phone=phone,
            area=area,
            availability=availability,
            message=message,
            cv=cv,
            job=None,   # لأنه ما في وظيفة متاحة حالياً
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
