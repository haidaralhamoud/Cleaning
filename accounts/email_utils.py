from django.conf import settings
from django.core.mail import get_connection


def verification_from_email():
    return getattr(settings, "VERIFICATION_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)


def verification_email_connection():
    return get_connection(
        backend=getattr(settings, "VERIFICATION_EMAIL_BACKEND", settings.EMAIL_BACKEND),
        host=getattr(settings, "VERIFICATION_EMAIL_HOST", settings.EMAIL_HOST),
        port=getattr(settings, "VERIFICATION_EMAIL_PORT", settings.EMAIL_PORT),
        username=getattr(settings, "VERIFICATION_EMAIL_HOST_USER", settings.EMAIL_HOST_USER),
        password=getattr(settings, "VERIFICATION_EMAIL_HOST_PASSWORD", settings.EMAIL_HOST_PASSWORD),
        use_tls=getattr(settings, "VERIFICATION_EMAIL_USE_TLS", settings.EMAIL_USE_TLS),
        use_ssl=getattr(settings, "VERIFICATION_EMAIL_USE_SSL", settings.EMAIL_USE_SSL),
        timeout=getattr(settings, "VERIFICATION_EMAIL_TIMEOUT", settings.EMAIL_TIMEOUT),
    )
