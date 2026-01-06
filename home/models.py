from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
User = get_user_model()

# =====================================================================
# BASE BOOKING
# =====================================================================
class BaseBooking(models.Model):

    STATUS_CHOICES = [
        # Normal flow
        ("ORDERED", "Order Placed"),
        ("SCHEDULED", "Confirmed / Scheduled"),
        ("ON_THE_WAY", "Provider On The Way"),
        ("STARTED", "Check in / Service Started"),
        ("PAUSED", "Service Paused"),
        ("COMPLETED", "Service Completed"),
        ("ASSIGNED", "Provider Assigned"),
        ("RESUMED", "Service Resumed"),
        # Exceptions
        ("CANCELLED_BY_CUSTOMER", "Cancelled by Customer"),
        ("NO_SHOW", "No Show"),
        ("INCIDENT_REPORTED", "Incident Reported"),
        ("REFUNDED", "Refunded"),
    ]

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="ORDERED")

    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)

    provider_on_way_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # (اختياري)
    INCIDENT_STATUS_CHOICES = [
        ("PENDING_REVIEW", "Pending Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]
    incident_status = models.CharField(
        max_length=30,
        choices=INCIDENT_STATUS_CHOICES,
        default="PENDING_REVIEW",
        blank=True
    )
    class Meta:
        abstract = True

    # =========================
    # INTERNAL LOGGER
    # =========================
    def _log(self, status, user=None, note=None):
        # Provider timeline
        BookingTimeline.objects.create(
            booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
            booking_id=self.id,
            status=status,
            note=note
        )

        # Customer timeline
        self.log_status(user=user, note=note or "")

    # =========================
    # STATUS ACTIONS
    # =========================
    def assign_provider(self, provider, user=None):
        self.provider = provider
        self.status = "ASSIGNED"
        self.save()
        self._log("ASSIGNED", user=user)

    def mark_on_the_way(self, user=None):
        if self.status != "ASSIGNED":
            raise ValueError("Invalid transition")

        self.status = "ON_THE_WAY"
        self.provider_on_way_at = timezone.now()
        self.save()
        self._log("ON_THE_WAY", user=user)

    def mark_started(self, user=None):
        if self.status != "ON_THE_WAY":
            raise ValueError("Invalid transition")

        self.status = "STARTED"
        self.started_at = timezone.now()
        self.save()
        self._log("STARTED", user=user)

    def mark_paused(self, user=None):
        if self.status != "STARTED":
            raise ValueError("Cannot pause now")

        self.status = "PAUSED"
        self.paused_at = timezone.now()
        self.save()
        self._log("PAUSED", user=user)

    def mark_resumed(self, user=None):
        if self.status != "PAUSED":
            raise ValueError("Cannot resume")

        self.status = "RESUMED"
        self.save()
        self._log("RESUMED", user=user)

    def mark_completed(self, user=None):
        if self.status not in ["STARTED", "PAUSED", "RESUMED"]:
            raise ValueError("Cannot complete")

        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        self.save()
        self._log("COMPLETED", user=user)

    def report_no_show(self, provider_user, note=""):
        from home.models import NoShowReport

        # لا تسمح إذا الحالة مو مناسبة
        if self.status not in ["ON_THE_WAY", "STARTED", "PAUSED", "RESUMED"]:
            raise ValueError("No Show can be reported only when service is ongoing")

        # ما تعمل أكثر من Pending
        existing = NoShowReport.objects.filter(
            booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
            booking_id=self.id,
            decision="PENDING"
        ).first()
        if existing:
            return existing

        report = NoShowReport.objects.create(
            booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
            booking_id=self.id,
            provider=provider_user,
            provider_note=note
        )

        # اختياري: سجل ب Timeline تبع المزود فقط (مو العميل)
        BookingTimeline.objects.create(
            booking_type=report.booking_type,
            booking_id=self.id,
            status="NO_SHOW_REPORTED",
            note=note
        )

        return report  
    
    def approve_no_show(self, admin_user, note=""):
        BookingTimeline.objects.create(
        booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
        booking_id=self.id,
        status="NO_SHOW_APPROVED",
        note=note
    )
        self.status = "NO_SHOW"
        self.save()
        self.log_status(user=admin_user, note=note or "No Show approved")

    def reject_no_show(self, admin_user, note=""):
        # ما نغير status
        BookingTimeline.objects.create(
            booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
            booking_id=self.id,
            status="NO_SHOW_REJECTED",
            note=note
        )

    # =========================
    # CUSTOMER HISTORY
    # =========================
    def log_status(self, user=None, note=""):
        from home.models import BookingStatusHistory

        BookingStatusHistory.objects.create(
            booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
            booking_id=self.id,
            status=self.status,
            changed_by=user,
            note=note
        )

    def cancel_by_admin(self, admin_user, note="Cancelled by admin"):
        self.status = "CANCELLED_BY_CUSTOMER"
        self.save()
        self.log_status(user=admin_user, note=note)


    def cancel_by_customer(self, user, note="Cancelled by customer"):
        if not self.can_cancel:
            raise ValueError("Cannot cancel this booking")

        self.status = "CANCELLED_BY_CUSTOMER"
        self.save()
        self.log_status(user=user, note=note)


    def _hours_to_service(self):
        if not self.scheduled_at:
            return None
        delta = self.scheduled_at - timezone.now()
        return delta.total_seconds() / 3600

    @property
    def is_instant_booking(self):
        h = self._hours_to_service()
        return (h is not None) and (h <= 3)

    @property
    def can_reschedule(self):
        # فقط ORDERED / SCHEDULED
        if self.status not in ["ORDERED", "SCHEDULED"]:
            return False

        h = self._hours_to_service()
        if h is None:
            return True  # إذا ما في موعد لسا، اسمح

        # ممنوع أقل من 12h
        return h >= 12

    @property
    def reschedule_free(self):
        h = self._hours_to_service()
        if h is None:
            return True
        return h >= 24

    @property
    def can_cancel(self):
        # ممنوع بعد ما يصير on the way / started / paused / completed
        if self.status not in ["ORDERED", "SCHEDULED"]:
            return False

        # Instant booking خلال 3 ساعات: ممنوع cancel
        if self.is_instant_booking:
            return False

        return True

    @property
    def cancel_free(self):
        h = self._hours_to_service()
        if h is None:
            return True
        return h >= 24
    # =========================
    # UI HELPERS
    # =========================
    @property
    def table_status(self):
        if self.status in ["ORDERED", "SCHEDULED", "ASSIGNED"]:
            return "upcoming"
        elif self.status in ["ON_THE_WAY", "STARTED", "PAUSED", "RESUMED"]:
            return "ongoing"
        elif self.status == "COMPLETED":
            return "completed"
        elif self.status in ["CANCELLED", "CANCELLED_BY_CUSTOMER", "NO_SHOW", "INCIDENT_REPORTED", "REFUNDED","CANCELLED_BY_CUSTOMER"]:
            return "cancelled"
        return "upcoming"

    @property
    def can_reschedule(self):
        return self.status in ["ORDERED", "SCHEDULED"]


# =====================================================================
# CONTACT / JOBS
# =====================================================================

# home/models.py

class BookingTimeline(models.Model):
    booking_type = models.CharField(max_length=20)  # private / business
    booking_id = models.PositiveIntegerField()
    status = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["created_at"]

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
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Application(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50)
    job = models.ForeignKey("Job", on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(blank=True, null=True)
    cv = models.FileField(upload_to="applications/cv/", null=True, blank=True)
    area = models.CharField(max_length=200, null=True, blank=True)
    availability = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


# =====================================================================
# BUSINESS
# =====================================================================

class BusinessService(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    recommended = models.CharField(max_length=200, blank=True, null=True)
    image = models.ImageField(upload_to="business_services/")
    icon = models.ImageField(upload_to="services/")
    description_service_aviable = models.TextField()

    def __str__(self):
        return self.title


class BusinessBundle(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    discount = models.CharField(max_length=50, blank=True, null=True)
    short_description = models.TextField(blank=True, null=True)
    target_audience = models.TextField(blank=True, null=True)
    what_included = models.JSONField(blank=True, null=True)
    why_choose = models.JSONField(blank=True, null=True)
    addons = models.JSONField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="bundles/", blank=True, null=True)

    def __str__(self):
        return self.title


class BusinessAddon(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    emoji = models.CharField(max_length=5, default="➕")

    def __str__(self):
        return self.title


class BusinessBooking(BaseBooking):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_bookings",
        null=True,
        blank=True
    )

    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_assigned_bookings"
    )

    selected_service = models.CharField(max_length=255, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(max_length=255, blank=True, null=True)
    office_address = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)

    office_size = models.CharField(max_length=255, blank=True, null=True)
    num_employees = models.CharField(max_length=255, blank=True, null=True)
    floors = models.CharField(max_length=100, blank=True, null=True)

    restrooms = models.CharField(
        max_length=10,
        choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4+", "4+")],
        blank=True,
        null=True
    )

    kitchen_cleaning = models.BooleanField(default=False)

    selected_bundle = models.ForeignKey(
        BusinessBundle,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bookings"
    )

    services_needed = models.JSONField(blank=True, null=True)
    addons = models.JSONField(blank=True, null=True)
    frequency = models.JSONField(blank=True, null=True)

    start_date = models.DateField(blank=True, null=True)
    preferred_time = models.CharField(max_length=255, blank=True, null=True)

    days_type = models.CharField(max_length=50, blank=True, null=True)
    custom_date = models.DateField(blank=True, null=True)
    custom_time = models.CharField(max_length=255, blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    path_type = models.CharField(max_length=20, default="bundle")

    def __str__(self):
        return f"Booking #{self.id}"


# =====================================================================
# PRIVATE (كلّه كامل بدون نقصان)
# =====================================================================

class PrivateMainCategory(models.Model):
    title = models.CharField(max_length=200)
    icon = models.ImageField(upload_to="private/categories/", blank=True, null=True)
    slug = models.SlugField(unique=True)

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
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    questions = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.title


class PrivateBooking(BaseBooking):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="private_bookings",
        null=True,
        blank=True
    )

    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="private_assigned_bookings"
    )

    zip_code = models.CharField(max_length=20, blank=True, null=True)
    zip_is_available = models.BooleanField(default=False)

    booking_method = models.CharField(
        max_length=20,
        choices=[("online", "Book Online Now"), ("call", "Request a Call"), ("email", "Send Email")],
        blank=True,
        null=True
    )

    main_category = models.CharField(max_length=100, blank=True, null=True)
    selected_services = models.JSONField(blank=True, null=True)
    service_answers = models.JSONField(blank=True, null=True)
    addons_selected = models.JSONField(blank=True, null=True)

    service_schedules = models.JSONField(blank=True, null=True)
    schedule_mode = models.CharField(
        max_length=20,
        default="same",
        choices=[("same", "Same"), ("per_service", "Per Service")]
    )

    appointment_date = models.DateField(blank=True, null=True)
    appointment_time_window = models.CharField(max_length=50, blank=True, null=True)
    frequency_type = models.CharField(max_length=50, blank=True, null=True)
    special_timing_requests = models.TextField(blank=True, null=True)
    day_work_best = models.JSONField(blank=True, null=True)
    End_Date = models.DateField(blank=True, null=True)

    pricing_details = models.JSONField(blank=True, null=True)

    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rot_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    address = models.CharField(max_length=255, blank=True, null=True)
    area = models.CharField(max_length=255, blank=True, null=True)
    duration_hours = models.CharField(max_length=100, blank=True, null=True)

    payment_method = models.CharField(
        max_length=50,
        choices=[("card", "Credit Card"), ("paypal", "Paypal"), ("klarna", "Klarna"), ("swish", "Swish")],
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


# =====================================================================
# ZIP / ADDONS / PRICING RULES
# =====================================================================

class AvailableZipCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    def __str__(self):
        return self.code


class NotAvailableZipRequest(models.Model):
    service = models.ForeignKey(PrivateService, on_delete=models.SET_NULL, null=True, blank=True)
    zip_code = models.CharField(max_length=20)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=50)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CallRequest(models.Model):
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50)
    email = models.EmailField()
    preferred_time = models.DateTimeField()
    message = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EmailRequest(models.Model):
    email_from = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    attachment = models.FileField(upload_to="email_attachments/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PrivateAddon(models.Model):
    service = models.ForeignKey(PrivateService, on_delete=models.CASCADE, related_name="addons_list")
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to="private/addons/", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    form_html = models.TextField(blank=True, null=True)


class ServiceQuestionRule(models.Model):
    service = models.ForeignKey(PrivateService, on_delete=models.CASCADE, related_name="pricing_rules")
    question_key = models.CharField(max_length=100)
    answer_value = models.CharField(max_length=200)
    price_change = models.DecimalField(max_digits=10, decimal_places=2)


class AddonRule(models.Model):
    addon = models.ForeignKey(PrivateAddon, on_delete=models.CASCADE, related_name="pricing_rules")
    question_key = models.CharField(max_length=100)
    answer_value = models.CharField(max_length=200)
    price_change = models.DecimalField(max_digits=10, decimal_places=2)


class ScheduleRule(models.Model):
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    price_change = models.DecimalField(max_digits=10, decimal_places=2)


class DateSurcharge(models.Model):
    rule_type = models.CharField(max_length=50, choices=[("weekday", "Weekday"), ("date", "Date")])
    weekday = models.CharField(max_length=3, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    surcharge_type = models.CharField(max_length=20, choices=[("percent", "Percent"), ("fixed", "Fixed")])
    amount = models.DecimalField(max_digits=10, decimal_places=2)



class BookingStatusHistory(models.Model):
    BOOKING_TYPE_CHOICES = [
        ("private", "Private"),
        ("business", "Business"),
    ]

    booking_type = models.CharField(max_length=10, choices=BOOKING_TYPE_CHOICES)
    booking_id = models.PositiveIntegerField()

    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]


class NoShowReport(models.Model):
    DECISION_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    booking_type = models.CharField(max_length=10, choices=[("private", "Private"), ("business", "Business")])
    booking_id = models.PositiveIntegerField()

    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="no_show_reports_sent"
    )

    decision = models.CharField(max_length=10, choices=DECISION_CHOICES, default="PENDING")
    provider_note = models.TextField(blank=True, null=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="no_show_reports_reviewed"
    )
    reviewed_note = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    # ✅ جديد: جلب الحجز
    def get_booking(self):
        from home.models import PrivateBooking, BusinessBooking
        if self.booking_type == "private":
            return PrivateBooking.objects.filter(id=self.booking_id).first()
        return BusinessBooking.objects.filter(id=self.booking_id).first()

    # ✅ جديد: تطبيق قرار الأدمن على الحجز
    def apply_decision_to_booking(self):
        booking = self.get_booking()
        if not booking:
            return

        # Approved => يصير NO_SHOW + ينضاف للتاريخ (Customer timeline)
        if self.decision == "APPROVED":
            booking.approve_no_show(
                admin_user=self.reviewed_by,
                note=self.reviewed_note or self.provider_note or "No show approved"
            )

        # Rejected => ما نغير status، بس نسجل رفض عند المزود (provider timeline)
        elif self.decision == "REJECTED":
            booking.reject_no_show(
                admin_user=self.reviewed_by,
                note=self.reviewed_note or "No show rejected"
            )

    def save(self, *args, **kwargs):
        is_update = self.pk is not None
        old_decision = None

        if is_update:
            old_decision = NoShowReport.objects.filter(pk=self.pk).values_list("decision", flat=True).first()

        super().save(*args, **kwargs)

        # ✅ طبّق فقط إذا تغير القرار من Pending إلى Approved/Rejected
        if old_decision != self.decision and self.decision in ["APPROVED", "REJECTED"]:
            # ثبت وقت المراجعة لو مو موجود
            if not self.reviewed_at:
                self.reviewed_at = timezone.now()
                super().save(update_fields=["reviewed_at"])

            self.apply_decision_to_booking()
