from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0042_privatebooking_appointment_start_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatemaincategory",
            name="display_order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
