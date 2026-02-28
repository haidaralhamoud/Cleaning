import logging
from django.conf import settings
from allauth.socialaccount.signals import social_account_error
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(social_account_error)
def log_social_login_error(request, provider, error, exception, **kwargs):
    try:
        redirect_uri = request.build_absolute_uri()
    except Exception:
        redirect_uri = None

    logger.error(
        "Social login error: provider=%s error=%s exception=%s redirect_uri=%s client_id=%s",
        getattr(provider, "id", provider),
        error,
        exception,
        redirect_uri,
        getattr(settings, "GOOGLE_CLIENT_ID", None),
    )
