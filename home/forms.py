from django import forms
from .models import Contact ,Application, Job

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'hembla-field'}),
            'last_name': forms.TextInput(attrs={'class': 'hembla-field'}),
            'email': forms.EmailInput(attrs={'class': 'hembla-field'}),
            'country_code': forms.TextInput(attrs={'class': 'hembla-field'}),
            'phone': forms.TextInput(attrs={'class': 'hembla-field'}),
            'message': forms.Textarea(attrs={'class': 'hembla-field'}),
            'inquiry_type': forms.Select(attrs={'class': 'hembla-field'}),
            'preferred_method': forms.TextInput(attrs={'class': 'hembla-field'}),
            'file': forms.ClearableFileInput(attrs={'class': 'hembla-field'}),
        }

class ApplicationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["job"].required = False

        for field in self.fields.values():
            field.widget.attrs["class"] = "hembla-field"

    class Meta:
        model = Application
        fields = ["full_name", "email", "phone", "job", "message", "cv", "area", "availability"]

        widgets = {
            "message": forms.Textarea(attrs={"placeholder": "Why are you interested?"}),
            "full_name": forms.TextInput(attrs={"placeholder": "Full Name"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "phone": forms.TextInput(attrs={"placeholder": "Phone Number"}),
            "area": forms.TextInput(attrs={"placeholder": "Preferred Role / Area of Interest"}),
            "availability": forms.TextInput(attrs={"placeholder": "Availability"}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["job"].required = False

    class Meta:
        model = Application
        fields = ["full_name", "email", "phone", "job", "message", "cv", "area", "availability"]

        widgets = {
            "full_name": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Full Name"}),
            "email": forms.EmailInput(attrs={"class": "hembla-field", "placeholder": "Email"}),
            "phone": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Phone Number"}),
            "job": forms.Select(attrs={"class": "hembla-field"}),
            "message": forms.Textarea(attrs={"class": "hembla-field", "placeholder": "Why are you interested?"}),
            "cv": forms.ClearableFileInput(attrs={"class": "hembla-field"}),

            # 🔥 هدول كانوا بدون ستايل — نرجعهم
            "area": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Preferred Role / Area of Interest"}),
            "availability": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Availability"}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 🔥 خلي "job" اختياري
        self.fields["job"].required = False

    class Meta:
        model = Application
        fields = ["full_name", "email", "phone", "job", "message", "cv", "area", "availability"]

        widgets = {
            "full_name": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Full Name"}),
            "email": forms.EmailInput(attrs={"class": "hembla-field", "placeholder": "Email"}),
            "phone": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Phone Number"}),
            "job": forms.Select(attrs={"class": "hembla-field"}),
            "message": forms.Textarea(attrs={"class": "hembla-field", "placeholder": "Why are you interested?"}),
            "cv": forms.ClearableFileInput(attrs={"class": "hembla-field"}),
            "area": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Preferred Role / Area of Interest"}),
            "availability": forms.TextInput(attrs={"class": "hembla-field", "placeholder": "Availability"}),
        }