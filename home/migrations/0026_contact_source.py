from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0025_alter_businessbooking_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="source",
            field=models.CharField(
                choices=[("private", "Private"), ("business", "Business")],
                default="private",
                max_length=20,
            ),
        ),
    ]
