from django.shortcuts import render
from django.shortcuts import render, redirect
from .forms import ContactForm

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