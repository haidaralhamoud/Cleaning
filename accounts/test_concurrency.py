from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature

from accounts.loyalty import award_points_for_booking
from accounts.mail_delivery import enqueue_message, deliver_message
from accounts.models import PointsTransaction
from home.models import PrivateBooking


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_OUTBOX_EAGER=False)
class PostgreSQLConcurrencyTests(TransactionTestCase):
    def _run_together(self, callback):
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return callback()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(lambda _: worker(), range(2)))

    @skipUnlessDBFeature("has_select_for_update")
    def test_two_workers_award_only_once(self):
        user = get_user_model().objects.create_user(username="concurrent-points")
        booking = PrivateBooking.objects.create(user=user, status="COMPLETED", points_awarded=25)
        results = self._run_together(lambda: award_points_for_booking(PrivateBooking.objects.get(pk=booking.pk)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(PointsTransaction.objects.filter(user=user, reason="BOOKING").count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_two_workers_submit_an_email_only_once(self):
        job = enqueue_message(EmailMultiAlternatives("Concurrent", "Body", "from@example.com", ["to@example.com"]))
        results = self._run_together(lambda: deliver_message(job.pk))
        self.assertEqual(sorted(results), [False, True])
