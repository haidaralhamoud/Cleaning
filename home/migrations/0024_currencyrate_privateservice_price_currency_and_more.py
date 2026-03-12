from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0023_privatebooking_payment_intent_unique_and_webhookevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="privateaddon",
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
        migrations.AddField(
            model_name="privateservice",
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
        migrations.CreateModel(
            name="CurrencyRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_currency", models.CharField(choices=[("SEK", "Swedish Krona (SEK)"), ("USD", "US Dollar (USD)"), ("EUR", "Euro (EUR)")], max_length=3, unique=True)),
                ("target_currency", models.CharField(choices=[("SEK", "Swedish Krona (SEK)"), ("USD", "US Dollar (USD)"), ("EUR", "Euro (EUR)")], default="SEK", max_length=3)),
                ("exchange_rate", models.DecimalField(decimal_places=6, default=1, help_text="How many target currency units equal 1 source currency unit.", max_digits=12)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["source_currency"]},
        ),
    ]
