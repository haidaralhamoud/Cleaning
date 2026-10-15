from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0049_homeserviceinquiry"),
    ]

    operations = [
        migrations.AddField(
            model_name="airbnbmanagementrequest",
            name="email",
            field=models.EmailField(default="", max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="airbnbmanagementrequest",
            name="name",
            field=models.CharField(default="", max_length=150),
            preserve_default=False,
        ),
    ]
