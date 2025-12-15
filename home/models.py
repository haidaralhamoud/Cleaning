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









#---------------------------------------------------------------------------------------------------------------------------------

class PrivateMainCategory(models.Model):
    title = models.CharField(max_length=200)
    icon = models.ImageField(upload_to="private/categories/", blank=True, null=True)
    slug = models.SlugField(unique=True)   # ← أضفناه
    def __str__(self):
        return self.title


class PrivateService(models.Model):
    category = models.ForeignKey(
        PrivateMainCategory,
        on_delete=models.CASCADE,
        related_name="services"
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    recommended = models.CharField(max_length=200, blank=True, null=True)

    image = models.ImageField(upload_to="private/services/", blank=True, null=True)

    # نوع الخدمة (لتسهيل الأسئلة)
    slug = models.SlugField(unique=True)

    # 🔥 السعر الأساسي للخدمة
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # كل خدمة فيها أسئلة مختلفة → JSON
    questions = models.JSONField(blank=True, null=True)

    # Add-ons الخاصة بالخدمة (ربط)
   
    def __str__(self):
        return self.title

class PrivateBooking(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)

    # -------------------------
    # STEP 1 → ZIP CODE CHECK
    # -------------------------
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    zip_is_available = models.BooleanField(default=False)

    # -------------------------
    # STEP 1.2 → BOOKING METHOD
    # (Book online, Request a Call, Send Email)
    # -------------------------
    booking_method = models.CharField(
        max_length=20,
        choices=[
            ("online", "Book Online Now"),
            ("call", "Request a Call"),
            ("email", "Send Email"),
        ],
        blank=True,
        null=True
    )


    # -------------------------
    # STEP 2 → CATEGORY SELECTION
    # (Cleaning / Family & Care / Repairs)
    # -------------------------
    main_category = models.CharField(max_length=100, blank=True, null=True)

    # خدمة واحدة فقط في البداية، لكنها قد تصبح عدة خدمات (service 1, service 2...)
    selected_services = models.JSONField(blank=True, null=True)
    # مثال: ["standard_cleaning", "deep_cleaning"]

    # -------------------------
    # STEP 3 → SERVICE QUESTIONS
    # (dynamic)
    # -------------------------
    # يتم تخزين الإجابات كلها كـ JSON مثل:
    # { "service1": { "Q1": "value", "Q2": 2, "Q3": "Option A" } }
    service_answers = models.JSONField(blank=True, null=True)

    # -------------------------
    # STEP 4 → ADD-ONS
    # -------------------------
    addons_selected = models.JSONField(blank=True, null=True)

    # -------------------------
    # STEP 5 → SCHEDULING
    # -------------------------
    service_schedules = models.JSONField(blank=True, null=True)
    schedule_mode = models.CharField(
        max_length=20,
        default="same",
        choices=[
            ("same", "Same schedule for all services"),
            ("per_service", "Separate schedule for each service"),
        ]
    )
# ----------- SAME SCHEDULE MODE -----------
    appointment_date = models.DateField(blank=True, null=True)
    appointment_time_window = models.CharField(max_length=50, blank=True, null=True)

    # Weekly / Monthly / One-time
    frequency_type = models.CharField(max_length=50, blank=True, null=True)

    # Special requests JSON → (converted to text)
    special_timing_requests = models.TextField(blank=True, null=True)

    # Best working days (list)
    day_work_best = models.JSONField(blank=True, null=True)

    # End date for recurring cleaning
    End_Date = models.DateField(blank=True, null=True)

    # 🔥 تفاصيل الأسعار (مهم للـ Checkout)
    pricing_details = models.JSONField(blank=True, null=True)

    # -------------------------
    # STEP 6 → CHECKOUT
    # -------------------------
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rot_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Location
    address = models.CharField(max_length=255, blank=True, null=True)
    area = models.CharField(max_length=255, blank=True, null=True)
    duration_hours = models.CharField(max_length=100, blank=True, null=True)

    # -------------------------
    # STEP 7 → PAYMENT
    # -------------------------
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ("card", "Credit Card"),
            ("paypal", "Paypal"),
            ("klarna", "Klarna"),
            ("swish", "Swish"),
        ],
        blank=True,
        null=True
    )

    card_number = models.CharField(max_length=50, blank=True, null=True)
    card_expiry = models.CharField(max_length=10, blank=True, null=True)
    card_cvv = models.CharField(max_length=10, blank=True, null=True)
    card_name = models.CharField(max_length=255, blank=True, null=True)

    accepted_terms = models.BooleanField(default=False)

    def __str__(self):
        return f"PrivateBooking #{self.id}"



