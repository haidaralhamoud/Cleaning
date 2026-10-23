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
    CommunicationPreference,
    CustomerNotification,
    CustomerNote,
    Incident,
    ServiceReview,
    ChatMessage,
    BookingRequestFix,
)
from home.models import (
    Application,
    CallRequest,
    Contact,
    PrivateBooking,
    BusinessBooking,
    NoShowReport,
    FeedbackRequest,
    HomeServiceInquiry,
    AirbnbManagementRequest,
    NotAvailableZipRequest,
)

logger = logging.getLogger(__name__)


def _admin_email():
    return getattr(settings, "ADMIN_ALERT_EMAIL", "Services@hemblaexperten.se")


def _contact_support_email():
    return getattr(settings, "CONTACT_SUPPORT_EMAIL", _admin_email())


def _send_admin_alert(subject, body):
    recipient = _admin_email()
    if not recipient:
        logger.error("Admin booking alert was not sent because ADMIN_ALERT_EMAIL is empty.")
        return False
    try:
        sent_count = send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        if sent_count != 1:
            logger.error(
                "Admin booking alert returned an unexpected sent count (%s) for %s.",
                sent_count,
                recipient,
            )
            return False
        return True
    except Exception:
        logger.exception("Failed to send admin alert email to %s (subject=%s)", recipient, subject)
        return False


def _send_customer_email(recipient, subject, body, *, reference="customer request"):
    recipient = (recipient or "").strip()
    if not recipient or recipient.lower() == "no-reply@example.com":
        return False
    try:
        return send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        ) == 1
    except Exception:
        logger.exception("Failed to send %s email to %s", reference, recipient)
        return False


