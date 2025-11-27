from django.db import models

INQUIRY_CHOICES = [
    ('general', 'General Inquiry'),
    ('support', 'Support'),
    ('pricing', 'Pricing'),
    ('booking', 'Booking'),
]

class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    country_code = models.CharField(max_length=10)
    phone = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()

    inquiry_type = models.CharField(max_length=50, choices=INQUIRY_CHOICES)
    preferred_method = models.CharField(max_length=50, default='email')

    file = models.FileField(upload_to='contact_files/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"


class Job(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    job_type = models.CharField(max_length=50, default="Full Time")
    image = models.ImageField(upload_to="jobs/", blank=True, null=True)
    is_active = models.BooleanField(default=True)   # 🔥 مهمّة جداً

    def __str__(self):
        return self.title
    
class Application(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50)
    job = models.ForeignKey("Job", on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(blank=True, null=True)
    cv = models.FileField(upload_to="applications/cv/", null=True, blank=True)

    # 🔥 طلبات بدون وظيفة
    area = models.CharField(max_length=200, null=True, blank=True)
    availability = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name




FREQUENCY_CHOICES = [
    ("daily", "Daily"),
    ("several_per_week", "Several times per week"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
    ("on_demand", "On-demand"),
    ("yearly", "Yearly"),
]

TIME_CHOICES = [
    ("before_hours", "Before office hours"),
    ("during_hours", "During office hours"),
    ("after_hours", "After office hours"),
]

BOOKING_TYPE_CHOICES = [
    ("business", "Business"),
    ("private", "Private"),
]
# models.py

class BusinessService(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    recommended = models.CharField(max_length=200, blank=True, null=True)
    image = models.ImageField(upload_to="business_services/")
    icon = models.ImageField(upload_to="services/")   # ← الصورة
    description_service_aviable = models.TextField()

    def __str__(self):
        return self.title

class BusinessBundle(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    discount = models.CharField(max_length=50, blank=True, null=True)

    # الوصف القصير (موجود)
    short_description = models.TextField(blank=True, null=True)

    # 🟦 الجديد:
    target_audience = models.TextField(blank=True, null=True)   # Best for -

    # what's included → عبارة عن قائمة عناصر
    what_included = models.JSONField(blank=True, null=True)

    # why choose this bundle
    why_choose = models.JSONField(blank=True, null=True)

    # add-ons
    addons = models.JSONField(blank=True, null=True)

    # notes
    notes = models.TextField(blank=True, null=True)

    # الصورة لاحقًا (خليها optional)
    image = models.ImageField(upload_to="bundles/", blank=True, null=True)

    def __str__(self):
        return self.title

class BusinessAddon(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    emoji = models.CharField(max_length=5, default="➕")  # لتظهر الإيموجي فوق العنوان

    def __str__(self):
        return self.title


class BusinessBooking(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    # Step 1: Services
    selected_service = models.CharField(max_length=255, blank=True, null=True)

    # Step 2: Company Info
    company_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(max_length=255, blank=True, null=True)
    office_address = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)

    # Step 3: Office Setup
    office_size = models.CharField(max_length=255, blank=True, null=True)
    num_employees = models.CharField(max_length=255, blank=True, null=True)
    floors = models.CharField(max_length=100, blank=True, null=True)

    # 🔹 FIXED — لازم يكون مسموح فراغ
    restrooms = models.CharField(
        max_length=10,
        choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4+", "4+")],
        blank=True,
        null=True
    )

    kitchen_cleaning = models.BooleanField(default=False)

    # Step 4: Bundle
    selected_bundle = models.ForeignKey(
        BusinessBundle,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bookings"
    )

    # Step 5: Services Needed
    services_needed = models.JSONField(blank=True, null=True)

    # Step 6: Add-ons
    addons = models.JSONField(blank=True, null=True)

    # Step 7: Frequency
    frequency = models.JSONField(blank=True, null=True)

    # Step 8: Scheduling
    start_date = models.DateField(blank=True, null=True)
    preferred_time = models.CharField(max_length=255, blank=True, null=True)

    # 🔹 FIXED — Days of week (Mon–Fri / Weekends / Custom date / Custom time)
    days_type = models.CharField(max_length=50, blank=True, null=True)

    custom_date = models.DateField(blank=True, null=True)
    custom_time = models.CharField(max_length=255, blank=True, null=True)

    # Notes
    notes = models.TextField(blank=True, null=True)

    path_type = models.CharField(
        max_length=20,
        default="bundle",   # bundle أو custom
    )

    def __str__(self):
        return f"Booking #{self.id}"
