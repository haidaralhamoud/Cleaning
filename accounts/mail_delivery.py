"""Durable notification delivery. Verification codes use their synchronous transport."""
import base64
import logging
from datetime import timedelta
from email.utils import make_msgid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.utils import timezone

from .models import Invoice, OutgoingEmail

logger = logging.getLogger(__name__)


def enqueue_message(message, *, invoice=None):
    message.message()  # Validate addresses and reject header injection before enqueueing.
    attachments = []
    for attachment in message.attachments:
        if not isinstance(attachment, tuple):
            raise ValueError("Only named file attachments are supported by the delivery queue.")
        name, content, mimetype = attachment
        if isinstance(content, str):
            content = content.encode(message.encoding or "utf-8")
        attachments.append([name, base64.b64encode(content).decode("ascii"), mimetype])
    headers = dict(message.extra_headers)
    headers.setdefault("Message-ID", make_msgid(domain="hembla-experten.se"))
    payload = {
        "subject": message.subject, "body": message.body, "from_email": message.from_email,
        "to": list(message.to), "cc": list(message.cc), "bcc": list(message.bcc),
        "reply_to": list(message.reply_to), "headers": headers,
        "alternatives": [list(a) for a in getattr(message, "alternatives", [])],
        "attachments": attachments, "content_subtype": message.content_subtype,
        "encoding": message.encoding or "utf-8",
    }
    job = OutgoingEmail.objects.create(payload=payload, invoice=invoice)
    if settings.EMAIL_OUTBOX_EAGER:
        transaction.on_commit(lambda: deliver_message(job.pk))
    return job


def deliver_message(pk):
    # Lock throughout SMTP submission so concurrent workers cannot send the same row.
    with transaction.atomic():
        job = OutgoingEmail.objects.select_for_update().get(pk=pk)
        now = timezone.now()
        if job.status != "pending" or job.next_attempt_at > now:
            return False
        job.attempts += 1
        try:
            payload = dict(job.payload)
            attachments = payload.pop("attachments", [])
            alternatives = payload.pop("alternatives", [])
            subtype = payload.pop("content_subtype", "plain")
            encoding = payload.pop("encoding", "utf-8")
            connection = get_connection(backend=settings.EMAIL_TRANSPORT_BACKEND, fail_silently=False)
            with connection:
                message = EmailMultiAlternatives(connection=connection, **payload)
                message.content_subtype = subtype
                message.encoding = encoding
                for content, mimetype in alternatives:
                    message.attach_alternative(content, mimetype)
                for name, content, mimetype in attachments:
                    message.attach(name, base64.b64decode(content), mimetype)
                if message.send(fail_silently=False) != 1:
                    raise RuntimeError("SMTP did not accept the message.")
        except Exception as exc:
            job.last_error = f"{type(exc).__name__} (code={getattr(exc, 'smtp_code', 'n/a')})"
            job.status = "failed" if job.attempts >= settings.EMAIL_OUTBOX_MAX_ATTEMPTS else "pending"
            job.next_attempt_at = now + timedelta(seconds=min(60 * (2 ** (job.attempts - 1)), 21600))
            job.save(update_fields=["status", "attempts", "last_error", "next_attempt_at"])
            logger.error("Email delivery failed: job=%s attempt=%s error=%s", job.pk, job.attempts, job.last_error)
            return False
        job.status = "sent"
        job.sent_at = timezone.now()
        job.last_error = ""
        job.save(update_fields=["status", "attempts", "sent_at", "last_error"])
        if job.invoice_id:
            Invoice.objects.filter(pk=job.invoice_id).update(status="SENT", sent_at=job.sent_at, is_locked=True)
        return True
