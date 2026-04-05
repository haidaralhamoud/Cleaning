from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0032_remove_privategenericaddon_and_booking_field"),
    ]

    operations = [
        migrations.AlterField(
            model_name="privateaddon",
            name="service",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="addons_list",
                to="home.privateservice",
            ),
        ),
    ]
