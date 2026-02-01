from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('home', '0005_bookingformdocument'),
    ]

    operations = [
        migrations.AddField(
            model_name='privateaddon',
            name='questions',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
