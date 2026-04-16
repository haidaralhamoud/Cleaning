from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            return

        try:
            from allauth.socialaccount.models import SocialApp
            from django.contrib.sites.models import Site
        except Exception:
            return

        try:
            site = Site.objects.get(id=settings.SITE_ID)
        except Exception:
            return

        try:
            apps = list(SocialApp.objects.filter(provider="google").order_by("id"))
            matched_app = None

            for app in apps:
                if (app.client_id or "").strip() == client_id.strip():
                    matched_app = app
                    break

            if matched_app is None:
                for app in apps:
                    if site in app.sites.all():
                        matched_app = app
                        break

            if matched_app is None:
                matched_app = SocialApp(provider="google")

            app = matched_app
            app.name = "Google"
            app.client_id = client_id
            app.secret = client_secret
            app.key = ""
            app.save()
            app.sites.add(site)
        except Exception:
            logger.exception("Failed to sync Google SocialApp for site_id=%s", settings.SITE_ID)
            return
