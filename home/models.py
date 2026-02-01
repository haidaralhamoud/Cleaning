from decimal import Decimal
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone

from accounts.models import ChatThread, DiscountCode
User = get_user_model()

# =====================================================================
# BASE BOOKING
# =====================================================================
class BaseBooking(models.Model):

    STATUS_CHOICES = [
        ("ORDERED", "Order Placed"),
        ("SCHEDULED", "Confirmed / Scheduled"),
        ("ASSIGNED", "Provider Assigned"),
        ("ON_THE_WAY", "Provider On The Way"),
        ("STARTED", "Check in / Service Started"),
        ("PAUSED", "Service Paused"),
        ("RESUMED", "Service Resumed"),
        ("COMPLETED", "Service Completed"),

        # Exceptions
        ("CANCELLED_BY_CUSTOMER", "Cancelled by Customer"),
        ("NO_SHOW", "No Show"),
        ("INCIDENT_REPORTED", "Incident Reported"),
        ("REFUNDED", "Refunded"),
    ]

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="ORDERED"
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)

    provider_on_way_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    quoted_duration_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Expected service duration in minutes"
    )

    # =========================
    # ✅ REFUND FIELDS (NEW)
    # =========================
    is_refunded = models.BooleanField(default=False)

    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    refund_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    refunded_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        abstract = True

    # =========================
    # LOYALTY (ADMIN CONTROLLED)
    # =========================
    points_awarded = models.IntegerField(
        null=True,
        blank=True,
        help_text="Points decided by admin after completion"
    )

    points_note = models.CharField(
        max_length=255,
        blank=True
    )

    points_processed = models.BooleanField(
        default=False,
        help_text="Prevent double points processing"
    )
    # =========================
    # INTERNAL LOGGER
    # =========================
    def _log(self, status, note=None):
        from home.models import BookingTimeline

        BookingTimeline.objects.create(
            booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
            booking_id=self.id,
            status=status,
            note=note
        )

    def log_status(self, user=None, note=""):
        from home.models import BookingStatusHistory

        BookingStatusHistory.objects.create(
            booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
            booking_id=self.id,
            status=self.status,
            changed_by=user,
            note=note
        )

    # =========================
    # REFUND ACTION (🔥 الأساس)
    # =========================
    def refund(self, amount, user=None, reason=""):

        from home.models import BookingStatusHistory

        booking_type = (
            "private"
            if self.__class__.__name__ == "PrivateBooking"
            else "business"
        )

        if amount <= 0:
            raise ValueError("Refund amount must be greater than zero")

        # ✅ فقط Private
        if booking_type == "private" and amount > self.total_price:
            raise ValueError("Refund amount cannot exceed total price")

        self.is_refunded = True
        self.refund_amount = amount
        self.refund_reason = reason
        self.refunded_at = timezone.now()
        self.status = "REFUNDED"
        self.save()

        BookingStatusHistory.objects.get_or_create(
            booking_type=booking_type,
            booking_id=self.id,
            status="REFUNDED",
            defaults={
                "changed_by": user,
                "note": reason
            }
        )

    def mark_on_the_way(self, user=None):
        if self.status != "ASSIGNED":
            return

        self.status = "ON_THE_WAY"
        self.provider_on_way_at = timezone.now()
        self.save(update_fields=["status", "provider_on_way_at"])

        self.log_status(user=user, note="Provider on the way")
        self._log(status="ON_THE_WAY", note="Provider on the way")


    def mark_started(self, user=None):
        if self.status != "ON_THE_WAY":
            return

        self.status = "STARTED"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

        self.log_status(user=user, note="Service started")
        self._log(status="STARTED", note="Service started")

    def mark_paused(self, user=None):
        if self.status != "STARTED":
            return

        self.status = "PAUSED"
        self.paused_at = timezone.now()
        self.save(update_fields=["status", "paused_at"])

        self.log_status(user=user, note="Service paused")
        self._log(status="PAUSED", note="Service paused")

    def mark_resumed(self, user=None):
        if self.status != "PAUSED":
            return

        self.status = "RESUMED"
        self.save(update_fields=["status"])

        self.log_status(user=user, note="Service resumed")
        self._log(status="RESUMED", note="Service resumed")

    def mark_completed(self, user=None):
        if self.status not in ["STARTED", "RESUMED"]:
            return

        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

        self.log_status(user=user, note="Service completed")
        self._log(status="COMPLETED", note="Service completed")

        # ==================================================
        # ⭐ LOYALTY POINTS (ONLY ONCE)
        # ==================================================
        if not self.points_processed and self.user:

            from accounts.models import PointsTransaction, Referral, Customer
            from accounts.models import Promotion

            base_points = int(self.total_price * 5)

            promo = Promotion.objects.filter(
                is_active=True,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            ).first()

            multiplier = promo.points_multiplier if promo else 1
            points = base_points * multiplier

            if points > 0:
                PointsTransaction.objects.create(
                    user=self.user,
                    amount=points,
                    reason="BOOKING",
                    booking_type="private" if self.__class__.__name__ == "PrivateBooking" else "business",
                    booking_id=self.id,
                    note=f"Completed booking #{self.id}",
                    created_by=user
                )

            # ==================================================
            # 🤝 REFERRAL LOGIC
            # ==================================================
            referral = Referral.objects.filter(
                referred_user=self.user,
                is_completed=False
            ).first()

            if referral:
                # 🎁 500 نقطة للـ referrer
                PointsTransaction.objects.create(
                    user=referral.referrer,
                    amount=500,
                    reason="REWARD",
                    note=f"Referral reward – User {self.user.id}",
                    created_by=user
                )

                # 🎯 تفعيل خصم 10% للمستخدم المحال
                customer = Customer.objects.filter(user=self.user).first()
                if customer:
                    customer.has_referral_discount = True
                    customer.save(update_fields=["has_referral_discount"])

                referral.is_completed = True
                referral.save(update_fields=["is_completed"])

            # 🔒 منع التكرار
            self.points_processed = True
            self.points_awarded = points
            self.points_note = "Auto awarded on completion"
            self.save(update_fields=[
                "points_processed",
                "points_awarded",
                "points_note"
            ])

    def assign_provider(self, provider, user=None):
        if self.provider == provider and self.status != "ORDERED":
            return

        self.provider = provider
        self.status = "ASSIGNED"
        self.save(update_fields=["provider", "status"])

        # 🔥 إنشاء ChatThread إذا ما موجود
        ChatThread.objects.get_or_create(
            booking_type="business",  # أو private
            booking_id=self.id,
            defaults={
                "customer": self.user,
                "provider": provider,
            }
        )

        self.log_status(user=user, note=f"Assigned to provider {provider}")
        self._log(status="ASSIGNED", note=f"Provider assigned: {provider}")

    def report_no_show(self, provider_user, note=""):
        from home.models import NoShowReport

        booking_type = (
            "private"
            if self.__class__.__name__ == "PrivateBooking"
            else "business"
        )

        # لا نسمح بتكرار No Show
        if self.status in ["NO_SHOW", "REFUNDED", "CANCELLED_BY_CUSTOMER"]:
            return

        NoShowReport.objects.create(
            booking_type=booking_type,
            booking_id=self.id,
            provider=provider_user,
            provider_note=note,
        )

        # log for admin visibility without changing booking status
        from home.models import BookingStatusHistory, BookingTimeline
        BookingStatusHistory.objects.create(
            booking_type=booking_type,
            booking_id=self.id,
            status="NO_SHOW_REPORTED",
            changed_by=provider_user,
            note=note or "No show reported by provider"
        )
        BookingTimeline.objects.create(
            booking_type=booking_type,
            booking_id=self.id,
            status="NO_SHOW_REPORTED",
            note=note or "No show reported by provider"
        )

    # =========================
    # NO SHOW APPROVAL
    # =========================
    def approve_no_show(self, admin_user, note="", refund_amount=None):
        self.status = "NO_SHOW"
        self.save(update_fields=["status"])

        self.log_status(user=admin_user, note=note or "No Show approved")
        self._log(status="NO_SHOW_APPROVED", note=note)

        if refund_amount:
            self.refund(
                amount=refund_amount,
                user=admin_user,
                reason="Refund after No Show"
            )

    def reject_no_show(self, admin_user, note=""):
        self._log(
            status="NO_SHOW_REJECTED",
            note=note
        )

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
        elif self.status in [
            "CANCELLED_BY_CUSTOMER",
            "NO_SHOW",
            "INCIDENT_REPORTED",
            "REFUNDED",
        ]:
            return "cancelled"
        return "upcoming"

    @property 
    def can_cancel(self): # ممنوع بعد ما يصير on the way / started / paused / completed
        if self.status not in ["ORDERED", "SCHEDULED"]: 
            return False # Instant booking خلال 3 ساعات: ممنوع cancel 
        if self.is_instant_booking: 
            return False 
        return True
    # =========================
    # =========================
    # LOYALTY (ADMIN CONTROLLED)
    # =========================
    points_awarded = models.IntegerField(
        null=True,
        blank=True,
        help_text="Points decided by admin after completion"
    )

    points_note = models.CharField(
        max_length=255,
        blank=True
    )

    points_processed = models.BooleanField(
        default=False,
        help_text="Prevent double points processing"
    )

