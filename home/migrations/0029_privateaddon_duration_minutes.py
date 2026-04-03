from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0028_serviceestimate_option_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="privateaddon",
            name="duration_minutes",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Extra time added by this add-on in minutes.",
            ),
        ),
    ]
