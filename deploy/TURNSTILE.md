# Turnstile

Add these values to the server's `.env` beside `manage.py`:

```dotenv
TURNSTILE_SITE_KEY=your_public_site_key
TURNSTILE_SECRET_KEY=your_private_secret_key
TURNSTILE_ALLOWED_HOSTNAMES=hembla-experten.se,www.hembla-experten.se
```

Register the same hostnames on the Cloudflare widget and use Managed mode. Keep
the secret in `.env`, out of Git and frontend code. Protection enables when keys
are present; an enabled installation with a missing key refuses to start.
`TURNSTILE_ENABLED=false` explicitly disables it. Tests disable it by default;
security tests enable it with mocked verification and fake credentials.

After uploading the updated Python, templates, and static source files, activate
the server's existing virtual environment and run beside `manage.py`:

```sh
python manage.py check
python manage.py collectstatic --noinput
sudo systemctl restart hembla
```

No database migrations are needed. Allow outbound HTTPS to
`challenges.cloudflare.com`. Test on the registered domain; production keys are
not for localhost. For local browser tests, use Cloudflare's documented test keys
in a separate development environment, never production settings.

Protected submissions: job and open applications, contact and service questions,
feedback, home and Airbnb enquiries, callback and email requests, unavailable ZIP
notifications, business booking confirmation, customer signup, and password reset.
Existing OTP verification and resend limits continue to apply. AJAX forms receive
JSON errors and refresh their single-use token for retry. Failed ordinary
submissions show a back-to-form page; the visitor may need to select an attachment
again if the browser did not retain it.

Private bookings are checked before checkout creates a Stripe payment intent.
Verification grants the browser session up to 30 minutes at checkout and clears
when the booking draft is removed. Direct invoice creation also requires this
clearance. Stripe confirmation and webhooks retain their existing Stripe
verification and are not blocked by an expired CAPTCHA after payment.

Browser checks after deployment:

1. Open a job application, complete Turnstile, and submit a test application.
2. Confirm it appears in the dashboard with its submission date.
3. Try home and Airbnb enquiries, including validation retries.
4. Reach private checkout and complete the security check before the payment form.
5. Confirm Turnstile analytics records successful server-side validations.

Server verification rejects missing, invalid, or expired tokens; wrong actions;
foreign hostnames; malformed responses; and verification service failures. CSRF
remains required. The verifier never logs secrets or tokens.
