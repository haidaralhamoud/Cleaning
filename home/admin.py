from django.contrib import admin
from .models import Contact , Job , Application , BusinessService,BusinessBooking ,BusinessBundle,BusinessAddon
# # Register your models here.
admin.site.register(Contact)
# admin.site.register(Service)
admin.site.register(Job)
admin.site.register(BusinessService)
admin.site.register(BusinessBooking)
admin.site.register(BusinessAddon)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "phone", "job", "application_type", "created_at"]
    list_filter = ["job", "created_at"]

    def application_type(self, obj):
        if obj.job:
            return "Job Application"
        return "Open Application"

    application_type.short_description = "Type"


@admin.register(BusinessBundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("title", "discount")  
    prepopulated_fields = {"slug": ("title",)}