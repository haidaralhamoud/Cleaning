from datetime import datetime, time, timedelta
from decimal import Decimal
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from home.models import BusinessBooking, EmailRequest, PrivateBooking, PrivateMainCategory, PrivateService
from accounts.models import Customer
from home.models import Contact
from home.availability_utils import generate_slots, provider_available_after_minutes
from home.pricing_utils import calculate_booking_price


class ProviderAvailabilityTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.provider = self.User.objects.create_user(username="provider1", password="pass123")

    def _dt(self, date_obj, t):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime.combine(date_obj, t), tz)

    def test_provider_is_available_overlap(self):
        now = timezone.now()
        booking1 = PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=now,
            quoted_duration_minutes=60,
            status="ORDERED",
        )
        booking2 = PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=now + timedelta(minutes=30),
            quoted_duration_minutes=30,
            status="ORDERED",
        )
        self.assertFalse(booking2.provider_is_available(self.provider))

        booking1.status = "COMPLETED"
        booking1.save(update_fields=["status"])
        self.assertTrue(booking2.provider_is_available(self.provider))

        booking1.status = "INCIDENT_REPORTED"
        booking1.save(update_fields=["status"])
        self.assertFalse(booking2.provider_is_available(self.provider))

    def test_generate_slots_excludes_overlap(self):
        date_obj = timezone.localdate()
        booking_start = self._dt(date_obj, time(10, 0))
        PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=booking_start,
            quoted_duration_minutes=60,
            status="ORDERED",
        )

        slots = generate_slots(
            self.provider,
            date_obj,
            duration_minutes=60,
            slot_size_minutes=30,
            day_start=time(8, 0),
            day_end=time(12, 0),
        )
        slot_times = [s.time().strftime("%H:%M") for s in slots]
        self.assertNotIn("10:00", slot_times)
        self.assertNotIn("10:30", slot_times)
        self.assertIn("08:00", slot_times)
        self.assertIn("11:00", slot_times)

    def test_provider_available_after_minutes(self):
        now = timezone.now()
        PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=now - timedelta(minutes=10),
            quoted_duration_minutes=60,
            status="ORDERED",
        )
        minutes = provider_available_after_minutes(self.provider, now=now)
        self.assertGreaterEqual(minutes, 49)
        self.assertLessEqual(minutes, 51)

    def test_extend_duration_conflict(self):
        date_obj = timezone.localdate()
        booking1 = PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=self._dt(date_obj, time(9, 0)),
            quoted_duration_minutes=60,
            status="ORDERED",
        )
        PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=self._dt(date_obj, time(10, 0)),
            quoted_duration_minutes=60,
            status="ORDERED",
        )
        with self.assertRaises(ValidationError):
            booking1.extend_duration(30)

        booking1.extend_duration(30, allow_conflict=True, note="Admin override")
        booking1.refresh_from_db()
        self.assertTrue(booking1.conflict_override)


