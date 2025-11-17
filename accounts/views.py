from django.shortcuts import render, redirect
from .forms import CustomerForm

def sign_up(request):
    if request.method == "POST":
        form = CustomerForm(request.POST, request.FILES)

        if form.is_valid():
            customer = form.save(commit=False)

            # كلمة المرور (لو بدك لاحقاً تشفريها)
            customer.password = form.cleaned_data["password"]

            customer.save()

            # حفظ الـ ManyToMany
            form.save_m2m()

            return redirect("login")

    else:
        form = CustomerForm()

    return render(request, "accounts/sign_up.html", {"form": form})
