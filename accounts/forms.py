from django import forms
from .models import Customer, Service, CustomerLocation , Incident
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



class CustomerBasicInfoForm(forms.ModelForm):

    class Meta:
        model = Customer
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "country_code",
            "date_of_birth",
            "gender",
            "pronouns",
            "preferred_contact_method",
            "preferred_language",
        ]

        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "country_code": forms.TextInput(attrs={"class": "form-control"}),
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "pronouns": forms.TextInput(attrs={"class": "form-control"}),
            "preferred_contact_method": forms.Select(attrs={"class": "form-control"}),
            "preferred_language": forms.Select(attrs={"class": "form-control"}),
        }



class CustomerLocationForm(forms.ModelForm):

    class Meta:
        model = CustomerLocation
        fields = [
            "address_type",
            "street_address",
            "city",
            "region",
            "postal_code",
            "country",
            "contact_name",
            "contact_phone",
            "entry_code",
            "parking_notes",
        ]

        widgets = {
            "address_type": forms.Select(
                attrs={"class": "form-control"}
            ),
            "street_address": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "city": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "region": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "postal_code": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "country": forms.Select(
                attrs={"class": "form-control"}
            ),
            "contact_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "contact_phone": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "entry_code": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "parking_notes": forms.TextInput(
                attrs={"class": "form-control"}
            ),
        }


class IncidentForm(forms.ModelForm):

    confirm = forms.BooleanField(
        required=True,
        label="I confirm this report is accurate"
    )

    class Meta:
        model = Incident
        fields = [
            "incident_type",
            "severity",
            "order",
            "incident_datetime",
            "location",
            "involved_person",
            "preferred_resolution",
            "description",
            "evidence",
        ]

        widgets = {
            "incident_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
            "description": forms.Textarea(attrs={"rows": 4}),
        }










