import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create private PostgreSQL and media backups; requires pg_dump."

    def add_arguments(self, parser):
        parser.add_argument("--destination", required=True)

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError("This command is for PostgreSQL; tests use an isolated SQLite database.")
        executable = shutil.which("pg_dump")
        if not executable:
            raise CommandError("Install the matching PostgreSQL client tools (pg_dump).")
        root = Path(options["destination"]).expanduser().resolve()
        media = Path(settings.MEDIA_ROOT).resolve()
        if root == media or root.is_relative_to(media) or root.is_relative_to(Path(settings.STATIC_ROOT).resolve()):
            raise CommandError("The destination must be outside publicly served media and static directories.")
        target = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target.mkdir(parents=True, mode=0o700, exist_ok=False)
        environment = os.environ.copy()
        environment["PGPASSWORD"] = db.get("PASSWORD", "")
        command = [executable, "--format=custom", "--no-owner", "--host", db.get("HOST") or "localhost",
                   "--port", str(db.get("PORT") or "5432"), "--username", db["USER"],
                   "--file", str(target / "database.dump"), db["NAME"]]
        try:
            subprocess.run(command, env=environment, check=True, capture_output=True)
            if media.exists():
                with tarfile.open(target / "media.tar.gz", "w:gz") as archive:
                    archive.add(media, arcname="media", recursive=True)
            for artifact in target.iterdir():
                artifact.chmod(0o600)
        except Exception as exc:
            raise CommandError(f"Backup incomplete: {type(exc).__name__}. Inspect the private destination; no source data was removed.") from None
        self.stdout.write(f"Backup created in {target}. Verify by restoring into an isolated database and media directory.")
