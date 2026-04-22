from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0041_alter_availablezipcode_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatebooking",
            name="appointment_start_time",
            field=models.TimeField(blank=True, null=True),
        ),
    ]
