from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0021_alter_customerlocation_country"),
    ]

    operations = [
        migrations.AddField(
            model_name="reward",
            name="discount_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
