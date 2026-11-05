# Deploying the technical fixes

These changes are local until deployed. Run commands from the directory containing manage.py using the service's virtual environment. Adapt all example paths, service users and proxy addresses to the existing server configuration.

## Before deployment

1. Back up PostgreSQL, media, Nginx and systemd configuration. The new command requires the matching PostgreSQL client tools:

   ```bash
   python manage.py backup_data --destination /var/backups/hembla
   ```

   Keep backups outside HTTP-served directories, restrict access, and use suitable encryption and off-host retention. Verify the dump using pg_restore --list and an actual restore into a separate database. Never restore over production merely to test a backup. Concurrent database and media edits require a maintenance window or filesystem snapshot for a consistent combined backup.

2. Configure POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST and POSTGRES_PORT in the server environment. The hard-coded database password was removed. The local connection now succeeds using environment configuration; that does not verify the production server.
3. Generate a strong DJANGO_SECRET_KEY on the server and protect its .env file:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

   Key rotation invalidates existing sessions and signatures. The weak LOCAL key was rotated; this does not rotate the server's environment automatically.
4. Rotate any database or mailbox passwords that appeared in shared files, using the actual database/mail provider, then update the corresponding environment variables. Provider passwords were not changed by this task.
5. db.json, media, staticfiles and bytecode were removed from the CURRENT Git index; files remain on disk. Old Git history was not rewritten. Review repository access and coordinate any history cleanup with other checkouts.

## Preserve existing media before pulling this change

This commit stops tracking existing media files. A normal Git pull into an older server checkout can DELETE files that used to be tracked, even though the local index cleanup kept local copies. Do not pull this change on a live server before taking and verifying an external media copy.

Use a maintenance window to stop uploads, copy the entire current media directory outside the checkout, deploy, and restore any missing media from that copy before reopening the site. Keep newly uploaded files; do not blindly overwrite them with an older backup. staticfiles can be rebuilt with collectstatic. Never use git clean or a destructive synchronization to deploy user media.

## Install and migrate

```bash
source /path/to/service/venv/bin/activate
pip install -r requirements.txt
python -m pip check
python manage.py preflight_deploy
python manage.py migrate --plan
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

preflight_deploy is read-only. It checks database access, duplicate booking loyalty awards and pending migrations. If duplicate awards exist, review the financial ledger before adding its unique constraint. No migration automatically deletes historical financial entries.

Superusers retain dashboard access. Other staff need the model-specific Django permissions for their tasks, or accounts.access_dashboard for full operations access. Do not grant full dashboard access merely because a service provider has is_staff.

Google OAuth configuration no longer writes to the database during application startup. After setting valid GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, explicitly synchronize it:

```bash
python manage.py sync_google_oauth
```

## REQUIRED: enable outgoing email processing

Notifications and invoices are stored in OutgoingEmail. EMAIL_OUTBOX_EAGER defaults to false: queued messages will wait until the worker runs. Verification codes intentionally use their synchronous verification transport so failures can be reported immediately and expired codes are not delivered hours later.

Edit User, Group, WorkingDirectory and ExecStart in deploy/hembla-email.service to match the existing application service. The worker needs the same environment, virtual environment and PostgreSQL access as Django. The example project directory is /var/www/hembla/Cleaning.

```bash
sudo install -m 644 deploy/hembla-email.service /etc/systemd/system/hembla-email.service
sudo install -m 644 deploy/hembla-email.timer /etc/systemd/system/hembla-email.timer
sudo systemctl daemon-reload
sudo systemctl enable --now hembla-email.timer
sudo systemctl start hembla-email.service
sudo systemctl status hembla-email.timer
sudo journalctl -u hembla-email.service --since today
```

Inspect OutgoingEmail status in Django Admin. Failed submissions retry with increasing delays, up to eight attempts. After fixing the cause, explicitly retry terminal failures:

```bash
python manage.py process_emails --retry-failed --limit 100
```

Do not run this against production as a harmless test: it submits actual due messages. This task did not send messages or process a production queue.

Invoices lock when queued and remain QUEUED until SMTP accepts the message. Only then do they become SENT with sent_at populated. SMTP acceptance does not establish Inbox delivery. A worker locks each job so concurrent workers cannot submit it simultaneously. A rare crash after SMTP acceptance but before database commit can still cause redelivery; SMTP cannot guarantee exactly-once delivery. Retries retain a stable Message-ID.

Delivered payloads are purged after 30 days during worker runs. Monitor terminal failures and queue size, since payloads include private message bodies and attachments. The admin view hides payloads.

## REQUIRED: send private media requests through Django

Django permission checks cannot protect files that Nginx serves directly. Merge deploy/nginx-private-media.conf into the existing HTTPS server and replace its example upstream with the application's actual upstream/socket.

The general public media location must not use ^~ in a way that bypasses the private-file rule. These prefixes must reach Django: contact_files, applications/cv, incidents, chat_files, email_attachments, request_fixes and booking_media. Do not delete or move media during deployment.

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart hembla
```

Check a private attachment using an anonymous window, an unrelated account, and its owner or an authorized employee. Unrelated accounts must not receive it. Documents download with no-store/nosniff; verified raster images can display inline. Format and size validation is not a malware scanner.

## Email DNS, HTTPS and trusted proxies

- SMTP authentication previously succeeded for services and verification; no real delivery was tested. After deployment, send to an explicitly approved test recipient and inspect Authentication-Results, SPF, DKIM, DMARC and provider bounce logs.
- Obtain the actual DKIM selector and record from Hostinger. Guessing common selector names does not prove DKIM is absent.
- DMARC currently has p=none. Do not jump to reject before auditing all senders and alignment; tighten policy based on actual delivery evidence.
- HSTS is enabled for the current host with a one-hour duration. Django's includeSubDomains/preload advisories remain intentionally unresolved until all relevant subdomains and HTTPS deployment are verified. No automatic preload submission occurred.
- TRUSTED_PROXY_IPS must contain only the actual reverse proxy addresses; the default is loopback. The application selects the nearest untrusted address in the forwarded chain instead of trusting a client-supplied leftmost entry.

## Tests and recovery

```bash
python manage.py test --noinput
python manage.py makemigrations --check --dry-run
```

Local tests use SQLite and in-memory email. Test configuration isolates HTTPS redirects and static manifests from production. GitHub Actions was added for clean installation and tests against both SQLite and PostgreSQL. Real row-lock concurrency tests require PostgreSQL and skip on SQLite. CI has not been triggered or deployed by this task.

For isolated PostgreSQL testing, set TEST_DATABASE_ENGINE=postgresql and dedicated POSTGRES_* credentials with permission to create a test database. Never use production credentials for concurrency tests.

Deployment recovery: stop the email timer before reverting application/database changes. Retain the private pre-deployment backup and the matching previous code. Review the migration plan and use an isolated restore to validate recovery before touching production. Do not blindly roll back a database after real emails or payments have been submitted.
