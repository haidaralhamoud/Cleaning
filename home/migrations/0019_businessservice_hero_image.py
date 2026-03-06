from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0018_businessservicecard"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessservice",
            name="hero_image",
            field=models.ImageField(blank=True, null=True, upload_to="business_services/hero/"),
        ),
    ]

