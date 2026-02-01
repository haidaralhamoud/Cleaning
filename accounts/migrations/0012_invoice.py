from django.db import migrations, models
import django.db.models.deletion
import accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_customerpreferences_frequency_custom_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_number", models.CharField(default=accounts.models._invoice_number, max_length=32, unique=True)),
                ("booking_type", models.CharField(blank=True, choices=[("private", "Private"), ("business", "Business")], max_length=10)),
                ("booking_id", models.PositiveIntegerField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("currency", models.CharField(default="USD", max_length=5)),
                ("status", models.CharField(choices=[("PAID", "Paid"), ("PENDING", "Pending"), ("FAILED", "Failed"), ("REFUNDED", "Refunded")], default="PENDING", max_length=10)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invoices", to="accounts.customer")),
                ("payment_method", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invoices", to="accounts.paymentmethod")),
            ],
            options={
                "ordering": ["-issued_at"],
            },
        ),
    ]
