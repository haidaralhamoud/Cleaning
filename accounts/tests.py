from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core import mail
from datetime import timedelta

from .models import PasswordResetOTP


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
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
