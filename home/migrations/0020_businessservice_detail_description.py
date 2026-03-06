from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0019_businessservice_hero_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessservice",
            name="detail_description",
            field=models.TextField(blank=True, null=True),
        ),
    ]

