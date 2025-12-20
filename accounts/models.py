from django.db import models
from django.contrib.auth.models import User

# خيارات اللغات
LANGUAGE_CHOICES = [
    ('sw-ar-en', 'Swedish - Arabic - English'),
    ('ar', 'Arabic'),
    ('en', 'English'),
    ('sv', 'Swedish'),
]

# أنواع الخدمات
SERVICE_CHOICES = [
    ('home_services', 'Home Services'),
    ('repair_maintenance', 'Repair & Maintenance'),
    ('lifestyle_help', 'Lifestyle & Personal Help'),
    ('outdoor_gardening', 'Outdoor & Gardening'),
    ('moving_logistics', 'Moving & Logistics'),
]

# Special add-ons
ADD_ON_CHOICES = [
    ('one', 'One'),
    ('two', 'Two'),
    ('three', 'Three'),
]


class Service(models.Model):
    key = models.CharField(max_length=50, choices=SERVICE_CHOICES, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.label


class Customer(models.Model):
    personal_identity_number = models.CharField(max_length=20)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Basic info
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField()

    # New fields to match the profile UI
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        blank=True
    )
    pronouns = models.CharField(max_length=30, blank=True)
    country_code = models.CharField(max_length=10, blank=True)
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('sms', 'SMS'),
        ],
        blank=True
    )

    # Address fields (original)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    house_num = models.CharField(max_length=20)
    full_address = models.CharField(max_length=255)

    # Extra fields to match UI (Address & Locations)
    primary_address = models.CharField(max_length=255, blank=True)
    additional_locations = models.JSONField(default=list, blank=True)
    entry_code = models.CharField(max_length=50, blank=True)
    parking_notes = models.TextField(blank=True)

    # Emergency Contact
    emergency_first_name = models.CharField(max_length=50, blank=True)
    emergency_last_name = models.CharField(max_length=50, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)
    emergency_relation = models.CharField(max_length=100, blank=True)

    # Desired Services (existing)
    desired_services = models.ManyToManyField(Service)

    custom_addons = models.JSONField(default=list, blank=True)
    optional_note = models.TextField(blank=True, null=True)

    preferred_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    accepted_terms = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
