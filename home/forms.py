from django import forms
from .models import Contact

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
