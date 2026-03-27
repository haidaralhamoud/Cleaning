from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0026_contact_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="privatebooking",
            name="use_rot",
            field=models.BooleanField(default=True),
        ),
    ]
