from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0014_alter_privateaddon_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatebooking",
            name="is_urgent",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="businessbooking",
            name="is_urgent",
            field=models.BooleanField(default=False),
        ),
    ]
