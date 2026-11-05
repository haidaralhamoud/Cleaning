import tempfile
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from smtplib import SMTPException

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.backends import EmailPhoneUsernameBackend
from accounts.invoice_utils import send_invoice_email
from accounts.loyalty import award_points_for_booking
from accounts.mail_delivery import enqueue_message, deliver_message
from accounts.models import Customer, Invoice, OutgoingEmail, PasswordResetOTP, PointsTransaction
from accounts.views import RememberMeLoginView
from home.models import Contact, PrivateBooking
from home.upload_security import validate_attachment

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["testserver"])
class AccountSecurityTests(TestCase):
    def test_disabled_account_is_not_authenticated(self):
        user = User.objects.create_user(username="disabled", email="disabled@example.com", password="password123", is_active=False)
        self.assertIsNone(EmailPhoneUsernameBackend().authenticate(None, username=user.email, password="password123"))

    def test_external_and_protocol_relative_redirects_are_rejected(self):
        request = RequestFactory().get("/accounts/login/", secure=True)
        request.user = SimpleNamespace(is_superuser=False, is_staff=False)
        view = RememberMeLoginView()
        view.request = request
        for target in ["https://outside.example/", "//outside.example/", "http://testserver/"]:
            self.assertEqual(view._authenticated_redirect_target(target), reverse("accounts:customer_profile_view"))
        self.assertEqual(view._authenticated_redirect_target("/accounts/my_bookimg/"), "/accounts/my_bookimg/")

    def test_signup_does_not_delete_disabled_user_or_related_profile(self):
        from accounts.tests import SignUpVerificationFlowTests
        payload = SignUpVerificationFlowTests._signup_payload(self)
        user = User.objects.create_user(username=payload["email"], email=payload["email"], password=payload["password"], is_active=False)
        customer = Customer.objects.create(user=user, email=user.email, first_name="Existing", last_name="Customer")
        self.client.post(reverse("accounts:sign_up"), payload)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        customer.refresh_from_db()
        self.assertEqual(customer.first_name, "Existing")
        self.assertFalse(user.access_profile.signup_pending)

    def test_pending_signup_can_resume_without_replacing_customer(self):
        from accounts.tests import SignUpVerificationFlowTests
        payload = SignUpVerificationFlowTests._signup_payload(self)
        self.client.post(reverse("accounts:sign_up"), payload)
        user = User.objects.get(email=payload["email"])
        customer_id = user.customer.pk
        self.assertTrue(user.access_profile.signup_pending)
        response = self.client.post(reverse("accounts:sign_up"), payload)
        self.assertRedirects(response, reverse("accounts:signup_verify"))
        self.assertEqual(Customer.objects.get(user=user).pk, customer_id)

    def test_reset_smtp_failure_is_handled(self):
        User.objects.create_user(username="reset", email="reset@example.com", password="password123")
        with patch("accounts.views._send_reset_code", side_effect=SMTPException("test failure")):
            response = self.client.post(reverse("password_reset"), {"email": "reset@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not send a verification code")

    def test_staff_requires_explicit_dashboard_permission(self):
        staff = User.objects.create_user(username="limited", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("home:dashboard_notifications_api")).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="view_contact", content_type__app_label="home"))
        self.assertEqual(self.client.get(reverse("home:dashboard_model_list", args=["contacts"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("home:dashboard_model_create", args=["contacts"])).status_code, 403)


class UploadSecurityTests(TestCase):
    def test_html_and_disguised_pdf_are_rejected(self):
        for filename in ["audit.html", "audit.pdf", "audit.txt"]:
            with self.assertRaises(ValidationError):
                validate_attachment(SimpleUploadedFile(filename, b"<html>audit</html>"))

    def test_size_limit_and_image_content_are_checked(self):
        with override_settings(MAX_UPLOAD_SIZE=8):
            with self.assertRaises(ValidationError):
                validate_attachment(SimpleUploadedFile("audit.txt", b"a" * 9))
        with self.assertRaises(ValidationError):
            validate_attachment(SimpleUploadedFile("audit.png", b"not an image"))
        buffer = BytesIO()
        Image.new("RGB", (8, 8)).save(buffer, format="PNG")
        upload = SimpleUploadedFile("audit.png", buffer.getvalue())
        validate_attachment(upload)
        self.assertEqual(upload.tell(), 0)

    def test_private_attachment_requires_record_permission(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            contact = Contact.objects.create(first_name="Test", last_name="Contact", email="contact@example.com",
                inquiry_type="general", file=SimpleUploadedFile("private.pdf", b"%PDF-1.4 audit"))
            viewer = User.objects.create_user(username="viewer")
            self.client.force_login(viewer)
            self.assertEqual(self.client.get(contact.file.url).status_code, 404)
            viewer.is_staff = True
            viewer.save(update_fields=["is_staff"])
            viewer.user_permissions.add(Permission.objects.get(codename="view_contact", content_type__app_label="home"))
            response = self.client.get(contact.file.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            response.close()


@override_settings(EMAIL_OUTBOX_EAGER=False, EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailOutboxTests(TestCase):
    def test_rollback_discards_notification_without_sending(self):
        before = OutgoingEmail.objects.count()
        with self.assertRaises(ValueError):
            with transaction.atomic():
                enqueue_message(mail.EmailMultiAlternatives("Audit", "Body", "from@example.com", ["to@example.com"]))
                raise ValueError("rollback")
        self.assertEqual(OutgoingEmail.objects.count(), before)
        self.assertEqual(len(mail.outbox), 0)

    def test_failure_is_retained_and_can_be_retried(self):
        job = enqueue_message(mail.EmailMultiAlternatives("Audit", "Body", "from@example.com", ["to@example.com"]))
        with patch("accounts.mail_delivery.get_connection", side_effect=SMTPException("test failure")):
            self.assertFalse(deliver_message(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.status, "pending")
        self.assertFalse(deliver_message(job.pk))
        OutgoingEmail.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now())
        self.assertTrue(deliver_message(job.pk))
        self.assertFalse(deliver_message(job.pk))
        self.assertEqual(len(mail.outbox), 1)

    def test_backend_queues_instead_of_sending(self):
        with override_settings(EMAIL_BACKEND="accounts.mail_backend.ReliableEmailBackend"):
            self.assertEqual(mail.send_mail("Audit", "Body", "from@example.com", ["to@example.com"]), 1)
        self.assertEqual(OutgoingEmail.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_invoice_is_sent_only_after_transport_accepts_attachment(self):
        user = User.objects.create_user(username="invoice-audit", email="invoice@example.com")
        customer = Customer.objects.create(user=user, email=user.email)
        invoice = Invoice.objects.create(customer=customer)
        with patch("accounts.invoice_utils.render_invoice_pdf", return_value=b"%PDF-audit"):
            send_invoice_email(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "QUEUED")
        self.assertIsNone(invoice.sent_at)
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse("accounts:Payment_and_Billing")), invoice.invoice_number)
        job = OutgoingEmail.objects.get(invoice=invoice)
        self.assertTrue(deliver_message(job.pk))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "SENT")
        self.assertIsNotNone(invoice.sent_at)
        self.assertContains(self.client.get(reverse("accounts:Payment_and_Billing")), invoice.invoice_number)
        self.assertTrue(invoice.is_locked)
        sent = mail.outbox[-1]
        self.assertEqual(sent.attachments[0][1], b"%PDF-audit")


class LoyaltySafetyTests(TestCase):
    def test_stale_booking_object_cannot_award_twice(self):
        user = User.objects.create_user(username="points-audit")
        booking = PrivateBooking.objects.create(user=user, status="COMPLETED", points_awarded=25)
        stale = PrivateBooking.objects.get(pk=booking.pk)
        self.assertTrue(award_points_for_booking(booking))
        self.assertFalse(award_points_for_booking(stale))
        self.assertEqual(PointsTransaction.objects.filter(user=user, reason="BOOKING").count(), 1)

    def test_finalize_requires_post(self):
        staff = User.objects.create_superuser(username="points-admin", email="points@example.com", password="password123")
        self.client.force_login(staff)
        url = reverse("accounts:finalize_booking", args=["private", 1])
        self.assertEqual(self.client.get(url).status_code, 405)


class AdditionalSecurityTests(TestCase):
    def test_untrusted_peer_cannot_spoof_rate_limit_ip(self):
        from home.security import client_ip
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.5", HTTP_X_FORWARDED_FOR="198.51.100.8")
        self.assertEqual(client_ip(request), "192.0.2.5")
        request = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.8")
        self.assertEqual(client_ip(request), "198.51.100.8")

    def test_booking_admin_escapes_customer_json(self):
        from django.contrib import admin
        from home.models import BusinessBooking
        rendered = admin.site._registry[BusinessBooking].pretty_json_colored([{"title": '<img src=x onerror="alert(1)">'}])
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)

    @override_settings(EMAIL_OUTBOX_EAGER=True, EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_eager_notification_waits_until_commit_callback(self):
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                job = enqueue_message(mail.EmailMultiAlternatives("After commit", "Body", "from@example.com", ["to@example.com"]))
                self.assertEqual(len(mail.outbox), 0)
                self.assertEqual(OutgoingEmail.objects.get(pk=job.pk).status, "pending")
        self.assertEqual(len(mail.outbox), 1)
