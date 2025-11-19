from django import forms
from .models import Customer, Service
import json

class CustomerForm(forms.ModelForm):
    
    # Checkbox list للـ Services
    desired_services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    # Password fields
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    # الحقل المخفي الخاص بالـ Add-Ons
    custom_addons = forms.CharField(widget=forms.HiddenInput(), required=False)

    accepted_terms = forms.BooleanField()
    
    class Meta:
        model = Customer
        fields = [
            "personal_identity_number", "first_name", "last_name",
            "phone", "email", "country", "city",
            "postal_code", "house_num", "full_address",
            "desired_services", "custom_addons", "optional_note",
            "preferred_language", "profile_photo", "password"
        ]

    def clean(self):
        cleaned = super().clean()

        # التحقق من كلمة المرور
        password = cleaned.get("password")
        confirm_password = cleaned.get("confirm_password")

        if password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match")

        # معالجة الـ Add-ons من JSON
        addons_raw = cleaned.get("custom_addons")
        try:
            cleaned["custom_addons"] = json.loads(addons_raw) if addons_raw else []
        except:
            cleaned["custom_addons"] = []

        return cleaned
