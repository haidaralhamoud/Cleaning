from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0039_loyaltytier_image"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="customer_number",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="invoice",
            name="delivery_terms",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="is_locked",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="invoice",
            name="late_interest_rate",
            field=models.DecimalField(decimal_places=2, default=Decimal("12.00"), max_digits=5),
        ),
        migrations.AddField(
            model_name="invoice",
            name="long_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_reference",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_terms",
            field=models.CharField(blank=True, default="10 days", max_length=60),
        ),
        migrations.AddField(
            model_name="invoice",
            name="rounding",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10),
        ),
        migrations.AddField(
            model_name="invoice",
            name="sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="sent_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_invoices", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("SENT", "Sent"),
                    ("PAID", "Paid"),
                    ("PENDING", "Pending"),
                    ("FAILED", "Failed"),
                    ("REFUNDED", "Refunded"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="DRAFT",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="InvoiceLineItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_order", models.PositiveIntegerField(default=0)),
                ("description", models.CharField(max_length=255)),
                ("service_time", models.CharField(blank=True, max_length=120)),
                ("quantity", models.DecimalField(decimal_places=2, default=Decimal("1.00"), max_digits=10)),
                ("unit_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("rot_rut_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("vat_percent", models.DecimalField(decimal_places=2, default=Decimal("25.00"), max_digits=5)),
                ("is_service_fee", models.BooleanField(default=False)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="line_items", to="accounts.invoice")),
            ],
            options={
                "ordering": ["line_order", "id"],
            },
        ),
    ]
