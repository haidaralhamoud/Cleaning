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

def contact_success(request):

    return render(request , 'home/contact_success.html',) 


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return render(request, "home/contact_success.html")
    else:
        form = ContactForm()

    return render(request, "home/contact.html", {"form": form})