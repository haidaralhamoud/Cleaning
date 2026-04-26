from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0038_providerprofile_supported_services"),
    ]

    operations = [
        migrations.AddField(
            model_name="loyaltytier",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="loyalty_tiers/"),
        ),
    ]
