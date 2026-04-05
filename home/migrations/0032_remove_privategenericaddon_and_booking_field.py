from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0031_privategenericaddon_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="privatebooking",
            name="generic_addons_selected",
        ),
        migrations.DeleteModel(
            name="PrivateGenericAddon",
        ),
    ]
