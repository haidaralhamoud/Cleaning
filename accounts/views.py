from django.shortcuts import render
from django.shortcuts import render, redirect
from .forms import CustomerForm




def sign_up(request):
    if request.method == "POST":
        form = CustomerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = CustomerForm()

    return render(request, "accounts/sign_up.html", {"form": form})


