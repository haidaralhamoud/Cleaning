from django.conf import settings
from django.db import migrations, models
from django.db.models import F


def mark_existing_feedback_as_approved(apps, schema_editor):
    FeedbackRequest = apps.get_model("home", "FeedbackRequest")
    FeedbackRequest.objects.filter(is_approved=False).update(
        is_approved=True,
        approved_at=F("created_at"),
    )


def unmark_existing_feedback_approval(apps, schema_editor):
    FeedbackRequest = apps.get_model("home", "FeedbackRequest")
    FeedbackRequest.objects.update(is_approved=False)


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0043_privatemaincategory_display_order"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="feedbackrequest",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feedbackrequest",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="approved_feedback_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="feedbackrequest",
            name="is_approved",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(mark_existing_feedback_as_approved, unmark_existing_feedback_approval),
    ]
