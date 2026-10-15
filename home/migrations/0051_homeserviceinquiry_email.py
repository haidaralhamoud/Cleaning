from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0050_airbnbmanagementrequest_name_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="homeserviceinquiry",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
    ]
