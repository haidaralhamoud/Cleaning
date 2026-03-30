import logging
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .email_utils import verification_email_connection, verification_from_email

logger = logging.getLogger(__name__)


class VerificationEmailAccountAdapter(DefaultAccountAdapter):
    def get_from_email(self):
        return verification_from_email()

    def send_mail(self, template_prefix, email, context):
        message = self.render_mail(template_prefix, email, context)
        message.from_email = verification_from_email()
        message.connection = verification_email_connection()
        message.send()


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
