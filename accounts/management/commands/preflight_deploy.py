from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count


class Command(BaseCommand):
    help = "Read-only database deployment checks; never changes records."

    def handle(self, *args, **options):
        from accounts.models import PointsTransaction
        try:
            connection.ensure_connection()
            duplicates = PointsTransaction.objects.filter(reason="BOOKING", booking_id__isnull=False).values(
                "user_id", "booking_type", "booking_id").annotate(total=Count("id")).filter(total__gt=1)
            count = duplicates.count()
            if count:
                raise CommandError(f"Found {count} duplicate loyalty awards. Review the ledger before applying its unique constraint; no records were changed.")
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Database preflight failed: {type(exc).__name__}. Check server connectivity and credentials.") from None
        self.stdout.write(f"Database reachable; no duplicate loyalty awards; {len(plan)} migrations pending.")
