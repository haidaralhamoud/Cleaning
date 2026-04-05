from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0034_serviceroomoption"),
    ]

    operations = [
        migrations.AddField(
            model_name="serviceroomoption",
            name="unit_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
