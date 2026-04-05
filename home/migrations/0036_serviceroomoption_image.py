from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0035_serviceroomoption_unit_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="serviceroomoption",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="private/room_options/"),
        ),
    ]
