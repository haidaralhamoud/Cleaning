from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.mail_delivery import deliver_message
from accounts.models import OutgoingEmail


class Command(BaseCommand):
    help = "Submit due notification emails, retry failures and purge expired delivered payloads."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--retry-failed", action="store_true")

    def handle(self, *args, **options):
        if options["limit"] < 1:
            self.stderr.write("--limit must be positive.")
            return
        now = timezone.now()
        if options["retry_failed"]:
            OutgoingEmail.objects.filter(status="failed").update(status="pending", attempts=0, next_attempt_at=now)
        ids = list(OutgoingEmail.objects.filter(status="pending", next_attempt_at__lte=now)
                   .order_by("created_at").values_list("pk", flat=True)[:options["limit"]])
        sent = sum(deliver_message(pk) for pk in ids)
        cutoff = now - timedelta(days=settings.EMAIL_OUTBOX_RETENTION_DAYS)
        OutgoingEmail.objects.filter(status="sent", sent_at__lt=cutoff).delete()
        self.stdout.write(f"Processed {len(ids)} email jobs; accepted {sent}; pending/failed remain available for review.")
