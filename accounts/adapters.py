import logging
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.core.exceptions import MultipleObjectsReturned
from django.conf import settings

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
    def get_app(self, request, provider, client_id=None):
        try:
            return super().get_app(request, provider, client_id=client_id)
        except MultipleObjectsReturned:
            app = self._select_preferred_app(request, provider, client_id=client_id)
            if app is not None:
                logger.warning(
                    "Multiple social apps matched provider=%s client_id=%s; using app id=%s name=%s",
                    provider,
                    client_id,
                    app.id,
                    app.name,
                )
                return app
            logger.exception(
                "Multiple social apps matched provider=%s client_id=%s and no deterministic fallback was found",
                provider,
                client_id,
            )
            raise

    def _select_preferred_app(self, request, provider, client_id=None):
        apps = self.list_apps(request, provider=provider, client_id=client_id)
        visible_apps = [app for app in apps if not getattr(app, "settings", {}).get("hidden")]
        candidates = visible_apps or apps
        db_candidates = [app for app in candidates if isinstance(app, SocialApp)]
        if not db_candidates:
            return candidates[0] if len(candidates) == 1 else None

        configured_client_id = (getattr(settings, "GOOGLE_CLIENT_ID", "") or "").strip()
        if configured_client_id:
            exact_matches = [
                app for app in db_candidates if (app.client_id or "").strip() == configured_client_id
            ]
            if len(exact_matches) == 1:
                return exact_matches[0]
            if len(exact_matches) > 1:
                db_candidates = exact_matches

        named_matches = [app for app in db_candidates if (app.name or "").strip().lower() == "google"]
        if len(named_matches) == 1:
            return named_matches[0]
        if len(named_matches) > 1:
            db_candidates = named_matches

        if len(db_candidates) == 1:
            return db_candidates[0]
        return sorted(db_candidates, key=lambda app: app.pk)[0]

    def on_authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        try:
            try:
                redirect_uri = request.build_absolute_uri() if request else None
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
        except Exception:
            logger.exception("Failed while logging social authentication error")
        return super().on_authentication_error(request, provider_id, error, exception, extra_context)
