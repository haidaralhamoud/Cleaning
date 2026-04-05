from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0037_serviceroomoption_price_currency"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedbackrequest",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
