from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


User = settings.AUTH_USER_MODEL

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
    # ⭐ Referral Discount
    has_referral_discount = models.BooleanField(default=False)
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




class ChatThread(models.Model):
    booking_type = models.CharField(max_length=20)  # private / business
    booking_id = models.PositiveIntegerField()

    customer = models.ForeignKey(
        User, related_name="customer_threads", on_delete=models.CASCADE
    )
    provider = models.ForeignKey(
        User, related_name="provider_threads", on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat {self.booking_type} #{self.booking_id}"


class ChatMessage(models.Model):
    thread = models.ForeignKey(ChatThread, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    file = models.FileField(
        upload_to="chat_files/",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Msg from {self.sender}"

# accounts/models.py


class BookingChecklist(models.Model):

    booking_private = models.OneToOneField(
        "home.PrivateBooking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="checklist"
    )

    booking_business = models.OneToOneField(
        "home.BusinessBooking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="checklist"
    )

    # Kitchen
    kitchen_counters = models.BooleanField(default=False)
    kitchen_sink = models.BooleanField(default=False)
    kitchen_floor = models.BooleanField(default=False)
    kitchen_fridge = models.BooleanField(default=False)

    # Bathroom
    bathroom_scrub = models.BooleanField(default=False)
    bathroom_mirrors = models.BooleanField(default=False)
    bathroom_floor = models.BooleanField(default=False)

    # Bedrooms
    bedroom_beds = models.BooleanField(default=False)
    bedroom_dust = models.BooleanField(default=False)
    bedroom_floor = models.BooleanField(default=False)

    # Living Room
    living_dust = models.BooleanField(default=False)
    living_vacuum = models.BooleanField(default=False)
    living_glass = models.BooleanField(default=False)

    notes = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)


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




class CommunicationPreference(models.Model):
    FREQUENCY_CHOICES = [
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("never", "Never"),
    ]

    TIME_CHOICES = [
        ("morning", "Morning"),
        ("afternoon", "Afternoon"),
        ("evening", "Evening"),
        ("any", "Any Time"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="communication_preferences"
    )

    service_reminders = models.BooleanField(default=True)
    promotions = models.BooleanField(default=True)

    frequency = models.CharField(
        max_length=10,
        choices=FREQUENCY_CHOICES,
        default="weekly"
    )

    email = models.BooleanField(default=True)
    sms = models.BooleanField(default=True)
    phone = models.BooleanField(default=False)
    push = models.BooleanField(default=True)
    in_app = models.BooleanField(default=True)

    language = models.CharField(max_length=20, default="English")
    secondary_language = models.CharField(max_length=20, blank=True, null=True)

    timing = models.CharField(
        max_length=15,
        choices=TIME_CHOICES,
        default="any"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Communication Preferences - {self.user}"
    


class BookingNote(models.Model):
    booking_type = models.CharField(max_length=10)  # private / business
    booking_id = models.PositiveIntegerField()

    text = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note for {self.booking_type} #{self.booking_id}"







class Referral(models.Model):
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made"
    )

    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referred_by",
        null=True,
        blank=True
    )

    code = models.CharField(max_length=20, unique=True)

    is_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.referrer} → {self.referred_user or 'Pending'}"


class LoyaltyTier(models.Model):
    name = models.CharField(max_length=50)

    min_points = models.PositiveIntegerField()
    max_points = models.PositiveIntegerField(null=True, blank=True)

    description = models.CharField(max_length=255)
    benefits = models.TextField()

    color = models.CharField(
        max_length=20,
        default="bronze",
        help_text="bronze / silver / gold"
    )

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)


class Reward(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()

    points_required = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)

    # مستقبلاً (optional)
    # discount_percent = models.PositiveIntegerField(null=True, blank=True)
    # free_service = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["points_required"]

    def __str__(self):
        return f"{self.title} ({self.points_required} pts)"



class Promotion(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()

    image = models.ImageField(
        upload_to="promotions/",
        blank=True,
        null=True
    )

    # مثال: 2 = Double points
    points_multiplier = models.PositiveIntegerField(
        default=1,
        help_text="1 = normal, 2 = double points, 3 = triple..."
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.title} (x{self.points_multiplier})"

    def is_current(self):
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active
            and self.start_date <= now <= self.end_date
        )

# accounts/models.py

class CustomerPreferences(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="preferences"
    )

    # ===== Cleaning Types =====
    cleaning_types = models.JSONField(default=list, blank=True)
    # example: ["standard", "deep", "move_out"]

    # ===== Products =====
    preferred_products = models.JSONField(default=list, blank=True)
    excluded_products = models.JSONField(default=list, blank=True)

    # ===== Frequency =====
    frequency = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )  # weekly / bi-weekly / monthly / on-demand

    # ===== Priorities =====
    priorities = models.JSONField(default=list, blank=True)
    # ["kitchen", "bathroom"]

    # ===== Lifestyle & Add-ons =====
    lifestyle_addons = models.JSONField(default=list, blank=True)

    # ===== Assembly & Renovations =====
    assembly_services = models.JSONField(default=list, blank=True)

    # ===== Meta =====
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.customer}"



class PointsTransaction(models.Model):

    REASON_CHOICES = [
        ("BOOKING", "Booking"),
        ("ADJUSTMENT", "Adjustment"),
        ("REWARD", "Reward"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="points_transactions"
    )

    amount = models.IntegerField()  # + أو -
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)

    booking_type = models.CharField(
        max_length=10,
        choices=[("private", "Private"), ("business", "Business")],
        null=True,
        blank=True
    )
    booking_id = models.PositiveIntegerField(null=True, blank=True)

    note = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="points_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} | {self.amount} pts"
    