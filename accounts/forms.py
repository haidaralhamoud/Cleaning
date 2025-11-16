from django import forms
from .models import Customer, Service

class CustomerForm(forms.ModelForm):

    desired_services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    accepted_terms = forms.BooleanField()

    class Meta:
        model = Customer
        fields = [
            "personal_identity_number", "first_name", "last_name",
            "phone", "email", "country", "city",
            "postal_code", "house_num", "full_address",
            "desired_services", "special_add_ons", "optional_note",
            "preferred_language", "profile_photo", "password"
        ]

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm_password = cleaned.get("confirm_password")

        if password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match")

        return cleaned
