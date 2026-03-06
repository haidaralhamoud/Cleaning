import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import (
    Customer,
    ProviderProfile,
    CustomerNote,
    Incident,
    ServiceReview,
    ChatMessage,
    BookingRequestFix,
)
from home.models import (
    Contact,
    PrivateBooking,
    BusinessBooking,
    NoShowReport,
)

logger = logging.getLogger(__name__)


def _admin_email():
    return getattr(settings, "ADMIN_ALERT_EMAIL", "Services@hemblaexperten.se")


def _send_admin_alert(subject, body):
    recipient = _admin_email()
    if not recipient:
        return
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send admin alert email")


def _booking_admin_url(booking_type, booking_id):
    if booking_type == "business":
        return f"/dashboard/business-bookings/{booking_id}/edit/"
    return f"/dashboard/private-bookings/{booking_id}/edit/"


@receiver(post_save, sender=PrivateBooking)
def notify_private_booking(sender, instance, created, **kwargs):
    if not created:
        return
    subject = f"New Private Booking #{instance.id}"
    body = f"A new private booking was created.\n\nBooking ID: {instance.id}\nStatus: {instance.status}\nLink: {_booking_admin_url('private', instance.id)}"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=BusinessBooking)
def notify_business_booking(sender, instance, created, **kwargs):
    if not created:
        return
    subject = f"New Business Booking #{instance.id}"
    body = f"A new business booking was created.\n\nBooking ID: {instance.id}\nStatus: {instance.status}\nLink: {_booking_admin_url('business', instance.id)}"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=Contact)
def notify_contact(sender, instance, created, **kwargs):
    if not created:
        return
    subject = "New Contact Message"
    body = f"New contact received.\n\nName: {instance.first_name} {instance.last_name}\nEmail: {instance.email}\nType: {instance.inquiry_type}\nLink: /dashboard/contacts/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=Incident)
def notify_incident(sender, instance, created, **kwargs):
    if not created:
        return
    subject = f"New Incident #{instance.id}"
    body = f"New incident reported.\n\nIncident ID: {instance.id}\nSeverity: {instance.severity}\nLink: /dashboard/incidents/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=ServiceReview)
def notify_review(sender, instance, created, **kwargs):
    if not created:
        return
    subject = f"New Service Review ({instance.service_title})"
    body = f"A new review was submitted.\n\nService: {instance.service_title}\nRating: {instance.overall_rating}\nLink: /dashboard/service-reviews/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=ChatMessage)
def notify_message(sender, instance, created, **kwargs):
    if not created:
        return
    thread = instance.thread
    booking_type = thread.booking_type if thread else "private"
    booking_id = thread.booking_id if thread else ""
    subject = "New Chat Message"
    link = _booking_admin_url(booking_type, booking_id) if booking_id else "/dashboard/"
    body = (
        "New chat message received.\n\n"
        f"Booking: {booking_type} #{booking_id}\n"
        f"Sender: {instance.sender}\n"
        f"Preview: {instance.text[:120] if instance.text else '[file]'}\n"
        f"Link: {link}"
    )
    _send_admin_alert(subject, body)


@receiver(post_save, sender=Customer)
def notify_customer(sender, instance, created, **kwargs):
    if not created:
        return
    subject = "New Customer Signup"
    body = f"New customer registered.\n\nName: {instance.first_name} {instance.last_name}\nEmail: {instance.email}\nLink: /dashboard/customers/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=ProviderProfile)
def notify_provider(sender, instance, created, **kwargs):
    if not created:
        return
    subject = "New Provider Profile"
    body = f"New provider profile created.\n\nProvider: {instance.user}\nLink: /dashboard/provider-profiles/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=NoShowReport)
def notify_no_show(sender, instance, created, **kwargs):
    if not created:
        return
    subject = "No-Show Report Submitted"
    body = f"No-show report submitted.\n\nBooking: {instance.booking_type} #{instance.booking_id}\nStatus: {instance.decision}\nLink: /dashboard/no-show/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=BookingRequestFix)
def notify_request_fix(sender, instance, created, **kwargs):
    subject = "Booking Request Fix Updated"
    if created:
        subject = "New Booking Request Fix"
    body = f"Request fix update.\n\nBooking: {instance.booking_type} #{instance.booking_id}\nStatus: {instance.status}\nLink: /dashboard/request-fixes/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=CustomerNote)
def notify_customer_note(sender, instance, created, **kwargs):
    subject = "Customer Notes Updated"
    if created:
        subject = "Customer Notes Added"
    body = f"Customer notes changed.\n\nCustomer: {instance.customer}\nLink: /dashboard/customer-notes/"
    _send_admin_alert(subject, body)
