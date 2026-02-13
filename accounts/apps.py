from django.apps import AppConfig
from django.conf import settings


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
            app, _ = SocialApp.objects.get_or_create(provider="google")
            app.name = "Google"
            app.client_id = client_id
            app.secret = client_secret
            app.key = ""
            app.save()
            app.sites.add(site)
        except Exception:
            return
