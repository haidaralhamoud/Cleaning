from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0015_add_booking_is_urgent"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessbooking",
            name="conflict_override",
            field=models.BooleanField(default=False, help_text="Admin override when a scheduling conflict exists"),
        ),
        migrations.AddField(
            model_name="businessbooking",
            name="conflict_override_note",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="conflict_override",
            field=models.BooleanField(default=False, help_text="Admin override when a scheduling conflict exists"),
        ),
        migrations.AddField(
            model_name="privatebooking",
            name="conflict_override_note",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
