from django.db import models


class ElectricalService(models.Model):
    title = models.CharField(max_length=120)
    short_description = models.TextField()
    bullet_points = models.TextField(blank=True, default="")
    icon = models.ImageField(upload_to='electricity/services/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class ConsultationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DONE = "done", "Done"
        CANCELED = "canceled", "Canceled"

    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40)
    email = models.EmailField(blank=True)
    service = models.ForeignKey(
        ElectricalService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultation_requests",
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"
