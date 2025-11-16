from django.shortcuts import render
from django.shortcuts import render, redirect


# Create your views here.
def home(request):

    return render(request , 'home/home.html',) 

def about(request):

    return render(request , 'home/about.html',) 

def contact(request):

    return render(request , 'home/contact.html',) 





