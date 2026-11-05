# Technical remediation status - 2026-11-05

The original findings are in TECHNICAL_REVIEW.md. This file distinguishes code changes and verified local work from production operations that still require server/provider access.

## Implemented

- Disabled accounts are preserved during signup. A separate signup_pending flag allows safe resumption for the original pending registrant without reactivating an administratively disabled account. Inactive authentication is rejected by the custom backend.
- Login return URLs are checked for allowed host and HTTPS scheme.
- Verification uses one SMTP connection; request/resend handlers distinguish failure and cooldown. Unknown password-reset email responses no longer disclose account existence. Proxy-supplied IPs are accepted only through trusted proxies.
- Django updated to 5.2.19; django-allauth socialaccount dependencies and python-dotenv declared and installed. pip check passes.
- PostgreSQL configuration reads the environment. A strong local secret replaced the weak local key. HSTS is enabled for the current host without unverified subdomain/preload commitments.
- Dashboard access uses explicit model permissions or the full accounts.access_dashboard permission, rather than granting all operations solely through is_staff.
- Upload stream size, extension, signature and image dimensions are checked. Private attachment downloads check record ownership or staff permissions and avoid public caching.
- Notification email has a durable database outbox, bounded retries, a worker command and systemd timer examples. Jobs roll back with the originating transaction. Verification stays synchronous. Invoices are QUEUED and locked until SMTP accepts delivery, then become SENT; pending invoices are not exposed in customer billing.
- Loyalty fulfillment locks the booking and has a database uniqueness constraint. Finalization requires POST and a model change permission.
- Customer JSON values are escaped in booking admin displays. The broken static template tag and unversioned immutable-cache behavior are fixed. Empty-invoice totals use Decimal zero safely.
- Database writes during app startup were removed. Google OAuth has an explicit setup command.
- 1,719 generated/sensitive paths were removed from the current Git index while their files were retained. Ignore rules and safe environment examples are included.
- Deployment preflight, private backup command, and CI for SQLite/PostgreSQL were added.

## Verified locally

- Full latest completed run: 68 discovered tests, 66 passed and 2 PostgreSQL-only concurrency tests skipped on SQLite.
- All 114 HTML templates parse without errors. A fresh production collectstatic build, including manifest processing, also passed in an isolated temporary directory.
- A final billing integration check also passes: a queued invoice stays hidden from customer billing and appears after accepted delivery.
- No model changes missing migrations; installed package requirements have no reported conflicts.
- Local PostgreSQL connection succeeds. A database/media backup was created under ../backups/20261105T180257876213Z; pg_restore could read its catalog, and the media archive contains 200 entries. A complete restore rehearsal was not performed.
- Four local migrations were applied successfully; deployment preflight reports zero pending migrations and no duplicate loyalty awards.
- A direct attempt to run the concurrency tests against an isolated local PostgreSQL test database was blocked because the configured role does not have CREATEDB. No database roles were changed. CI provides its own isolated PostgreSQL service for these tests; CI was not triggered from this session.
- Django deployment checks no longer flag the weak secret or missing HSTS duration. The includeSubDomains/preload advisories remain intentionally open pending HTTPS verification.
- No real messages or payments were submitted during this repair task.

## Production work still required

Follow deploy/README.md before deploying. Preserve an external media copy before pulling the Git untracking change, since Git can remove previously tracked server media during that pull. In particular:

1. Back up and verify recovery; review production environment variables, rotate exposed provider/database secrets, and review historical Git data exposure.
2. Apply migrations and collectstatic on the actual server, then restart the existing application service.
3. Install and enable the email worker/timer. With the default EMAIL_OUTBOX_EAGER=false, notifications and invoices wait for this worker; verification codes remain immediate.
4. Merge the private-media Nginx rule so direct static serving cannot bypass Django permissions.
5. Assign employee dashboard/model permissions deliberately.
6. Verify actual mail delivery and DKIM from message headers/provider settings before tightening DMARC. Do not enable HSTS preload/subdomains without confirming HTTPS coverage.
7. Run PostgreSQL concurrency checks with a dedicated test role/database and monitor the email queue, errors and backup recovery.

No production deployment, DNS change, provider password rotation, Git history rewrite or external email delivery was performed. Exact server paths and upstream settings must be checked before enabling the supplied service examples.
