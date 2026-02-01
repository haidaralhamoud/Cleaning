from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0006_privateaddon_questions"),
    ]

    operations = [
        migrations.CreateModel(
            name="RotSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
