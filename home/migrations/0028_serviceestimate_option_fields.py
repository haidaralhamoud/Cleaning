from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0027_privatebooking_use_rot"),
    ]

    operations = [
        migrations.AddField(
            model_name="serviceestimate",
            name="bedrooms_options",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="serviceestimate",
            name="property_options",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
