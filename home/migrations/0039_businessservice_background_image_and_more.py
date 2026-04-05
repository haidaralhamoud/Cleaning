from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0038_feedbackrequest_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessservice",
            name="background_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="business_services/background/",
                verbose_name="Image for background",
            ),
        ),
        migrations.AddField(
            model_name="privateservice",
            name="background_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="private/background/",
                verbose_name="Image for background",
            ),
        ),
    ]
