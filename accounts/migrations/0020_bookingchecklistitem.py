from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0024_currencyrate_privateservice_price_currency_and_more"),
        ("accounts", "0019_customer_stripe_customer_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingChecklistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("service_slug", models.CharField(blank=True, max_length=255)),
                ("service_title", models.CharField(blank=True, max_length=255)),
                ("service_order", models.PositiveIntegerField(default=0)),
                ("group_title", models.CharField(blank=True, max_length=255)),
                ("group_order", models.PositiveIntegerField(default=0)),
                ("item_label", models.CharField(max_length=255)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_completed", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking_business", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="checklist_items", to="home.businessbooking")),
                ("booking_private", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="checklist_items", to="home.privatebooking")),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="completed_checklist_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["service_order", "group_order", "sort_order", "id"],
            },
        ),
    ]
