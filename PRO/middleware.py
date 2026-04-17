from urllib.parse import parse_qs, urlparse

from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseForbidden

from accounts.models import UserAccessProfile


class AdminSiteAccessGuard:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info or ""
        if path.startswith("/admin/"):
            if request.user.is_authenticated:
                profile = getattr(request.user, "access_profile", None)
                if profile is None:
                    profile = UserAccessProfile.objects.create(user=request.user)
                    if request.user.is_superuser:
                        profile.role = "global_super"
                        profile.site = "main"
                        profile.save()
                role = getattr(profile, "role", "") if profile else ""
                site = getattr(profile, "site", "main") if profile else "main"
                if role != "global_super" and site != "main":
                    return HttpResponseForbidden("Forbidden")
        return self.get_response(request)


class LoginRedirectMessageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            return response

        if response.status_code not in {301, 302, 303, 307, 308}:
            return response

        location = response.headers.get("Location") or ""
        if not location:
            return response

        parsed = urlparse(location)
        login_path = (parsed.path or "").rstrip("/")
        if login_path != "/accounts/login":
            return response

        next_value = parse_qs(parsed.query).get("next", [""])[0]
        target_path = (next_value or request.get_full_path() or "").lower()
        message_text = self._message_for_target(target_path)
        if not message_text:
            return response

        storage = getattr(request, "_messages", None)
        if storage is None:
            return response

        messages.warning(request, message_text)
        return response

    @staticmethod
    def _message_for_target(target_path):
        if not target_path:
            return ""

        message_map = [
            ("/booking/checkout/", "Please sign in to continue to checkout."),
            ("/booking/payment/complete/", "Please sign in to complete your payment."),
            ("/payment/success/", "Please sign in to view your payment status."),
            ("/business/", "Please sign in to continue your business booking."),
            ("/private/booking/", "Please sign in to continue your booking."),
            ("/accounts/chat/", "Please sign in to open your chat."),
            ("/accounts/booking/", "Please sign in to manage this booking."),
            ("/accounts/customer_profile_view/", "Please sign in to view your profile."),
            ("/accounts/address_and_locations_view/", "Please sign in to manage your addresses."),
            ("/accounts/my_bookimg/", "Please sign in to view your bookings."),
            ("/accounts/incident/", "Please sign in to view your incidents."),
            ("/accounts/service_preferences/", "Please sign in to manage your service preferences."),
            ("/accounts/communication/", "Please sign in to manage your communication settings."),
            ("/accounts/customer_notes/", "Please sign in to manage your customer notes."),
            ("/accounts/payment_and_billing/", "Please sign in to manage payment and billing."),
            ("/accounts/change_password/", "Please sign in to change your password."),
            ("/accounts/service_history_and_ratings/", "Please sign in to view your service history and ratings."),
            ("/accounts/loyalty_and_rewards/", "Please sign in to view your loyalty rewards."),
            ("/accounts/provider/messages/", "Please sign in to view provider messages."),
            ("/accounts/provider/profile/", "Please sign in to view your provider profile."),
            ("/accounts/", "Please sign in to continue."),
        ]

        for marker, message_text in message_map:
            if marker in target_path:
                return message_text

        return ""


class StaticAssetCacheMiddleware:
    IMMUTABLE_EXTENSIONS = {
        ".css",
        ".js",
        ".mjs",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".svg",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".mp4",
        ".webm",
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self.static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path_info or ""
        if not path.startswith(self.static_url):
            return response

        if response.has_header("Cache-Control"):
            return response

        lower_path = path.lower()
        if any(lower_path.endswith(ext) for ext in self.IMMUTABLE_EXTENSIONS):
            response["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response["Cache-Control"] = "public, max-age=3600"

        return response
