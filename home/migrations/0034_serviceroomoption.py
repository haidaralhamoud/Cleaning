from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0033_privateaddon_service_nullable_for_all_services"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceRoomOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("short_label", models.CharField(help_text="Short badge like BR, KT, BT", max_length=10)),
                ("title", models.CharField(max_length=120)),
                ("subtitle", models.CharField(blank=True, default="Per room setup", max_length=150)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("service", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="room_options", to="home.privateservice")),
            ],
            options={
                "ordering": ["display_order", "title"],
            },
        ),
    ]
