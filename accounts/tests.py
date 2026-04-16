from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core import mail
from datetime import timedelta

from .models import Customer, PasswordResetOTP


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SECURE_SSL_REDIRECT=False,
    VERIFICATION_FROM_EMAIL="Hembla Experten Verification <verification@hembla-experten.se>",
    VERIFICATION_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    VERIFICATION_EMAIL_HOST_USER="verification@hembla-experten.se",
    VERIFICATION_EMAIL_HOST_PASSWORD="secret",
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    },
)
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="OldPassword123",
        )

    def test_request_reset_creates_otp(self):
        response = self.client.post(reverse("password_reset"), {"email": "test@example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PasswordResetOTP.objects.filter(email="test@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].from_email,
            "Hembla Experten Verification <verification@hembla-experten.se>",
        )

    def test_verify_code_success(self):
        otp = PasswordResetOTP.objects.create(
            email="test@example.com",
            user=self.user,
            otp_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=10),
            last_sent_at=timezone.now(),
        )
        session = self.client.session
        session["password_reset_email"] = "test@example.com"
        session.save()

        response = self.client.post(reverse("password_reset_verify"), {"code": "123456"})
        self.assertEqual(response.status_code, 302)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_set_new_password(self):
        session = self.client.session
        session["password_reset_verified_email"] = "test@example.com"
        session["password_reset_verified_at"] = int(timezone.now().timestamp())
        session.save()

        response = self.client.post(
            reverse("password_reset_new"),
            {"new_password1": "NewPassword123", "new_password2": "NewPassword123"},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword123"))

    def test_wrong_code_locks_after_max_attempts(self):
        otp = PasswordResetOTP.objects.create(
            email="test@example.com",
            user=self.user,
            otp_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=10),
            last_sent_at=timezone.now(),
        )
        session = self.client.session
        session["password_reset_email"] = "test@example.com"
        session.save()

        for _ in range(5):
            self.client.post(reverse("password_reset_verify"), {"code": "000000"})

        otp.refresh_from_db()
        self.assertIsNotNone(otp.locked_until)

    def test_expired_code_rejected(self):
        otp = PasswordResetOTP.objects.create(
            email="test@example.com",
            user=self.user,
            otp_hash=make_password("123456"),
            expires_at=timezone.now() - timedelta(minutes=1),
            last_sent_at=timezone.now(),
        )
        session = self.client.session
        session["password_reset_email"] = "test@example.com"
        session.save()

        response = self.client.post(reverse("password_reset_verify"), {"code": "123456"})
        self.assertEqual(response.status_code, 200)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_resend_cooldown(self):
        PasswordResetOTP.objects.create(
            email="test@example.com",
            user=self.user,
            otp_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=10),
            last_sent_at=timezone.now(),
            ip_address="10.0.0.1",
        )
        response = self.client.post(
            reverse("password_reset"),
            {"email": "test@example.com"},
            HTTP_X_FORWARDED_FOR="10.0.0.1",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_cooldown_per_ip(self):
        PasswordResetOTP.objects.create(
            email="first@example.com",
            user=self.user,
            otp_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=10),
            last_sent_at=timezone.now(),
            ip_address="10.0.0.2",
        )
        User.objects.create_user(
            username="second@example.com",
            email="second@example.com",
            password="SomePassword123",
        )
        response = self.client.post(
            reverse("password_reset"),
            {"email": "second@example.com"},
            HTTP_X_FORWARDED_FOR="10.0.0.2",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_request_reset_rejects_unknown_email(self):
        response = self.client.post(reverse("password_reset"), {"email": "missing@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No account found with this email.")

    def test_success_marks_single_use(self):
        older = PasswordResetOTP.objects.create(
            email="test@example.com",
            user=self.user,
            otp_hash=make_password("123456"),
            expires_at=timezone.now() + timedelta(minutes=10),
            last_sent_at=timezone.now(),
        )
        latest = PasswordResetOTP.objects.create(
            email="test@example.com",
            user=self.user,
            otp_hash=make_password("654321"),
            expires_at=timezone.now() + timedelta(minutes=10),
            last_sent_at=timezone.now(),
        )
        session = self.client.session
        session["password_reset_email"] = "test@example.com"
        session.save()

        self.client.post(reverse("password_reset_verify"), {"code": "654321"})
        latest.refresh_from_db()
        older.refresh_from_db()
        self.assertTrue(latest.is_used)
        self.assertTrue(older.is_used)
        self.assertEqual(
            PasswordResetOTP.objects.filter(email="test@example.com", is_used=False).count(),
            0,
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SECURE_SSL_REDIRECT=False,
    VERIFICATION_FROM_EMAIL="Hembla Experten Verification <verification@hembla-experten.se>",
    VERIFICATION_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    VERIFICATION_EMAIL_HOST_USER="verification@hembla-experten.se",
    VERIFICATION_EMAIL_HOST_PASSWORD="secret",
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    },
)
class SignUpVerificationFlowTests(TestCase):
    def _signup_payload(self, **overrides):
        data = {
            "personal_identity_number": "19991231-1234",
            "first_name": "Test",
            "last_name": "User",
            "phone": "123456789",
            "email": "newuser@example.com",
            "country": "Sweden",
            "city": "Stockholm",
            "postal_code": "12345",
            "house_num": "10",
            "full_address": "Main Street 10",
            "password": "NewPassword123",
            "confirm_password": "NewPassword123",
            "accepted_terms": "on",
        }
        data.update(overrides)
        return data

    def test_signup_creates_inactive_account_and_sends_code(self):
        response = self.client.post(reverse("accounts:sign_up"), self._signup_payload())

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("accounts:signup_verify"))
        user = User.objects.get(email="newuser@example.com")
        self.assertFalse(user.is_active)
        self.assertTrue(Customer.objects.filter(user=user).exists())
        self.assertTrue(PasswordResetOTP.objects.filter(email="newuser@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_signup_verify_activates_account(self):
        self.client.post(reverse("accounts:sign_up"), self._signup_payload())
        otp = PasswordResetOTP.objects.filter(email="newuser@example.com").latest("created_at")

        otp.otp_hash = make_password("123456")
        otp.save(update_fields=["otp_hash"])

        response = self.client.post(reverse("accounts:signup_verify"), {"code": "123456"})

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="newuser@example.com")
        otp.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(otp.is_used)
