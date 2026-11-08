import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from home.models import Application, HomeServiceInquiry, Job
from home.turnstile import CHECKOUT_CLEARANCE, TurnstileMiddleware, verify_token


TURNSTILE_TEST_SETTINGS = {
    "TURNSTILE_ENABLED": True,
    "TURNSTILE_SITE_KEY": "public-test-key",
    "TURNSTILE_SECRET_KEY": "private-test-secret",
    "TURNSTILE_ALLOWED_HOSTNAMES": ["hembla-experten.se", "www.hembla-experten.se"],
}


@override_settings(**TURNSTILE_TEST_SETTINGS)
class TurnstileVerificationTests(SimpleTestCase):
    def verify_response(self, result, action="application"):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(result).encode()
        with patch("home.turnstile.urlopen", return_value=response) as call:
            verified = verify_token("a-token", action)
        return verified, call

    def test_accepts_matching_action_and_hostname(self):
        verified, call = self.verify_response({
            "success": True, "action": "application", "hostname": "hembla-experten.se",
        })
        self.assertTrue(verified)
        self.assertEqual(call.call_args.kwargs["timeout"], 5)
        request = call.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "https://challenges.cloudflare.com/turnstile/v0/siteverify")
        self.assertIn(b"secret=private-test-secret", request.data)

    def test_rejects_failed_expired_foreign_and_malformed_results(self):
        for result in [
            {"success": False, "error-codes": ["timeout-or-duplicate"]},
            {"success": True, "action": "signup", "hostname": "hembla-experten.se"},
            {"success": True, "action": "application", "hostname": "attacker.example"},
            {"success": True, "action": "application", "hostname": None},
            {"success": "true", "action": "application", "hostname": "hembla-experten.se"},
            [], None,
        ]:
            with self.subTest(result=result):
                self.assertFalse(self.verify_response(result)[0])

    def test_missing_and_oversized_tokens_do_not_contact_cloudflare(self):
        with patch("home.turnstile.urlopen") as call:
            for token in [None, "", " ", "x" * 2049]:
                self.assertFalse(verify_token(token, "application"))
            call.assert_not_called()

    def test_network_failure_fails_closed_without_logging_secrets(self):
        with patch("home.turnstile.urlopen", side_effect=URLError("unavailable")):
            with self.assertLogs("home.turnstile", level="WARNING") as logs:
                self.assertFalse(verify_token("a-token", "application"))
        self.assertNotIn(settings.TURNSTILE_SECRET_KEY, "".join(logs.output))
        self.assertNotIn("a-token", "".join(logs.output))

    def test_invalid_json_fails_closed(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"not json"
        with patch("home.turnstile.urlopen", return_value=response):
            with self.assertLogs("home.turnstile", level="WARNING"):
                self.assertFalse(verify_token("a-token", "application"))

    def test_widget_exposes_only_public_key(self):
        html = render_to_string("home/includes/turnstile.html", {
            "turnstile_enabled": True,
            "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
            "turnstile_action": "application",
        })
        self.assertIn('data-sitekey="public-test-key"', html)
        self.assertIn('data-action="application"', html)
        self.assertNotIn(settings.TURNSTILE_SECRET_KEY, html)


@override_settings(**TURNSTILE_TEST_SETTINGS)
class TurnstileMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TurnstileMiddleware(lambda request: HttpResponse("view ran"))

    def request(self, view_name, data=None, method="post", session=None):
        request = getattr(self.factory, method)("/example/", data or {})
        request.session = session if session is not None else {}
        request.resolver_match = SimpleNamespace(view_name=view_name)
        return request

    def process(self, request):
        return self.middleware.process_view(request, None, (), {})

    def test_all_public_submission_routes_reject_missing_tokens(self):
        routes = [
            "home:careers_home", "home:apply_page", "home:contact",
            "home:service_contact_submit", "home:feedback_request",
            "home:submit_call_request", "home:submit_home_service_inquiry",
            "home:submit_airbnb_management_request", "home:business_scheduling",
            "accounts:sign_up", "password_reset",
        ]
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.process(self.request(route)).status_code, 403)

    def test_zip_lookup_stays_open_but_lead_submission_needs_check(self):
        self.assertIsNone(self.process(self.request("home:private_zip_step1", {"zip-submit": ""})))
        self.assertEqual(self.process(self.request("home:private_zip_step1", {"contact-submit": ""})).status_code, 403)
        for form_type in ["call_request", "email_request"]:
            self.assertEqual(self.process(self.request("home:private_zip_available", {"form_type": form_type})).status_code, 403)

    def test_checkout_is_challenged_before_payment_view(self):
        request = self.request("home:private_booking_checkout", method="get", session={"private_booking_draft": {"selected_services": ["cleaning"]}})
        response = self.process(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-action="private_checkout"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn(settings.TURNSTILE_SECRET_KEY.encode(), response.content)

    @patch("home.turnstile.verify_token", return_value=True)
    def test_checkout_verification_grants_session_clearance(self, verify):
        session = {"private_booking_draft": {"selected_services": ["cleaning"]}}
        request = self.request("home:private_booking_checkout", {
            "form_type": "turnstile_checkout", "cf-turnstile-response": "token",
        }, session=session)
        self.assertEqual(self.process(request).status_code, 302)
        verify.assert_called_once_with("token", "private_checkout")
        self.assertIn(CHECKOUT_CLEARANCE, session)
        self.assertIsNone(self.process(self.request("home:private_booking_checkout", method="get", session=session)))

    def test_old_checkout_clearance_is_not_accepted(self):
        session = {"private_booking_draft": {"selected_services": ["cleaning"]}, CHECKOUT_CLEARANCE: time.time() - 1801}
        self.assertContains(self.process(self.request("home:private_booking_checkout", method="get", session=session)), "Security check")

    def test_direct_invoice_post_cannot_bypass_check(self):
        self.assertEqual(self.process(self.request("home:private_booking_cash_invoice_pdf")).status_code, 302)

    def test_resuming_checkout_also_needs_verification(self):
        request = self.request("home:private_booking_checkout", {"payment_intent": "pi_example"}, method="get")
        self.assertContains(self.process(request), 'data-action="private_checkout"')

    def test_payment_confirmation_webhooks_and_admin_remain_unaffected(self):
        for route in ["home:stripe_webhook", "home:private_booking_payment_complete", "admin:index", "home:dashboard_model_create"]:
            with self.subTest(route=route):
                self.assertIsNone(self.process(self.request(route)))

    def test_finishing_booking_removes_clearance(self):
        session = {"private_booking_draft": {"selected_services": ["cleaning"]}, CHECKOUT_CLEARANCE: time.time()}
        request = self.request("home:private_booking_checkout", session=session)
        def finish(request):
            request.session.pop("private_booking_draft")
            return HttpResponse("finished")
        TurnstileMiddleware(finish)(request)
        self.assertNotIn(CHECKOUT_CLEARANCE, session)

    @override_settings(TURNSTILE_ENABLED=False)
    def test_disabled_configuration_keeps_existing_behavior(self):
        self.assertIsNone(self.process(self.request("home:apply_page")))


@override_settings(**TURNSTILE_TEST_SETTINGS)
class TurnstileSubmissionTests(TestCase):
    def test_missing_token_does_not_save_application_or_send_mail(self):
        job = Job.objects.create(title="Cleaner", description="Cleaning")
        response = self.client.post(reverse("home:apply_page", args=[job.pk]), {
            "full_name": "Applicant", "email": "person@example.com", "phone": "123", "job": job.pk,
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Application.objects.count(), 0)

    @patch("home.turnstile.verify_token", return_value=True)
    def test_valid_application_still_saves_and_records_submission_date(self, verify):
        job = Job.objects.create(title="Cleaner", description="Cleaning")
        response = self.client.post(reverse("home:apply_page", args=[job.pk]), {
            "full_name": "Applicant", "email": "person@example.com", "phone": "123", "job": job.pk,
            "cf-turnstile-response": "token",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(Application.objects.get().created_at)
        verify.assert_called_once_with("token", "application")

    def test_ajax_receives_usable_json_without_saving(self):
        response = self.client.post(reverse("home:submit_home_service_inquiry"), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["success"])
        self.assertIn("turnstile", response.json()["errors"])
        self.assertEqual(HomeServiceInquiry.objects.count(), 0)

    def test_csrf_protection_is_still_required(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        with patch("home.turnstile.verify_token") as verify:
            response = client.post(reverse("home:careers_home"), {"cf-turnstile-response": "token"})
        self.assertEqual(response.status_code, 403)
        verify.assert_not_called()