class AvailableZipCode(models.Model):
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.code
    

    

class NotAvailableZipRequest(models.Model):
    service = models.ForeignKey(
        PrivateService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="not_available_requests"
    )
    zip_code = models.CharField(max_length=20)

    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100, blank=True)
    email      = models.EmailField()
    phone      = models.CharField(max_length=50)
    message    = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.zip_code} - {self.first_name} {self.last_name}"
    




class CallRequest(models.Model):
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50)
    email = models.EmailField()
    preferred_time = models.DateTimeField()
    message = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.phone}"    
    
class EmailRequest(models.Model):
    email_from = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    attachment = models.FileField(upload_to="email_attachments/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} - {self.email_from}"

class PrivateAddon(models.Model):
    service = models.ForeignKey(
        PrivateService,
        on_delete=models.CASCADE,
        related_name="addons_list"
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to="private/addons/", blank=True, null=True)
    # 🔥 سعر ثابت للـ Add-on
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # 🔥 سعر لكل وحدة (نوافذ، loads، سجّادة… الخ)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # HTML form
    form_html = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.service.title})"



class ServiceQuestionRule(models.Model):
    """
    قاعدة تسعير لسؤال معيّن في خدمة معيّنة.
    مثال:
      service = Standard Office Cleaning
      question_key = "size"
      answer_value = "80-120"
      price_change = +20
    """
    service = models.ForeignKey(PrivateService, on_delete=models.CASCADE, related_name="pricing_rules")
    question_key = models.CharField(max_length=100)
    answer_value = models.CharField(max_length=200)
    price_change = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.service.title} – {self.question_key} = {self.answer_value} → {self.price_change}"
class AddonRule(models.Model):
    addon = models.ForeignKey(PrivateAddon, on_delete=models.CASCADE, related_name="pricing_rules")
    question_key = models.CharField(max_length=100)
    answer_value = models.CharField(max_length=200)
    price_change = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.addon.title} – {self.question_key} = {self.answer_value} → {self.price_change}"
class ScheduleRule(models.Model):
    key = models.CharField(max_length=100)      # مثال: "frequency_type" أو "time_window"
    value = models.CharField(max_length=100)    # مثال: "weekly" أو "evening"
    price_change = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.key} = {self.value} → {self.price_change}"




class DateSurcharge(models.Model):
    DAY_CHOICES = [
        ("Mon", "Monday"),
        ("Tue", "Tuesday"),
        ("Wed", "Wednesday"),
        ("Thu", "Thursday"),
        ("Fri", "Friday"),
        ("Sat", "Saturday"),
        ("Sun", "Sunday"),
    ]

    # نوع القانون
    rule_type = models.CharField(
        max_length=50,
        choices=[
            ("weekday", "Specific Weekday"),
            ("date", "Specific Date"),
        ]
    )

    # إذا كان نوع القانون weekday
    weekday = models.CharField(max_length=3, choices=DAY_CHOICES, blank=True, null=True)

    # إذا كان نوع القانون date
    date = models.DateField(blank=True, null=True)

    # نوع الزيادة
    surcharge_type = models.CharField(
        max_length=20,
        choices=[
            ("percent", "Percent"),
            ("fixed", "Fixed Amount"),
        ]
    )

    # النسبة أو الرقم
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        if self.rule_type == "weekday":
            return f"{self.weekday} → {self.amount} ({self.surcharge_type})"
        return f"{self.date} → {self.amount} ({self.surcharge_type})"