@receiver(post_save, sender=Application)
def notify_job_application(sender, instance, created, **kwargs):
    """Acknowledge the candidate and alert the company about a new application."""
    if not created:
        return

    role = instance.job.title if instance.job_id else (instance.area or "Open application")
    candidate_email = (instance.email or "").strip()
    if candidate_email:
        customer_body = (
            f"Hello {instance.full_name},\n\n"
            "Thank you for your interest in joining Hembla Experten. "
            "We have received your application and our team will review it.\n\n"
            f"Application number: {instance.pk}\n"
            f"Role: {role}\n"
            f"Availability: {instance.availability or 'Not specified'}\n\n"
            "We will contact you if your profile matches the role.\n\n"
            "Best regards,\nHembla Experten"
        )
        try:
            send_mail(
                f"We received your application #{instance.pk}",
                customer_body,
                settings.DEFAULT_FROM_EMAIL,
                [candidate_email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Failed to send application confirmation for application %s", instance.pk)

    admin_body = (
        "A new job application was received.\n\n"
        f"Application ID: {instance.pk}\n"
        f"Name: {instance.full_name}\n"
        f"Email: {instance.email}\n"
        f"Phone: {instance.phone}\n"
        f"Role: {role}\n"
        f"Preferred area: {instance.area or 'Not specified'}\n"
        f"Availability: {instance.availability or 'Not specified'}\n"
        f"Message: {instance.message or 'None'}\n\n"
        "Dashboard: /dashboard/applications/"
    )
    _send_admin_alert(f"New Job Application #{instance.pk} - {instance.full_name}", admin_body)


@receiver(post_save, sender=NotAvailableZipRequest)
def notify_unavailable_zip_request(sender, instance, created, **kwargs):
    if not created:
        return
    service = instance.service.title if instance.service_id else "Not specified"
    _send_customer_email(
        instance.email,
        f"We received your service-area request #{instance.pk}",
        (
            f"Hello {instance.first_name},\n\n"
            "Thank you for contacting Hembla Experten. We received your request and will review "
            "service availability in your area.\n\n"
            f"ZIP code: {instance.zip_code}\nService: {service}\n\n"
            "Our team will contact you when we have an update.\n\nBest regards,\nHembla Experten"
        ),
        reference=f"unavailable ZIP request #{instance.pk}",
    )
    _send_admin_alert(
        f"New Service-Area Request #{instance.pk}",
        (
            "A customer requested service in an unavailable ZIP code.\n\n"
            f"Name: {instance.first_name} {instance.last_name}\nEmail: {instance.email}\n"
            f"Phone: {instance.phone}\nZIP code: {instance.zip_code}\nService: {service}\n"
            f"Message: {instance.message or 'None'}\n\nDashboard: /dashboard/not-available-zips/"
        ),
    )


@receiver(post_save, sender=CallRequest)
def notify_company_about_call_request(sender, instance, created, **kwargs):
    if not created:
        return
    preferred_time = instance.preferred_time.strftime("%Y-%m-%d %H:%M") if instance.preferred_time else "Not specified"
    _send_admin_alert(
        f"New Call Request #{instance.pk}",
        (
            "A customer requested a call.\n\n"
            f"Name: {instance.full_name}\nEmail: {instance.email}\nPhone: {instance.phone}\n"
            f"Preferred time: {preferred_time}\nLanguage: {instance.language or 'Not specified'}\n"
            f"Message: {instance.message or 'None'}\n\nDashboard: /dashboard/call-requests/"
        ),
    )


@receiver(post_save, sender=HomeServiceInquiry)
def notify_home_service_inquiry(sender, instance, created, **kwargs):
    """Send both sides of the acknowledgement for the homepage request form."""
    if not created:
        return

    date_label = instance.preferred_date.strftime("%B %d, %Y") if instance.preferred_date else "Not specified"
    time_label = instance.preferred_time.strftime("%H:%M") if instance.preferred_time else "Not specified"
    customer_body = (
        "Thank you for contacting Hembla Experten. We have received your cleaning request.\n\n"
        f"Request number: {instance.pk}\n"
        f"Service: {instance.service}\n"
        f"Address: {instance.address}\n"
        f"Preferred date: {date_label}\n"
        f"Preferred time: {time_label}\n\n"
        "This is a request, not a confirmed booking. Our team will contact you shortly "
        "to confirm availability and the details."
    )
    try:
        send_mail(
            f"We received your cleaning request #{instance.pk}",
            customer_body,
            settings.DEFAULT_FROM_EMAIL,
            [instance.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send home service inquiry confirmation for inquiry %s", instance.pk)

    admin_body = (
        f"A new home service request was received.\n\n"
        f"Request ID: {instance.pk}\n"
        f"Service: {instance.service}\n"
        f"Address: {instance.address}\n"
        f"Email: {instance.email}\n"
        f"Phone: {instance.phone}\n"
        f"Preferred date: {date_label}\n"
        f"Preferred time: {time_label}\n"
        f"Additional information: {instance.message or 'None'}\n\n"
        "Dashboard: /dashboard/home-service-inquiries/"
    )
    _send_admin_alert(f"New Home Service Request #{instance.pk}", admin_body)


@receiver(post_save, sender=AirbnbManagementRequest)
def notify_airbnb_management_request(sender, instance, created, **kwargs):
    if not created:
        return

    services = ", ".join(instance.services or []) or "Not specified"
    customer_body = (
        f"Hello {instance.name},\n\n"
        "Thank you for contacting Hembla Experten. We have received your Airbnb management request.\n\n"
        f"Request number: {instance.pk}\n"
        f"Services: {services}\n"
        f"Properties: {instance.property_count}\n"
        f"Location: {instance.location or 'Not specified'}\n\n"
        "Our team will contact you shortly to discuss the best solution for your properties."
    )
    try:
        send_mail(
            f"We received your Airbnb management request #{instance.pk}",
            customer_body,
            settings.DEFAULT_FROM_EMAIL,
            [instance.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send Airbnb request confirmation for request %s", instance.pk)

    admin_body = (
        "A new Airbnb management request was received.\n\n"
        f"Request ID: {instance.pk}\n"
        f"Name: {instance.name}\n"
        f"Email: {instance.email}\n"
        f"Phone: {instance.phone}\n"
        f"Services: {services}\n"
        f"Properties: {instance.property_count}\n"
        f"Location: {instance.location or 'Not specified'}\n"
        f"Additional information: {instance.message or 'None'}\n\n"
        "Dashboard: /dashboard/airbnb-management-requests/"
    )
    _send_admin_alert(f"New Airbnb Management Request #{instance.pk}", admin_body)


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


def _create_booking_in_app_notification(user, *, title, body, booking_type, booking_id):
    if not user:
        return

    pref = CommunicationPreference.objects.filter(user=user).only("in_app").first()
    if pref is not None and not pref.in_app:
        return

    CustomerNotification.objects.create(
        user=user,
        title=title,
        body=body,
        notification_type="general",
        booking_type=booking_type,
        booking_id=booking_id,
    )


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
        "booking_time_window": booking.appointment_start_time.strftime("%H:%M") if getattr(booking, "appointment_start_time", None) else "",
        "booking_total": booking.payment_amount or booking.total_price,
        "booking_currency": (booking.payment_currency or "SEK").upper(),
        "booking_url": booking_url,
    }
    subject = f"Your booking is confirmed #{booking.id}"
    text_body = render_to_string("home/emails/private_booking_confirmation.txt", context)
    html_body = render_to_string("home/private_booking_confirmation_email.html", context)
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
    if getattr(instance, "user_id", None):
        service_titles = _private_booking_service_titles(instance)
        service_label = ", ".join(service_titles[:2]) if service_titles else "your service"
        if len(service_titles) > 2:
            service_label = f"{service_label} +{len(service_titles) - 2} more"
        _create_booking_in_app_notification(
            instance.user,
            title=f"Booking Confirmed #{instance.id}",
            body=f"Your private booking for {service_label} has been received and confirmed.",
            booking_type="private",
            booking_id=instance.id,
        )
    subject = f"New Private Booking #{instance.id}"
    body = f"A new private booking was created.\n\nBooking ID: {instance.id}\nStatus: {instance.status}\nLink: {_booking_admin_url('private', instance.id)}"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=BusinessBooking)
def notify_business_booking(sender, instance, created, **kwargs):
    if not created:
        return
    _send_business_booking_confirmation(instance)
    if getattr(instance, "user_id", None):
        _create_booking_in_app_notification(
            instance.user,
            title=f"Booking Confirmed #{instance.id}",
            body=f"Your business booking for {_business_booking_service_label(instance)} has been received and confirmed.",
            booking_type="business",
            booking_id=instance.id,
        )
    subject = f"New Business Booking #{instance.id}"
    body = f"A new business booking was created.\n\nBooking ID: {instance.id}\nStatus: {instance.status}\nLink: {_booking_admin_url('business', instance.id)}"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=Contact)
def notify_contact(sender, instance, created, **kwargs):
    if not created:
        return
    _send_customer_email(
        instance.email,
        "We received your message",
        (
            f"Hello {instance.first_name or 'Customer'},\n\n"
            "Thank you for contacting Hembla Experten. We have received your message and our team "
            "will get back to you as soon as possible.\n\n"
            f"Reference: Contact #{instance.pk}\n\nBest regards,\nHembla Experten"
        ),
        reference=f"contact confirmation #{instance.pk}",
    )
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
    customer_email = getattr(instance.customer, "email", "") if instance.customer_id else ""
    _send_customer_email(
        customer_email,
        f"We received your incident report #{instance.id}",
        (
            "Your incident report has been received and will be reviewed by our team.\n\n"
            f"Reference: Incident #{instance.id}\nSeverity: {instance.severity}\n\n"
            "We will contact you if additional information is needed.\n\nBest regards,\nHembla Experten"
        ),
        reference=f"incident confirmation #{instance.id}",
    )
    subject = f"New Incident #{instance.id}"
    body = f"New incident reported.\n\nIncident ID: {instance.id}\nSeverity: {instance.severity}\nLink: /dashboard/incidents/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=ServiceReview)
def notify_review(sender, instance, created, **kwargs):
    if not created:
        return
    customer_email = getattr(instance.customer, "email", "") if instance.customer_id else ""
    _send_customer_email(
        customer_email,
        "Thank you for your review",
        (
            "Thank you for sharing your feedback with Hembla Experten.\n\n"
            f"Service: {instance.service_title}\nRating: {instance.overall_rating}/5\n\n"
            "Your feedback helps us improve our service.\n\nBest regards,\nHembla Experten"
        ),
        reference=f"service review #{instance.id}",
    )
    subject = f"New Service Review ({instance.service_title})"
    body = f"A new review was submitted.\n\nService: {instance.service_title}\nRating: {instance.overall_rating}\nLink: /dashboard/service-reviews/"
    _send_admin_alert(subject, body)


@receiver(post_save, sender=FeedbackRequest)
def notify_feedback_request(sender, instance, created, **kwargs):
    if not created:
        return
    _send_customer_email(
        instance.email,
        f"We received your feedback #{instance.pk}",
        (
            f"Hello {instance.customer_name or 'Customer'},\n\n"
            "Thank you for contacting Hembla Experten. We received your feedback/request and "
            "our team will review it.\n\n"
            f"Reference: Feedback #{instance.pk}\n\nBest regards,\nHembla Experten"
        ),
        reference=f"feedback confirmation #{instance.pk}",
    )
    subject = "New Feedback Pending Review"
    sender_label = (instance.customer_name or instance.email or f"Feedback #{instance.pk}").strip()
    preview = (instance.feedback_text or "").strip()
    if len(preview) > 160:
        preview = f"{preview[:160]}..."
    body = (
        f"A new feedback submission is waiting for admin approval.\n\n"
        f"Sender: {sender_label}\n"
        f"Rating: {instance.rating}/5\n"
        f"Preview: {preview or 'No feedback text'}\n"
        f"Link: /dashboard/feedback/"
    )
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
    if created:
        customer_email = getattr(instance.customer, "email", "") if instance.customer_id else ""
        _send_customer_email(
            customer_email,
            f"We received your booking correction request #{instance.id}",
            (
                "Your request to correct booking details has been received.\n\n"
                f"Booking: {instance.booking_type.title()} #{instance.booking_id}\n"
                f"Reference: Request #{instance.id}\n\n"
                "Our team will review it and update you.\n\nBest regards,\nHembla Experten"
            ),
            reference=f"booking correction request #{instance.id}",
        )


@receiver(post_save, sender=CustomerNote)
def notify_customer_note(sender, instance, created, **kwargs):
    subject = "Customer Notes Updated"
    if created:
        subject = "Customer Notes Added"
    body = f"Customer notes changed.\n\nCustomer: {instance.customer}\nLink: /dashboard/customer-notes/"
    _send_admin_alert(subject, body)
