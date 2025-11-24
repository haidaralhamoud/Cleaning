from django.db import models

INQUIRY_CHOICES = [
    ('general', 'General Inquiry'),
    ('support', 'Support'),
    ('pricing', 'Pricing'),
    ('booking', 'Booking'),
]

class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    country_code = models.CharField(max_length=10)
    phone = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()

    inquiry_type = models.CharField(max_length=50, choices=INQUIRY_CHOICES)
    preferred_method = models.CharField(max_length=50, default='email')

    file = models.FileField(upload_to='contact_files/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"


class Job(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    job_type = models.CharField(max_length=50, default="Full Time")
    image = models.ImageField(upload_to="jobs/", blank=True, null=True)
    is_active = models.BooleanField(default=True)   # 🔥 مهمّة جداً

    def __str__(self):
        return self.title
    
class Application(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50)
    job = models.ForeignKey("Job", on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(blank=True, null=True)
    cv = models.FileField(upload_to="applications/cv/", null=True, blank=True)

    # 🔥 طلبات بدون وظيفة
    area = models.CharField(max_length=200, null=True, blank=True)
    availability = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name
