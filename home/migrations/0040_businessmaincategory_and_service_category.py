from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0039_businessservice_background_image_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessMainCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(unique=True)),
            ],
            options={
                "ordering": ["title"],
            },
        ),
        migrations.AddField(
            model_name="businessservice",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="services",
                to="home.businessmaincategory",
            ),
        ),
    ]
