from datetime import datetime, time, timedelta
from decimal import Decimal
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from home.models import Application, AirbnbManagementRequest, BusinessBooking, CallRequest, EmailRequest, FeedbackRequest, HomeServiceInquiry, Job, NotAvailableZipRequest, PrivateBooking, PrivateMainCategory, PrivateService
from accounts.models import Customer, ProviderShift
from home.models import Contact
from home.availability_utils import generate_slots, provider_available_after_minutes, has_overlap
from home.pricing_utils import calculate_booking_price
from home.views import CustomerDashboardForm


@override_settings(
    PUBLIC_SITE_URL="https://hembla-experten.se",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class PublicSeoTests(TestCase):
    def test_robots_lists_private_areas_and_absolute_sitemap(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Disallow: /private/api/")
        self.assertContains(response, "Sitemap: https://hembla-experten.se/sitemap.xml")

    def test_canonical_ignores_query_string_and_home_has_schema(self):
        contact = self.client.get("/contact?submitted=1")
        home = self.client.get("/")

        self.assertContains(
            contact,
            '<link rel="canonical" href="https://hembla-experten.se/contact">',
            html=True,
        )
        self.assertContains(home, "Home Cleaning in Stockholm | Hembla Experten")
        self.assertContains(home, '"@type": "LocalBusiness"')
        self.assertContains(home, '"opens": "07:00"')
        self.assertContains(home, '"closes": "18:00"')

    def test_sitemap_contains_public_pages_and_database_services(self):
        category = PrivateMainCategory.objects.create(title="Homes", slug="homes")
        service = PrivateService.objects.create(
            category=category,
            title="Test clean",
            slug="test-clean",
        )

        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://hembla-experten.se/")
        self.assertContains(response, reverse("accounts:service_detail", args=[service.slug]))
        self.assertNotContains(response, "/admin/")
        self.assertNotContains(response, "/booking/checkout/")

    def test_service_metadata_uses_service_content(self):
        category = PrivateMainCategory.objects.create(title="Homes", slug="homes")
        service = PrivateService.objects.create(
            category=category,
            title="Deep Cleaning Stockholm",
            slug="deep-cleaning-stockholm",
            description="A thorough cleaning service for homes in Stockholm.",
            image="private/services/deep-clean.jpg",
        )

        response = self.client.get(reverse("accounts:service_detail", args=[service.slug]))

        self.assertContains(response, "Deep Cleaning Stockholm | Hembla Experten")
        self.assertContains(response, "A thorough cleaning service for homes in Stockholm.")
        self.assertContains(
            response,
            "https://hembla-experten.se/media/private/services/deep-clean.jpg",
        )


class PrivateBookingFlowSafetyTests(TestCase):
    def setUp(self):
        self.category = PrivateMainCategory.objects.create(
            title="Home cleaning",
            slug="home-cleaning",
        )
        self.service = PrivateService.objects.create(
            category=self.category,
            title="Standard cleaning",
            slug="standard-cleaning",
            price=Decimal("250.00"),
            price_currency="SEK",
        )

    def _set_draft(self, **updates):
        draft = {
            "selected_services": [self.service.slug],
            "schedule_mode": "same",
        }
        draft.update(updates)
        session = self.client.session
        session["private_booking_draft"] = draft
        session.save()

    def test_checkout_redirects_when_schedule_is_incomplete(self):
        self._set_draft()

        response = self.client.get(reverse("home:private_booking_checkout"))

        self.assertRedirects(response, reverse("home:private_booking_schedule"), fetch_redirect_response=False)

    def test_invoice_endpoint_rejects_get_requests(self):
        user = get_user_model().objects.create_user(
            username="invoice-flow@example.com",
            email="invoice-flow@example.com",
            password="test-password",
        )
        self.client.force_login(user)
        self._set_draft(appointment_date=timezone.localdate().isoformat(), appointment_start_time="10:00")

        response = self.client.get(reverse("home:private_booking_cash_invoice_pdf"))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(PrivateBooking.objects.count(), 0)

    def test_invoice_endpoint_requires_terms_acceptance(self):
        user = get_user_model().objects.create_user(
            username="invoice-terms@example.com",
            email="invoice-terms@example.com",
            password="test-password",
        )
        self.client.force_login(user)
        self._set_draft(appointment_date=timezone.localdate().isoformat(), appointment_start_time="10:00")

        response = self.client.post(reverse("home:private_booking_cash_invoice_pdf"))

        self.assertRedirects(response, reverse("home:private_booking_checkout"), fetch_redirect_response=False)
        self.assertEqual(PrivateBooking.objects.count(), 0)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    },
)
class CustomerDashboardFormTests(TestCase):
    def customer_data(self, email="new.customer@example.com"):
        return {
            "personal_identity_number": "19900101-1234",
            "first_name": "New",
            "last_name": "Customer",
            "phone": "+46700000000",
            "email": email,
            "country": "Sweden",
            "city": "Stockholm",
            "postal_code": "11122",
            "house_num": "10",
            "full_address": "Example Street 10",
            "preferred_language": "en",
        }

    def test_customer_dashboard_does_not_expose_user_field(self):
        user_model = get_user_model()
        staff_user = user_model.objects.create_user(
            username="dashboard-admin",
            password="pass123",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(
            reverse("home:dashboard_model_create", args=["customers"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("user", response.context["form"].fields)

    def test_customer_form_creates_and_links_account_automatically(self):
        form = CustomerDashboardForm(data=self.customer_data())

        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save()

        self.assertEqual(customer.user.email, "new.customer@example.com")
        self.assertEqual(customer.user.first_name, "New")
        self.assertFalse(customer.user.has_usable_password())

    def test_customer_form_links_existing_account_with_same_email(self):
        user_model = get_user_model()
        existing_user = user_model.objects.create_user(
            username="existing-user",
            email="existing.customer@example.com",
            password="pass123",
        )
        form = CustomerDashboardForm(
            data=self.customer_data("existing.customer@example.com")
        )

        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save()

        self.assertEqual(customer.user, existing_user)

    def test_customer_form_allows_multiple_customers_with_same_contact_email(self):
        first_form = CustomerDashboardForm(data=self.customer_data("shared@example.com"))
        self.assertTrue(first_form.is_valid(), first_form.errors)
        first_customer = first_form.save()

        second_data = self.customer_data("shared@example.com")
        second_data["personal_identity_number"] = "19920202-5678"
        second_data["first_name"] = "Second"
        second_form = CustomerDashboardForm(data=second_data)

        self.assertTrue(second_form.is_valid(), second_form.errors)
        second_customer = second_form.save()

        self.assertEqual(second_customer.email, "shared@example.com")
        self.assertNotEqual(second_customer.user, first_customer.user)
        self.assertEqual(first_customer.user.email, "shared@example.com")
        self.assertEqual(second_customer.user.email, "")

    def test_customer_form_allows_editing_email_to_an_existing_customer_email(self):
        first_form = CustomerDashboardForm(data=self.customer_data("shared@example.com"))
        self.assertTrue(first_form.is_valid(), first_form.errors)
        first_form.save()

        second_data = self.customer_data("second@example.com")
        second_data["personal_identity_number"] = "19920202-5678"
        second_form = CustomerDashboardForm(data=second_data)
        self.assertTrue(second_form.is_valid(), second_form.errors)
        second_customer = second_form.save()
        original_user = second_customer.user

        second_data["email"] = "shared@example.com"
        edit_form = CustomerDashboardForm(data=second_data, instance=second_customer)

        self.assertTrue(edit_form.is_valid(), edit_form.errors)
        updated_customer = edit_form.save()
        self.assertEqual(updated_customer.email, "shared@example.com")
        self.assertEqual(updated_customer.user, original_user)


class ProviderAvailabilityTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.provider = self.User.objects.create_user(username="provider1", password="pass123")
        ProviderShift.objects.create(
            provider=self.provider,
            weekday=timezone.localdate().weekday(),
            start_time=time(8, 0),
            end_time=time(20, 0),
        )

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
        self.assertNotIn("11:00", slot_times)

    def test_provider_available_after_minutes(self):
        now = timezone.now()
        PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=now - timedelta(minutes=10),
            quoted_duration_minutes=60,
            status="ORDERED",
        )
        minutes = provider_available_after_minutes(self.provider, now=now)
        self.assertGreaterEqual(minutes, 109)
        self.assertLessEqual(minutes, 111)

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
        self.User = get_user_model()
        self.provider = self.User.objects.create_user(username="provider2", password="pass123")
        self.category = PrivateMainCategory.objects.create(title="Home")

    def _dt(self, date_obj, t):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime.combine(date_obj, t), tz)

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

    def test_service_base_price_is_ignored_and_question_price_is_used(self):
        service = PrivateService.objects.create(
            category=self.category,
            title="Air Conditioner Cleaning",
            slug="air-conditioner-cleaning",
            price=999,
            questions={
                "units": {
                    "label": "How many units?",
                    "type": "select",
                    "options": [
                        {"label": "One unit", "value": "one", "price": 350, "duration": 60},
                    ],
                }
            },
        )
        booking = PrivateBooking(
            selected_services=[service.slug],
            service_answers={service.slug: {"units": "one"}},
        )

        pricing = calculate_booking_price(booking)

        self.assertEqual(pricing["services_total"], 350.0)
        self.assertEqual(pricing["service_breakdown"][service.slug], 350.0)

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

    def test_start_time_builds_service_window_with_buffer(self):
        booking = PrivateBooking(
            appointment_date=timezone.localdate(),
            appointment_start_time=time(9, 0),
            quoted_duration_minutes=120,
        )

        start_dt, end_dt = booking.get_service_window()

        self.assertIsNotNone(start_dt)
        self.assertIsNotNone(end_dt)
        self.assertEqual(start_dt.strftime("%H:%M"), "09:00")
        self.assertEqual(end_dt.strftime("%H:%M"), "12:00")

    def test_has_overlap_uses_start_and_end_datetimes(self):
        date_obj = timezone.localdate()
        now_start = self._dt(date_obj, time(9, 0))
        PrivateBooking.objects.create(
            provider=self.provider,
            scheduled_at=now_start,
            quoted_duration_minutes=120,
            status="ASSIGNED",
        )

        self.assertTrue(has_overlap(self.provider, self._dt(date_obj, time(10, 0)), self._dt(date_obj, time(11, 0))))
        self.assertFalse(has_overlap(self.provider, self._dt(date_obj, time(13, 30)), self._dt(date_obj, time(14, 30))))


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Hembla Experten <services@hembla-experten.se>",
    ALLOWED_HOSTS=["hembla-experten.se", "testserver"],
    CONTACT_SUPPORT_EMAIL="support@hembla-experten.se",
    SECURE_SSL_REDIRECT=False,
)
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class BookingEmailSignalTests(TestCase):
    def test_job_application_sends_candidate_and_company_emails_and_dashboard_notification(self):
        job = Job.objects.create(title="Cleaning Specialist", description="Join our team")
        application = Application.objects.create(
            full_name="Sara Andersson",
            email="sara@example.com",
            phone="070 111 22 33",
            job=job,
            area="Stockholm",
            availability="Immediately",
            message="I have three years of experience.",
        )

        self.assertEqual(len(mail.outbox), 2)
        candidate_email = next(email for email in mail.outbox if "sara@example.com" in email.to)
        self.assertEqual(candidate_email.subject, f"We received your application #{application.pk}")
        self.assertIn("Cleaning Specialist", candidate_email.body)

        company_email = next(email for email in mail.outbox if "services@hembla-experten.se" in email.to)
        self.assertEqual(company_email.subject, f"New Job Application #{application.pk} - Sara Andersson")
        self.assertIn("I have three years of experience.", company_email.body)

        staff = get_user_model().objects.create_user(username="careers-admin", password="pass123", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("home:dashboard_notifications_api"))
        matching_items = [
            item for item in response.json()["items"]
            if item["title"] == f"New Job Application #{application.pk}"
        ]
        self.assertEqual(len(matching_items), 1)
        self.assertEqual(matching_items[0]["url"], "/dashboard/applications/")

    def test_airbnb_request_sends_customer_and_company_emails_and_dashboard_notification(self):
        response = self.client.post(
            reverse("home:submit_airbnb_management_request"),
            data={
                "services": ["Complete Management", "Cleaning & Turnovers"],
                "property_count": "2–3",
                "name": "Lama Hassan",
                "email": "airbnb@example.com",
                "location": "Stockholm",
                "phone": "070 555 12 34",
                "message": "Two city apartments.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        airbnb_request = AirbnbManagementRequest.objects.get(email="airbnb@example.com")
        self.assertEqual(len(mail.outbox), 2)
        customer_email = next(email for email in mail.outbox if "airbnb@example.com" in email.to)
        self.assertIn("We received your Airbnb management request", customer_email.subject)
        self.assertIn("Complete Management", customer_email.body)
        company_email = next(email for email in mail.outbox if "services@hembla-experten.se" in email.to)
        self.assertEqual(company_email.subject, f"New Airbnb Management Request #{airbnb_request.pk}")
        self.assertIn("Two city apartments.", company_email.body)

        staff = get_user_model().objects.create_user(username="airbnb-admin", password="pass123", is_staff=True)
        self.client.force_login(staff)
        dashboard_response = self.client.get(reverse("home:dashboard_notifications_api"))
        matching_items = [
            item for item in dashboard_response.json()["items"]
            if item["title"] == f"New Airbnb Management Request #{airbnb_request.pk}"
        ]
        self.assertEqual(len(matching_items), 1)
        self.assertEqual(matching_items[0]["url"], "/dashboard/airbnb-management-requests/")

    def test_home_service_inquiry_sends_customer_and_company_emails(self):
        response = self.client.post(
            reverse("home:submit_home_service_inquiry"),
            data={
                "service": "Deep cleaning",
                "address": "Storgatan 12, Jarfalla",
                "email": "requester@example.com",
                "phone": "070 123 45 67",
                "date": "2026-11-20",
                "time": "10:30",
                "message": "Please call before arriving.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        inquiry = HomeServiceInquiry.objects.get(email="requester@example.com")
        self.assertEqual(len(mail.outbox), 2)

        customer_email = next(email for email in mail.outbox if "requester@example.com" in email.to)
        self.assertIn("We received your cleaning request", customer_email.subject)
        self.assertIn("Deep cleaning", customer_email.body)
        self.assertIn("November 20, 2026", customer_email.body)

        company_email = next(email for email in mail.outbox if "services@hembla-experten.se" in email.to)
        self.assertEqual(company_email.subject, f"New Home Service Request #{inquiry.pk}")
        self.assertIn("070 123 45 67", company_email.body)
        self.assertIn("Please call before arriving.", company_email.body)

    def test_home_service_inquiry_appears_in_dashboard_notifications(self):
        inquiry = HomeServiceInquiry.objects.create(
            service="Regular cleaning",
            address="Test address",
            email="dashboard@example.com",
            phone="0700000000",
        )
        staff = get_user_model().objects.create_user(
            username="dashboard-admin",
            password="pass123",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("home:dashboard_notifications_api"))

        self.assertEqual(response.status_code, 200)
        matching_items = [
            item for item in response.json()["items"]
            if item["title"] == f"New Home Service Request #{inquiry.pk}"
        ]
        self.assertEqual(len(matching_items), 1)
        self.assertEqual(matching_items[0]["url"], "/dashboard/home-service-inquiries/")

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
            appointment_start_time=time(9, 0),
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
        self.assertIn("09:00", customer_email.body)

        admin_emails = [
            email for email in mail.outbox
            if "services@hembla-experten.se" in email.to and "New Private Booking" in email.subject
        ]
        self.assertEqual(len(admin_emails), 1)
        self.assertIn("A new private booking was created", admin_emails[0].body)

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
        customer_emails = [
            email for email in mail.outbox
            if "lama@example.com" in email.to and email.subject == "We received your message"
        ]
        self.assertEqual(len(customer_emails), 1)

    def test_unavailable_zip_request_sends_both_emails_and_dashboard_notification(self):
        category = PrivateMainCategory.objects.create(title="Home")
        service = PrivateService.objects.create(
            category=category,
            title="Standard Cleaning",
            slug="zip-standard-cleaning",
            price=100,
        )
        zip_request = NotAvailableZipRequest.objects.create(
            service=service,
            zip_code="12345",
            first_name="Lama",
            last_name="Hassan",
            email="zip-customer@example.com",
            phone="0700000000",
            message="Please notify me.",
        )

        self.assertTrue(any("zip-customer@example.com" in email.to for email in mail.outbox))
        self.assertTrue(any("services@hembla-experten.se" in email.to for email in mail.outbox))

        staff = get_user_model().objects.create_user(username="zip-admin", password="pass123", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("home:dashboard_notifications_api"))
        matching_items = [
            item for item in response.json()["items"]
            if item["title"] == f"New ZIP Request #{zip_request.pk}"
        ]
        self.assertEqual(len(matching_items), 1)
        self.assertEqual(matching_items[0]["url"], "/dashboard/not-available-zips/")

    def test_feedback_sends_customer_and_company_emails_and_dashboard_notification(self):
        feedback = FeedbackRequest.objects.create(
            customer_name="Lama Hassan",
            email="feedback-customer@example.com",
            feedback_text="The service was excellent.",
            rating=5,
        )

        self.assertTrue(any("feedback-customer@example.com" in email.to for email in mail.outbox))
        self.assertTrue(any("services@hembla-experten.se" in email.to for email in mail.outbox))

        staff = get_user_model().objects.create_user(username="feedback-admin", password="pass123", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("home:dashboard_notifications_api"))
        matching_items = [
            item for item in response.json()["items"]
            if item["title"] == "Pending Feedback: Lama Hassan"
        ]
        self.assertEqual(len(matching_items), 1)

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
        self.assertContains(success_response, "Thank You! We've Got Your Message")

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

        redirect_url = reverse("home:private_zip_available", args=[service.slug])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)
        self.assertTrue(EmailRequest.objects.filter(email_from="customer@example.com").exists())

        success_response = self.client.get(redirect_url)
        self.assertEqual(success_response.status_code, 200)
        self.assertTrue(success_response.context["email_success"])

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

    def test_private_zip_available_call_request_sends_customer_confirmation_email(self):
        category = PrivateMainCategory.objects.create(title="Home")
        service = PrivateService.objects.create(
            category=category,
            title="Appliance Installation Support",
            slug="appliance-installation-support",
            price=100,
        )

        response = self.client.post(
            reverse("home:private_zip_available", args=[service.slug]),
            data={
                "form_type": "call_request",
                "name": "Lama Hassan",
                "phone": "123456789",
                "email": "customer@example.com",
                "preferred_time": "2026-04-20 14:30",
                "message": "Please call after lunch.",
                "language": "Arabic",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(CallRequest.objects.filter(email="customer@example.com").exists())

        customer_emails = [
            email for email in mail.outbox
            if "customer@example.com" in email.to and email.subject == "Your call request has been received"
        ]
        self.assertEqual(len(customer_emails), 1)
        self.assertIn("Appliance Installation Support", customer_emails[0].body)
        self.assertIn("April 20, 2026 at 14:30", customer_emails[0].body)
        self.assertIn("123456789", customer_emails[0].body)
        company_emails = [
            email for email in mail.outbox
            if "services@hembla-experten.se" in email.to and "New Call Request" in email.subject
        ]
        self.assertEqual(len(company_emails), 1)
