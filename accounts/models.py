from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

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



class CustomerLocation(models.Model):

    ADDRESS_TYPE_CHOICES = [
        ("home", "Home"),
        ("office", "Office"),
        ("vacation", "Vacation Home"),
        ("other", "Other"),
    ]
    COUNTRY = [
        ("Syria", "Syria"),
        ("office", "Office"),
        ("vacation", "Vacation Home"),
        ("other", "Other"),
    ]

    customer = models.ForeignKey(Customer,on_delete=models.CASCADE,related_name="locations")

    # ===== Address Info =====
    address_type = models.CharField(max_length=20,choices=ADDRESS_TYPE_CHOICES)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=20,choices=COUNTRY)

    # ===== Contact at location =====
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)

    # ===== Access info =====
    entry_code = models.CharField(max_length=50, blank=True)
    parking_notes = models.CharField(max_length=255, blank=True)

    # ===== Map (جاهز للمستقبل) =====
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    # ===== Behavior =====
    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # ضمان Location واحدة فقط Primary
        if self.is_primary:
            CustomerLocation.objects.filter(
                customer=self.customer,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_address_type_display()} - {self.street_address}"



class Incident(models.Model):

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="incidents"
    )

    order = models.CharField(max_length=100)

    incident_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)

    incident_datetime = models.DateTimeField()
    location = models.CharField(max_length=255)

    involved_person = models.CharField(max_length=100, blank=True)
    preferred_resolution = models.CharField(max_length=100, blank=True)

    description = models.TextField()

    evidence = models.FileField(
        upload_to="incidents/",
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Incident #{self.id} - {self.customer}"

from django.db import models
from django.conf import settings

class CustomerNote(models.Model):
    KEY_CHOICES = [
        ("mat", "Leave under mat"),
        ("garden", "Hide in the garden"),
        ("hand", "Hand directly"),
        ("custom", "Custom"),
    ]

    PRODUCTS_CHOICES = [
        ("company", "Company products"),
        ("customer", "Customer products"),
    ]

    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_note"
    )

    key_handling = models.CharField(max_length=20, choices=KEY_CHOICES, default="mat")
    key_custom_instructions = models.CharField(max_length=255, blank=True)

    alarm_code = models.CharField(max_length=50, blank=True)

    products_supplies = models.CharField(max_length=20, choices=PRODUCTS_CHOICES, default="customer")
    cleaning_material_location = models.CharField(max_length=255, blank=True)

    special_requests = models.TextField(blank=True)
    general_notes = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notes for {self.customer}"


# accounts/models.py

class PaymentMethod(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="payment_methods"
    )

    cardholder_name = models.CharField(max_length=100)
    card_last4 = models.CharField(max_length=4)
    expiry_date = models.CharField(max_length=5)  # MM/YY

    CARD_TYPES = [
        ("visa", "Visa"),
        ("mastercard", "MasterCard"),
        ("amex", "American Express"),
        ("discover", "Discover"),
    ]
    card_type = models.CharField(max_length=20, choices=CARD_TYPES)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.card_type.upper()} •••• {self.card_last4}"




