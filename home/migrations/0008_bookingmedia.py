from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0007_rotsetting"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingMedia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "booking_type",
                    models.CharField(
                        choices=[("private", "Private"), ("business", "Business")],
                        max_length=10,
                    ),
                ),
                ("booking_id", models.PositiveIntegerField()),
                (
                    "phase",
                    models.CharField(
                        choices=[("before", "Before"), ("during", "During"), ("after", "After"), ("issue", "Issue")],
                        default="before",
                        max_length=10,
                    ),
                ),
                ("file", models.ImageField(upload_to="booking_media/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="booking_media",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
