from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0042_invoicelineitem_discount_percent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="currency",
            field=models.CharField(default="SEK", max_length=5),
        ),
    ]
