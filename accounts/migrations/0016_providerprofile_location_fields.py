from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_alter_customer_desired_services_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="providerprofile",
            name="area",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="providerprofile",
            name="city",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="providerprofile",
            name="nearby_areas",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="providerprofile",
            name="region",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
