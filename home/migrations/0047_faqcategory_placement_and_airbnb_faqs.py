from django.db import migrations, models


AIRBNB_FAQS = [
    (
        "What areas do you cover?",
        "Stockholm, Solna, Järfälla and surrounding areas.",
    ),
    (
        "Can you handle multiple properties?",
        "Yes. Our service scales from one property to a complete portfolio.",
    ),
    (
        "Do you provide linen and toiletries?",
        "Yes, linen, toiletries and restocking can all be included.",
    ),
    (
        "How do payments work?",
        "We prepare a solution based on your property and selected services, then confirm the pricing with you before work begins.",
    ),
]


def create_airbnb_faqs(apps, schema_editor):
    FAQCategory = apps.get_model("home", "FAQCategory")
    FAQItem = apps.get_model("home", "FAQItem")

    category, _ = FAQCategory.objects.get_or_create(
        title="Airbnb Management",
        placement="airbnb",
        defaults={"icon": "", "order": 0, "is_active": True},
    )

    for order, (question, answer) in enumerate(AIRBNB_FAQS, start=1):
        FAQItem.objects.get_or_create(
            category=category,
            question=question,
            defaults={"answer": answer, "order": order, "is_active": True},
        )


def remove_airbnb_faqs(apps, schema_editor):
    FAQCategory = apps.get_model("home", "FAQCategory")
    FAQCategory.objects.filter(
        title="Airbnb Management",
        placement="airbnb",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0046_airbnbmanagementrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="faqcategory",
            name="placement",
            field=models.CharField(
                choices=[
                    ("general", "General FAQ page"),
                    ("airbnb", "Airbnb Management page"),
                ],
                default="general",
                help_text="Choose where this FAQ category should appear.",
                max_length=20,
            ),
        ),
        migrations.RunPython(create_airbnb_faqs, remove_airbnb_faqs),
    ]