# CANCEL / RESCHEDULE LOGIC (RESTORED)
# =========================
    def cancel_by_admin(self, admin_user, note="Cancelled by admin", refund_amount=None):

        self.status = "CANCELLED_BY_CUSTOMER"
        self.save(update_fields=["status"])

        self.log_status(user=admin_user, note=note)
        self._log(status="CANCELLED_BY_CUSTOMER", note=note)

        if refund_amount:
            self.refund(
                amount=refund_amount,
                user=admin_user,
                reason="Refund after admin cancellation"
            )
            
    def cancel_by_customer(self, user, note="Cancelled by customer", refund_amount=None):
        if not self.can_cancel:
            raise ValueError("Cannot cancel this booking")

        # 1️⃣ سجل الإلغاء
        self.status = "CANCELLED_BY_CUSTOMER"
        self.save(update_fields=["status"])

        self.log_status(user=user, note=note)
        self._log(status="CANCELLED_BY_CUSTOMER", note=note)

        # 2️⃣ إذا في Refund → نفّذه
        if refund_amount:
            self.refund(
                amount=refund_amount,
                user=user,
                reason="Refund after customer cancellation"
            )


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
        if self.status not in ["ORDERED", "SCHEDULED"]:
            return False

        h = self._hours_to_service()
        if h is None:
            return True

        return h >= 12


    @property
    def reschedule_free(self):
        h = self._hours_to_service()
        if h is None:
            return True

        return h >= 24


    @property
    def cancel_free(self):
        h = self._hours_to_service()
        if h is None:
            return True

        return h >= 24

    @property
    def actual_duration(self):
        if not self.started_at or not self.completed_at:
            return None
        return self.completed_at - self.started_at
    
    def format_minutes(self, minutes):
        if not minutes:
            return "—"
        h = minutes // 60
        m = minutes % 60
        if m == 0:
            return f"{h} hours"
        return f"{h} hours {m} minutes"

    def format_timedelta(self, td):
        if not td:
            return "—"
        total_minutes = int(td.total_seconds() // 60)
        return self.format_minutes(total_minutes)


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


    discount_code = models.ForeignKey(
        DiscountCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    def __str__(self):
        return f"Booking #{self.id}"
    
    def save_model(self, request, obj, form, change):
        provider_before = None

        if obj.pk:
            provider_before = BusinessBooking.objects.get(pk=obj.pk).provider

        super().save_model(request, obj, form, change)

        # 🔥 إذا تعيّن provider لأول مرة → ASSIGNED
        if obj.provider and provider_before != obj.provider:
            if obj.status == "ORDERED":
                obj.assign_provider(
                    provider=obj.provider,
                    user=request.user
                )


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
    hero_image = models.ImageField(upload_to="private/hero/", blank=True, null=True)
    hero_subtitle = models.CharField(max_length=255, blank=True)
    hero_cta_text = models.CharField(max_length=60, blank=True)
    hero_cta_url = models.URLField(blank=True)
    intro_text = models.TextField(blank=True)
    starting_price = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    questions = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.title


class ServicePricing(models.Model):
    service = models.OneToOneField(
        PrivateService,
        on_delete=models.CASCADE,
        related_name="pricing"
    )
    title = models.CharField(max_length=120, default="Transparent Pricing")
    card_title = models.CharField(max_length=120, blank=True)
    subtitle = models.TextField(blank=True)
    price_label = models.CharField(max_length=80, blank=True)
    price_value = models.CharField(max_length=80, blank=True)
    price_note = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    cta_text = models.CharField(max_length=50, blank=True)
    cta_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.service.title} pricing"


class ServiceEstimate(models.Model):
    service = models.OneToOneField(
        PrivateService,
        on_delete=models.CASCADE,
        related_name="estimate"
    )
    title = models.CharField(max_length=120, default="Get a Quick Estimate")
    property_label = models.CharField(max_length=120, default="Property Size (m²)")
    bedrooms_label = models.CharField(max_length=120, default="Number of Bedrooms")
    cta_text = models.CharField(max_length=50, default="Calculate Estimate")
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.service.title} estimate"


