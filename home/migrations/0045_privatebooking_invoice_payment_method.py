from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0044_feedbackrequest_approval"),
    ]

    operations = [
        migrations.AlterField(
            model_name="privatebooking",
            name="payment_method",
            field=models.CharField(blank=True, choices=[("card", "Credit Card"), ("invoice", "Invoice")], max_length=50, null=True),
        ),
    ]
