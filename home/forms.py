from django import forms
from .models import Contact ,Application, Job , BusinessBooking,NotAvailableZipRequest,CallRequest,EmailRequest, FeedbackRequest

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



class BusinessCompanyInfoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 🔵 كل الحقول إجبارية
        for field in self.fields.values():
            field.required = True

    class Meta:
        model = BusinessBooking
        fields = [
            "company_name",
            "contact_person",
            "role",
            "office_address",
            "email",
            "phone",
        ]

        widgets = {
            "company_name": forms.TextInput(attrs={"placeholder": "Enter your company name"}),
            "contact_person": forms.TextInput(attrs={"placeholder": "Enter contact person"}),
            "role": forms.TextInput(attrs={"placeholder": "Enter role"}),
            "office_address": forms.TextInput(attrs={"placeholder": "Enter office address"}),
            "email": forms.EmailInput(attrs={"placeholder": "Enter email"}),
            "phone": forms.TextInput(attrs={"placeholder": "Enter phone number"}),
        }


OFFICE_SIZE_CHOICES = [
    ("Small", "Small"),
    ("Medium", "Medium"),
    ("Large", "Large"),
]

EMPLOYEE_CHOICES = [
    ("1-10", "1–10"),
    ("11-25", "11–25"),
    ("26-50", "26–50"),
    ("50+", "+50"),
]

FLOOR_CHOICES = [
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4+", "4+"),
]

RESTROOM_CHOICES = [
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4+", "4+"),
]

class OfficeSetupForm(forms.ModelForm):

    restrooms = forms.ChoiceField(
        choices=RESTROOM_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "restroom-btn"}),
        required=True
    )

    kitchen_cleaning = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "toggle-checkbox"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # كل الحقول المطلوبة
        self.fields["office_size"].required = True
        self.fields["num_employees"].required = True
        self.fields["floors"].required = True
        self.fields["restrooms"].required = True

    class Meta:
        model = BusinessBooking
        fields = [
            "office_size",
            "num_employees",
            "floors",
            "restrooms",
            "kitchen_cleaning",
        ]

        widgets = {
            "office_size": forms.Select(attrs={"class": "hembla-select"}),
            "num_employees": forms.Select(attrs={"class": "hembla-select"}),
            "floors": forms.Select(attrs={"class": "hembla-select"}),
        }

    restrooms = forms.ChoiceField(
        choices=RESTROOM_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "restroom-btn"})
    )

    kitchen_cleaning = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "toggle-checkbox"}),
    )

    class Meta:
        model = BusinessBooking
        fields = [
            "office_size",
            "num_employees",
            "floors",
            "restrooms",
            "kitchen_cleaning",
        ]

        widgets = {
            "office_size": forms.Select(
                choices=OFFICE_SIZE_CHOICES,
                attrs={"class": "hembla-select"}
            ),
            "num_employees": forms.Select(
                choices=EMPLOYEE_CHOICES,
                attrs={"class": "hembla-select"}
            ),
            "floors": forms.Select(
                choices=FLOOR_CHOICES,
                attrs={"class": "hembla-select"}
            ),
        }


class ZipCheckForm(forms.Form):
    zip = forms.CharField(
        label="Zip Code",
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter your zip...",
        })
    )

class NotAvailableZipForm(forms.ModelForm):

    class Meta:
        model = NotAvailableZipRequest
        fields = ["first_name", "last_name", "email", "phone", "message", "zip_code"]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "Your Name"}),
            "last_name":  forms.TextInput(attrs={"placeholder": "Your Last Name"}),
            "email":      forms.EmailInput(attrs={"placeholder": "Your Email"}),
            "phone":      forms.TextInput(attrs={"placeholder": "Your Phone"}),
            "message":    forms.Textarea(attrs={"placeholder": "Your Message"}),
            "zip_code":   forms.HiddenInput(),  # نخزّن zip بدون ما يغيّرو
        }




class CallRequestForm(forms.ModelForm):
    class Meta:
        model = CallRequest
        fields = ["full_name", "phone", "email", "preferred_time", "message", "language"]

        widgets = {
            "preferred_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }        


class EmailRequestForm(forms.ModelForm):
    class Meta:
        model = EmailRequest
        fields = ["email_from", "subject", "message", "attachment"]        


class FeedbackRequestForm(forms.ModelForm):
    class Meta:
        model = FeedbackRequest
        fields = ["customer_name", "feedback_text", "rating", "service_type", "request_details"]
        widgets = {
            "customer_name": forms.TextInput(attrs={
                "placeholder": "Your name",
            }),
            "feedback_text": forms.Textarea(attrs={
                "placeholder": "Share your experience, suggestions, or feedback...",
                "rows": 5,
            }),
            "rating": forms.Select(),
            "service_type": forms.TextInput(attrs={
                "placeholder": "Service type",
            }),
            "request_details": forms.Textarea(attrs={
                "placeholder": "Describe your request",
                "rows": 4,
            }),
        }
