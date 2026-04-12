import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse

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


def _contact_support_email():
    return getattr(settings, "CONTACT_SUPPORT_EMAIL", _admin_email())


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


def _public_base_url():
    for host in getattr(settings, "ALLOWED_HOSTS", []):
        if host and host not in {"*", "localhost", "127.0.0.1", "45.93.137.166"} and "." in host:
            return f"https://{host}"
    return ""


def _private_booking_customer_email(booking):
    user = getattr(booking, "user", None)
    if user and user.email:
        return user.email.strip()

    customer = Customer.objects.filter(user_id=getattr(booking, "user_id", None)).first()
    if customer and customer.email:
        return customer.email.strip()
    return ""


def _business_booking_customer_email(booking):
    email = (getattr(booking, "email", "") or "").strip()
    if email:
        return email

    user = getattr(booking, "user", None)
    if user and user.email:
        return user.email.strip()
    return ""


def _private_booking_customer_name(booking):
    user = getattr(booking, "user", None)
    if user:
        full_name = user.get_full_name().strip()
        if full_name:
            return full_name

    customer = Customer.objects.filter(user_id=getattr(booking, "user_id", None)).first()
    if customer:
        full_name = f"{customer.first_name} {customer.last_name}".strip()
        if full_name:
            return full_name

    if user and user.username:
        return user.username
    return "there"


def _business_booking_customer_name(booking):
    for value in (
        getattr(booking, "contact_person", ""),
        getattr(booking, "company_name", ""),
    ):
        value = (value or "").strip()
        if value:
            return value

    user = getattr(booking, "user", None)
    if user:
        full_name = user.get_full_name().strip()
        if full_name:
            return full_name
        if user.username:
            return user.username
    return "there"


def _private_booking_service_titles(booking):
    selected_services = getattr(booking, "selected_services", None) or []
    if not isinstance(selected_services, list) or not selected_services:
        return []

    services_by_slug = {
        service.slug: service.title
        for service in PrivateBooking._meta.apps.get_model("home", "PrivateService").objects.filter(
            slug__in=selected_services
        )
    }
    return [services_by_slug.get(slug, str(slug).replace("-", " ").title()) for slug in selected_services]


def _business_booking_service_label(booking):
    for value in (
        getattr(booking, "selected_service", ""),
        getattr(getattr(booking, "selected_bundle", None), "title", ""),
    ):
        value = (value or "").strip()
        if value:
            return value

    services_needed = getattr(booking, "services_needed", None) or []
    if isinstance(services_needed, list) and services_needed:
        return ", ".join(str(item) for item in services_needed)
    return "Business cleaning service"


def _private_booking_details_url(booking):
    base_url = _public_base_url()
    if not base_url:
        return ""
    try:
        return f"{base_url}{reverse('accounts:view_service_details', args=['private', booking.id])}"
    except NoReverseMatch:
        return ""


def _business_booking_details_url(booking):
    base_url = _public_base_url()
    if not base_url:
        return ""
    try:
        return f"{base_url}{reverse('accounts:view_service_details', args=['business', booking.id])}"
    except NoReverseMatch:
        return ""


def _send_private_booking_confirmation(booking):
    recipient = _private_booking_customer_email(booking)
    if not recipient:
        return

    booking_url = _private_booking_details_url(booking)
    context = {
        "customer_name": _private_booking_customer_name(booking),
        "booking": booking,
        "service_titles": _private_booking_service_titles(booking),
        "booking_date": booking.appointment_date,
        "booking_time_window": booking.appointment_time_window or "",
        "booking_total": booking.payment_amount or booking.total_price,
        "booking_currency": (booking.payment_currency or "SEK").upper(),
        "booking_url": booking_url,
    }
    subject = f"Your booking is confirmed #{booking.id}"
    text_body = render_to_string("home/emails/private_booking_confirmation.txt", context)
    html_body = render_to_string("home/emails/private_booking_confirmation.html", context)
    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [recipient])
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send private booking confirmation email for booking %s", booking.id)


def _send_business_booking_confirmation(booking):
    recipient = _business_booking_customer_email(booking)
    if not recipient:
        return

    context = {
        "customer_name": _business_booking_customer_name(booking),
        "booking": booking,
        "service_label": _business_booking_service_label(booking),
        "booking_date": booking.custom_date or booking.start_date,
        "booking_time_window": booking.custom_time or booking.preferred_time or "",
        "booking_url": _business_booking_details_url(booking),
    }
    subject = f"Your business booking is confirmed #{booking.id}"
    text_body = render_to_string("home/emails/business_booking_confirmation.txt", context)
    html_body = render_to_string("home/emails/business_booking_confirmation.html", context)
    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [recipient])
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send business booking confirmation email for booking %s", booking.id)


def _booking_admin_url(booking_type, booking_id):
    if booking_type == "business":
        return f"/dashboard/business-bookings/{booking_id}/edit/"
    return f"/dashboard/private-bookings/{booking_id}/edit/"


@receiver(post_save, sender=PrivateBooking)
def notify_private_booking(sender, instance, created, **kwargs):
    if not created:
        return
    _send_private_booking_confirmation(instance)
    subject = f"New Private Booking #{instance.id}"
    body = f"A new private booking was created.\n\nBooking ID: {instance.id}\nStatus: {instance.status}\nLink: {_booking_admin_url('private', instance.id)}"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=BusinessBooking)
def notify_business_booking(sender, instance, created, **kwargs):
    if not created:
        return
    _send_business_booking_confirmation(instance)
    subject = f"New Business Booking #{instance.id}"
    body = f"A new business booking was created.\n\nBooking ID: {instance.id}\nStatus: {instance.status}\nLink: {_booking_admin_url('business', instance.id)}"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=Contact)
def notify_contact(sender, instance, created, **kwargs):
    if not created:
        return
    dashboard_link = "/dashboard/contacts/"
    subject = "New Contact Message"
    body = f"New contact received.\n\nName: {instance.first_name} {instance.last_name}\nEmail: {instance.email}\nType: {instance.inquiry_type}\nLink: {dashboard_link}"
    recipient = _contact_support_email()
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
        logger.exception("Failed to send contact form email")


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
