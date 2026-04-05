from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0036_serviceroomoption_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="serviceroomoption",
            name="price_currency",
            field=models.CharField(
                choices=[
                    ("SEK", "Swedish Krona (SEK)"),
                    ("USD", "US Dollar (USD)"),
                    ("EUR", "Euro (EUR)"),
                ],
                default="USD",
                max_length=3,
            ),
        ),
    ]
