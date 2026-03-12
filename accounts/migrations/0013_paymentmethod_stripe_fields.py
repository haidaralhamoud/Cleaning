from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_invoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="stripe_payment_method_id",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="exp_month",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="exp_year",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