class BookingPricingDurationTests(TestCase):
    def setUp(self):
        self.category = PrivateMainCategory.objects.create(title="Home")

    def test_service_without_option_durations_uses_default_duration(self):
        service = PrivateService.objects.create(
            category=self.category,
            title="Standard Cleaning",
            slug="standard-cleaning",
            price=100,
            questions={
                "size": {
                    "label": "Home size",
                    "type": "select",
                    "options": [
                        {"label": "Small", "value": "small"},
                        {"label": "Large", "value": "large"},
                    ],
                }
            },
        )
        booking = PrivateBooking(
            selected_services=[service.slug],
            service_answers={service.slug: {"size": "small"}},
        )

        pricing = calculate_booking_price(booking)

        self.assertEqual(pricing["duration_minutes"], 120.0)
        self.assertTrue(pricing["duration_is_estimated"])

    def test_multiple_services_without_option_durations_stack_default_duration(self):
        service_one = PrivateService.objects.create(
            category=self.category,
            title="Kitchen Cleaning",
            slug="kitchen-cleaning",
            price=100,
        )
        service_two = PrivateService.objects.create(
            category=self.category,
            title="Bathroom Cleaning",
            slug="bathroom-cleaning",
            price=100,
        )
        booking = PrivateBooking(
            selected_services=[service_one.slug, service_two.slug],
            service_answers={},
        )

        pricing = calculate_booking_price(booking)

        self.assertEqual(pricing["duration_minutes"], 240.0)
        self.assertTrue(pricing["duration_is_estimated"])


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Hembla Experten <services@hembla-experten.se>",
    ALLOWED_HOSTS=["hembla-experten.se", "testserver"],
    CONTACT_SUPPORT_EMAIL="support@hembla-experten.se",
    SECURE_SSL_REDIRECT=False,
)
class BookingEmailSignalTests(TestCase):
    def test_private_booking_creation_sends_customer_confirmation_email(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="pass123",
        )
        Customer.objects.create(
            user=user,
            first_name="Lama",
            last_name="Hassan",
            phone="123456",
            email="customer@example.com",
        )

        category = PrivateMainCategory.objects.create(title="Home")
        service = PrivateService.objects.create(
            category=category,
            title="Standard Cleaning",
            slug="standard-cleaning",
            price=100,
        )

        PrivateBooking.objects.create(
            user=user,
            selected_services=[service.slug],
            appointment_date=timezone.localdate(),
            appointment_time_window="09:00 - 12:00",
            total_price=Decimal("249.00"),
            payment_amount=Decimal("249.00"),
            payment_currency="sek",
        )

        customer_emails = [
            email for email in mail.outbox
            if "customer@example.com" in email.to and "Your booking is confirmed" in email.subject
        ]
        self.assertEqual(len(customer_emails), 1)
        customer_email = customer_emails[0]
        self.assertEqual(customer_email.from_email, "Hembla Experten <services@hembla-experten.se>")
        self.assertIn("Your booking is confirmed", customer_email.subject)
        self.assertIn("Standard Cleaning", customer_email.body)
        self.assertIn("09:00 - 12:00", customer_email.body)

    def test_business_booking_creation_sends_customer_confirmation_email(self):
        BusinessBooking.objects.create(
            company_name="Acme AB",
            contact_person="Nour",
            email="office@example.com",
            selected_service="Office Cleaning",
            custom_date=timezone.localdate(),
            custom_time="08:00 - 10:00",
        )

        customer_emails = [
            email for email in mail.outbox
            if "office@example.com" in email.to and "Your business booking is confirmed" in email.subject
        ]
        self.assertEqual(len(customer_emails), 1)
        customer_email = customer_emails[0]
        self.assertEqual(customer_email.from_email, "Hembla Experten <services@hembla-experten.se>")
        self.assertIn("Acme AB", customer_email.body)
        self.assertIn("Office Cleaning", customer_email.body)
        self.assertIn("08:00 - 10:00", customer_email.body)

    def test_contact_form_sends_email_to_support_and_renders_support_email(self):
        response = self.client.get(reverse("home:contact"))
        self.assertContains(response, "support@hembla-experten.se")

        Contact.objects.create(
            first_name="Lama",
            last_name="Hassan",
            email="lama@example.com",
            country_code="+46",
            phone="123456",
            message="Need help",
            inquiry_type="general",
            preferred_method="email",
        )

        support_emails = [
            email for email in mail.outbox
            if "support@hembla-experten.se" in email.to and email.subject == "New Contact Message"
        ]
        self.assertEqual(len(support_emails), 1)

    def test_contact_form_post_redirects_to_success_page(self):
        response = self.client.post(
            reverse("home:contact"),
            data={
                "first_name": "Lama",
                "last_name": "Hassan",
                "email": "lama@example.com",
                "country_code": "+46",
                "phone": "123456",
                "message": "Need help",
                "inquiry_type": "general",
                "preferred_method": "email",
            },
        )

        self.assertRedirects(response, f"{reverse('home:contact')}?submitted=1")
        self.assertTrue(Contact.objects.filter(email="lama@example.com").exists())
        self.assertEqual(Contact.objects.get(email="lama@example.com").source, "private")

        success_response = self.client.get(f"{reverse('home:contact')}?submitted=1")
        self.assertContains(success_response, "Thank You! We&#x27;ve Got Your Message", html=False)

    def test_private_zip_available_email_request_sends_support_and_customer_emails(self):
        category = PrivateMainCategory.objects.create(title="Home")
        service = PrivateService.objects.create(
            category=category,
            title="Standard Cleaning",
            slug="standard-cleaning",
            price=100,
        )

        response = self.client.post(
            reverse("home:private_zip_available", args=[service.slug]),
            data={
                "form_type": "email_request",
                "email_from": "customer@example.com",
                "subject": "Need help with booking",
                "message": "Please contact me back.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmailRequest.objects.filter(email_from="customer@example.com").exists())

        support_emails = [
            email for email in mail.outbox
            if "support@hembla-experten.se" in email.to
        ]
        self.assertEqual(len(support_emails), 1)
        self.assertIn("Need help with booking", support_emails[0].subject)
        self.assertIn("customer@example.com", support_emails[0].body)

        customer_emails = [
            email for email in mail.outbox
            if "customer@example.com" in email.to and email.subject == "We received your request"
        ]
        self.assertEqual(len(customer_emails), 1)
        self.assertIn("We have received your request", customer_emails[0].body)
        self.assertIn("Standard Cleaning", customer_emails[0].body)
