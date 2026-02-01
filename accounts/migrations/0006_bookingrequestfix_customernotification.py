from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_subscription"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingRequestFix",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("booking_type", models.CharField(choices=[("private", "Private"), ("business", "Business")], max_length=10)),
                ("booking_id", models.PositiveIntegerField()),
                ("message", models.TextField()),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("IN_REVIEW", "In Review"), ("RESOLVED", "Resolved")], default="OPEN", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="CustomerNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("body", models.TextField(blank=True)),
                ("notification_type", models.CharField(choices=[("request_fix", "Request Fix"), ("approve_work", "Approve Work"), ("general", "General")], default="general", max_length=20)),
                ("booking_type", models.CharField(blank=True, max_length=10)),
                ("booking_id", models.PositiveIntegerField(blank=True, null=True)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("request_fix", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="accounts.bookingrequestfix")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="BookingRequestFixAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.ImageField(upload_to="request_fixes/")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("request_fix", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="accounts.bookingrequestfix")),
            ],
        ),
    ]
