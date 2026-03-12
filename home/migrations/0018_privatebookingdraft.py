from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0017_stripe_payment_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrivateBookingDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_intent_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("payment_status", models.CharField(blank=True, max_length=50, null=True)),
                ("payment_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("payment_currency", models.CharField(blank=True, max_length=10, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("completed", "Completed"), ("expired", "Expired")], default="pending", max_length=20)),
                ("payload", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="private_booking_drafts", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
