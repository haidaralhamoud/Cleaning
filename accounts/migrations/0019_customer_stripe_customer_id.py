from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_merge_20260311_1602"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="stripe_customer_id",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]
