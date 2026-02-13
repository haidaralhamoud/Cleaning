from datetime import datetime, time, timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from home.models import PrivateBooking
from home.availability_utils import generate_slots, provider_available_after_minutes


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
