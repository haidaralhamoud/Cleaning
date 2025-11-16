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

class Customer(models.Model):
    personal_identity_number = models.CharField(max_length=20)

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    phone = models.CharField(max_length=20)
    email = models.EmailField()

    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    postal_code = models.CharField(max_length=20)
    house_num = models.CharField(max_length=20)
    full_address = models.CharField(max_length=255)

    # Desired services: many services possible
    desired_services = models.ManyToManyField("Service")

    # Add-ons
    special_add_ons = models.CharField(max_length=10, choices=ADD_ON_CHOICES, null=True, blank=True)

    optional_note = models.TextField(blank=True, null=True)

    preferred_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES)

    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    password = models.CharField(max_length=255)

    accepted_terms = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Service(models.Model):
    key = models.CharField(max_length=50, choices=SERVICE_CHOICES, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.label
