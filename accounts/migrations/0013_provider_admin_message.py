from django.db import migrations, models
import django.db.models.deletion
import django.conf


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_invoice"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderAdminMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("body", models.TextField(blank=True)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="provider_admin_messages_created", to=django.conf.settings.AUTH_USER_MODEL)),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="admin_messages", to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
