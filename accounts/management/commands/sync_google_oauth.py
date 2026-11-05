from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Explicitly sync the configured Google OAuth application after migrations."

    def handle(self, *args, **options):
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise CommandError("Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET first.")
        with transaction.atomic():
            site, _ = Site.objects.get_or_create(pk=settings.SITE_ID, defaults={
                "domain": "hembla-experten.se", "name": "Hembla Experten"})
            app = SocialApp.objects.filter(provider="google", sites=site).first()
            if app is None:
                app = SocialApp(provider="google")
            app.name = "Google"
            app.client_id = settings.GOOGLE_CLIENT_ID
            app.secret = settings.GOOGLE_CLIENT_SECRET
            app.key = ""
            app.save()
            app.sites.add(site)
        self.stdout.write("Google OAuth application synchronized without displaying credentials.")
