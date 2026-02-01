from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_servicereview_highlights_providerprofile_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan_name", models.CharField(default="Weekly Cleaning", max_length=120)),
                ("duration_hours", models.PositiveSmallIntegerField(default=2)),
                ("price_per_session", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("frequency", models.CharField(default="weekly", max_length=20)),
                ("next_billing_date", models.DateField(blank=True, null=True)),
                ("next_service_date", models.DateField(blank=True, null=True)),
                ("skip_next_service", models.BooleanField(default=False)),
                ("is_paused", models.BooleanField(default=False)),
                ("pause_until", models.DateField(blank=True, null=True)),
                ("resume_on", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("cancelled", "Cancelled")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("cancellation_reason", models.CharField(blank=True, max_length=255)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription",
                        to="accounts.customer",
                    ),
                ),
                (
                    "payment_method",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="subscriptions",
                        to="accounts.paymentmethod",
                    ),
                ),
            ],
        ),
    ]
