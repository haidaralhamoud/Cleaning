from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0048_homeheroprice"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeServiceInquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("service", models.CharField(max_length=100)),
                ("address", models.CharField(max_length=255)),
                ("phone", models.CharField(max_length=50)),
                ("preferred_date", models.DateField(blank=True, null=True)),
                ("preferred_time", models.TimeField(blank=True, null=True)),
                ("message", models.TextField(blank=True)),
                ("contacted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Home service inquiry",
                "verbose_name_plural": "Home service inquiries",
                "ordering": ["-created_at"],
            },
        ),
    ]
