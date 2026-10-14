from django.db import migrations, models


def create_default_home_hero_price(apps, schema_editor):
    HomeHeroPrice = apps.get_model("home", "HomeHeroPrice")
    HomeHeroPrice.objects.get_or_create(
        pk=1,
        defaults={
            "label": "Home cleaning from",
            "hourly_price": 240,
            "currency": "SEK",
            "unit_label": "/ hour",
            "note": "after RUT deduction",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0047_faqcategory_placement_and_airbnb_faqs"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeHeroPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(default="Home cleaning from", max_length=100)),
                ("hourly_price", models.DecimalField(decimal_places=2, default=240, max_digits=10)),
                ("currency", models.CharField(choices=[("SEK", "Swedish Krona (SEK)"), ("USD", "US Dollar (USD)"), ("EUR", "Euro (EUR)")], default="SEK", max_length=3)),
                ("unit_label", models.CharField(default="/ hour", max_length=40)),
                ("note", models.CharField(default="after RUT deduction", max_length=120)),
            ],
            options={
                "verbose_name": "Home hero price",
                "verbose_name_plural": "Home hero price",
            },
        ),
        migrations.RunPython(create_default_home_hero_price, migrations.RunPython.noop),
    ]
