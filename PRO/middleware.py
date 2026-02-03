from django.http import HttpResponseForbidden
from accounts.models import UserAccessProfile


class AdminSiteAccessGuard:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info or ""
        if path.startswith("/electrical-admin/"):
            if request.user.is_authenticated:
                profile = getattr(request.user, "access_profile", None)
                if profile is None:
                    profile = UserAccessProfile.objects.create(user=request.user)
                    if request.user.is_superuser:
                        profile.role = "global_super"
                        profile.site = "main"
                        profile.save()
                role = getattr(profile, "role", "") if profile else ""
                site = getattr(profile, "site", "main") if profile else "main"
                if role != "global_super" and site != "electrical":
                    return HttpResponseForbidden("Forbidden")
        elif path.startswith("/admin/"):
            if request.user.is_authenticated:
                profile = getattr(request.user, "access_profile", None)
                if profile is None:
                    profile = UserAccessProfile.objects.create(user=request.user)
                    if request.user.is_superuser:
                        profile.role = "global_super"
                        profile.site = "main"
                        profile.save()
                role = getattr(profile, "role", "") if profile else ""
                site = getattr(profile, "site", "main") if profile else "main"
                if role != "global_super" and site != "main":
                    return HttpResponseForbidden("Forbidden")
        return self.get_response(request)
