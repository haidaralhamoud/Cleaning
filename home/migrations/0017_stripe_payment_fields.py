from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0016_booking_conflict_override"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="privatebooking",
            name="card_number",
        ),
        migrations.RemoveField(
            model_name="privatebooking",
            name="card_expiry",
        ),
        migrations.RemoveField(
            model_name="privatebooking",
            name="card_cvv",
        ),
        migrations.RemoveField(
            model_name="privatebooking",
            name="card_name",
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="payment_intent_id",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="payment_status",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="payment_brand",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="payment_last4",
            field=models.CharField(blank=True, max_length=4, null=True),
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="payment_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="payment_currency",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]
