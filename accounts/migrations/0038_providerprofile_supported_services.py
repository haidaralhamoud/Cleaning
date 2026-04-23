from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0042_privatebooking_appointment_start_time"),
        ("accounts", "0037_providershift"),
    ]

    operations = [
        migrations.AddField(
            model_name="providerprofile",
            name="supported_services",
            field=models.ManyToManyField(
                blank=True,
                related_name="provider_profiles",
                to="home.privateservice",
            ),
        ),
    ]
