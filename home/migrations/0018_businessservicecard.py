from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0017_faqcategory_faqitem"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessServiceCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150)),
                ("body", models.TextField(help_text="One bullet per line")),
                ("order", models.PositiveIntegerField(default=0)),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cards", to="home.businessservice")),
            ],
            options={
                "ordering": ["order"],
            },
        ),
    ]
