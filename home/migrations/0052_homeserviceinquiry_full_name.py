from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0051_homeserviceinquiry_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="homeserviceinquiry",
            name="full_name",
            field=models.CharField(default="", max_length=200),
        ),
    ]
