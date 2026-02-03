from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="electricalservice",
            name="bullet_points",
            field=models.TextField(blank=True, default=""),
        ),
    ]