class ServiceEcoPromise(models.Model):
    service = models.OneToOneField(
        PrivateService,
        on_delete=models.CASCADE,
        related_name="eco_promise"
    )
    title = models.CharField(max_length=140, default="Our Eco-Friendly Promise")
    subtitle = models.TextField(blank=True)
    cta_text = models.CharField(max_length=50, default="Add To Cart")

    def __str__(self):
        return f"{self.service.title} eco promise"


class ServiceEcoPoint(models.Model):
    promise = models.ForeignKey(
        ServiceEcoPromise,
        on_delete=models.CASCADE,
        related_name="points"
    )
    title = models.CharField(max_length=140)
    body = models.TextField()
    icon = models.CharField(max_length=30, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class ServiceCard(models.Model):
    service = models.ForeignKey(
        PrivateService,
        on_delete=models.CASCADE,
        related_name="cards"
    )
    title = models.CharField(max_length=150)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Example: bi-check-circle, bi-exclamation-circle"
    )
    body = models.TextField(
        help_text="One bullet per line"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.service.title} - {self.title}"

    def items(self):
        return [line.strip() for line in self.body.splitlines() if line.strip()]


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


    discount_code = models.ForeignKey(
        DiscountCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
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


class FeedbackRequest(models.Model):
    RATING_CHOICES = [
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5"),
    ]

    customer_name = models.CharField(max_length=100, blank=True)
    feedback_text = models.TextField()
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    service_type = models.CharField(max_length=100, blank=True)
    request_details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BookingFormDocument(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    source_file = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PrivateAddon(models.Model):
    service = models.ForeignKey(PrivateService, on_delete=models.CASCADE, related_name="addons_list")
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to="private/addons/", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    form_html = models.TextField(blank=True, null=True)
    questions = models.JSONField(blank=True, null=True)

    def build_form_html_from_questions(self):
        questions = self.questions or {}
        rows = []
        for key, q in questions.items():
            if not q:
                continue
            label = q.get("label", "")
            q_type = (q.get("type") or "text").strip()
            options = q.get("options") or []

            def opt_value(opt):
                if isinstance(opt, dict):
                    return opt.get("label", "")
                return str(opt)

            def opt_display(opt):
                if isinstance(opt, dict):
                    base = opt.get("label", "")
                    duration = opt.get("duration", 0)
                    if duration:
                        return f"{base} ({duration} min)"
                    return base
                return str(opt)

            if q_type == "select":
                opts = ["<option value=\"\">Select...</option>"] + [
                    f"<option value=\"{opt_value(o)}\">{opt_display(o)}</option>" for o in options
                ]
                field_html = f"""
<label>{label}</label>
<select name="{key}">{''.join(opts)}</select>
"""
            elif q_type == "multiselect":
                opts = [
                    f"<option value=\"{opt_value(o)}\">{opt_display(o)}</option>" for o in options
                ]
                field_html = f"""
<label>{label}</label>
<select name="{key}" multiple>{''.join(opts)}</select>
"""
            elif q_type == "radio":
                items = []
                for o in options:
                    v = opt_value(o)
                    items.append(
                        f"""<label class="option-item"><input type="radio" name="{key}" value="{v}"><span>{opt_display(o)}</span></label>"""
                    )
                field_html = f"""
<label>{label}</label>
<div class="option-group">{''.join(items)}</div>
"""
            elif q_type == "checkbox":
                items = []
                for o in options:
                    v = opt_value(o)
                    items.append(
                        f"""<label class="option-item"><input type="checkbox" name="{key}" value="{v}"><span>{opt_display(o)}</span></label>"""
                    )
                field_html = f"""
<label>{label}</label>
<div class="option-group">{''.join(items)}</div>
"""
            elif q_type == "textarea":
                field_html = f"""
<label>{label}</label>
<textarea name="{key}"></textarea>
"""
            elif q_type == "number":
                field_html = f"""
<label>{label}</label>
<input type="number" name="{key}">
"""
            else:
                field_html = f"""
<label>{label}</label>
<input type="text" name="{key}">
"""
            rows.append(f"""<div class="addon-field">{field_html}</div>""")
        return "".join(rows)

    def save(self, *args, **kwargs):
        if self.questions:
            self.form_html = self.build_form_html_from_questions()
        super().save(*args, **kwargs)


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

class RotSetting(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ROT {self.amount}"


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

    booking_type = models.CharField(
        max_length=10,
        choices=[("private", "Private"), ("business", "Business")]
    )

    booking_id = models.PositiveIntegerField()

    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="no_show_reports_sent"
    )

    decision = models.CharField(
        max_length=10,
        choices=DECISION_CHOICES,
        default="PENDING"
    )

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

    def get_booking(self):
        from home.models import PrivateBooking, BusinessBooking

        if self.booking_type == "private":
            return PrivateBooking.objects.filter(id=self.booking_id).first()

        return BusinessBooking.objects.filter(id=self.booking_id).first()

    def apply_decision(self):
        booking = self.get_booking()
        if not booking:
            return

        if self.decision == "APPROVED":
            booking.approve_no_show(
                admin_user=self.reviewed_by,
                note=self.reviewed_note or self.provider_note
            )

        elif self.decision == "REJECTED":
            booking.reject_no_show(
                admin_user=self.reviewed_by,
                note=self.reviewed_note
            )

    def save(self, *args, **kwargs):
        old_decision = None
        if self.pk:
            old_decision = NoShowReport.objects.get(pk=self.pk).decision

        super().save(*args, **kwargs)

        if old_decision != self.decision and self.decision in ["APPROVED", "REJECTED"]:
            self.reviewed_at = timezone.now()
            super().save(update_fields=["reviewed_at"])
            self.apply_decision()




            




# home/models.py


class BookingNote(models.Model):
    private_booking = models.ForeignKey(
        "PrivateBooking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="note"
    )
    business_booking = models.ForeignKey(
        "BusinessBooking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="note"
    )

    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.text[:40]


class BookingMedia(models.Model):
    PHASE_CHOICES = [
        ("before", "Before"),
        ("during", "During"),
        ("after", "After"),
        ("issue", "Issue"),
    ]

    booking_type = models.CharField(
        max_length=10,
        choices=[("private", "Private"), ("business", "Business")]
    )
    booking_id = models.PositiveIntegerField()

    phase = models.CharField(
        max_length=10,
        choices=PHASE_CHOICES,
        default="before"
    )
    file = models.ImageField(upload_to="booking_media/")

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_media"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.booking_type} #{self.booking_id} {self.phase}"

    def get_booking(self):
        if self.booking_type == "private":
            return PrivateBooking.objects.filter(id=self.booking_id).first()
        return BusinessBooking.objects.filter(id=self.booking_id).first()
