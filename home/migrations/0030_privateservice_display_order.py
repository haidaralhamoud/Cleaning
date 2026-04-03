from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0029_privateaddon_duration_minutes"),
    ]

    operations = [
        migrations.AddField(
            model_name="privateservice",
            name="display_order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
