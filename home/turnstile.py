"""Verify public submissions before their views save data or send mail."""

import json
import logging
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
CHECKOUT_CLEARANCE = "turnstile_checkout_verified_at"
CHECKOUT_CLEARANCE_SECONDS = 30 * 60

SUBMISSION_ACTIONS = {
    "home:careers_home": "application",
    "home:apply_page": "application",
    "home:contact": "contact",
    "home:service_contact_submit": "contact",
    "home:feedback_request": "feedback",
    "home:submit_call_request": "call_request",
    "home:submit_home_service_inquiry": "home_inquiry",
    "home:submit_airbnb_management_request": "airbnb_inquiry",
    "home:business_scheduling": "business_booking",
    "accounts:sign_up": "signup",
    "password_reset": "password_reset",
}
JSON_VIEWS = {
    "home:submit_call_request", "home:submit_home_service_inquiry",
    "home:submit_airbnb_management_request",
}
ERROR_MESSAGE = "Please complete the security check and try again. Your request has not been sent."


def turnstile_context(request):
    return {
        "turnstile_enabled": settings.TURNSTILE_ENABLED,
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
    }


def verify_token(token, action):
    if not isinstance(token, str) or not token.strip() or len(token) > 2048:
        return False
    payload = urlencode({"secret": settings.TURNSTILE_SECRET_KEY, "response": token}).encode()
    verification = Request(SITEVERIFY_URL, data=payload, method="POST")
    try:
        with urlopen(verification, timeout=5) as response:
            result = json.loads(response.read(16384))
    except (URLError, OSError, ValueError):
        # Never log the token, secret, or submitted form data.
        logger.warning("Turnstile verification service unavailable")
        return False
    return (
        isinstance(result, dict)
        and result.get("success") is True
        and result.get("action") == action
        and isinstance(result.get("hostname"), str)
        and result["hostname"].lower() in settings.TURNSTILE_ALLOWED_HOSTNAMES
    )


def submission_action(request, view_name):
    if view_name == "home:private_zip_step1":
        return "zip_request" if "contact-submit" in request.POST else None
    if view_name == "home:private_zip_available":
        form_type = request.POST.get("form_type")
        return form_type if form_type in {"call_request", "email_request"} else None
    return SUBMISSION_ACTIONS.get(view_name)


def challenge_response(request, *, checkout=False, failed=False):
    # This standalone page deliberately avoids unrelated database context processors.
    html = render_to_string("home/turnstile_check.html", {
        **turnstile_context(request),
        "checkout": checkout,
        "failed": failed,
        "error_message": ERROR_MESSAGE,
        "retry_url": request.get_full_path(),
        "csrf_token": get_token(request),
    })
    response = HttpResponse(html, status=403 if failed else 200)
    response["Cache-Control"] = "no-store"
    return response


class TurnstileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        had_draft = bool(getattr(request, "session", {}).get("private_booking_draft"))
        response = self.get_response(request)
        # Completing an order removes its draft; the next order needs a new check.
        if had_draft and "private_booking_draft" not in request.session:
            request.session.pop(CHECKOUT_CLEARANCE, None)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not settings.TURNSTILE_ENABLED:
            return None
        view_name = request.resolver_match.view_name
        if view_name in {"home:private_booking_checkout", "home:private_booking_cash_invoice_pdf"}:
            # Check before checkout creates a payment intent, not after Stripe charges.
            # Payment callbacks/webhooks always keep their own Stripe verification.
            verified_at = request.session.get(CHECKOUT_CLEARANCE)
            if isinstance(verified_at, (int, float)) and 0 <= time.time() - verified_at < CHECKOUT_CLEARANCE_SECONDS:
                return None
            if view_name == "home:private_booking_cash_invoice_pdf":
                return redirect("home:private_booking_checkout") if request.method == "POST" else None
            if not (request.session.get("private_booking_draft") or request.GET.get("payment_intent_id")
                    or request.GET.get("payment_intent") or request.session.get("latest_private_payment_intent_id")):
                return None
            if request.method == "POST" and request.POST.get("form_type") == "turnstile_checkout":
                if verify_token(request.POST.get("cf-turnstile-response"), "private_checkout"):
                    request.session[CHECKOUT_CLEARANCE] = time.time()
                    return redirect(request.get_full_path())
                return challenge_response(request, checkout=True, failed=True)
            return challenge_response(request, checkout=True)

        if request.method != "POST":
            return None
        action = submission_action(request, view_name)
        if not action or verify_token(request.POST.get("cf-turnstile-response"), action):
            return None
        if view_name in JSON_VIEWS or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "error": ERROR_MESSAGE,
                "errors": {"turnstile": [ERROR_MESSAGE]},
            }, status=403)
        return challenge_response(request, failed=True)
