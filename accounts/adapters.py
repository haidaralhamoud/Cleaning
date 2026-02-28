import logging
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

logger = logging.getLogger(__name__)


class SocialAccountLoggingAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        try:
            redirect_uri = request.build_absolute_uri()
        except Exception:
            redirect_uri = None

        logger.error(
            "Social login error: provider=%s error=%s exception=%s redirect_uri=%s client_id=%s",
            provider_id,
            error,
            exception,
            redirect_uri,
            getattr(settings, "GOOGLE_CLIENT_ID", None),
        )
        return super().on_authentication_error(request, provider_id, error, exception, extra_context)
