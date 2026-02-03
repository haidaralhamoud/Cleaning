from django.contrib.admin import AdminSite


class ElectricityAdminSite(AdminSite):
    site_header = "Electrical & Smart Home Admin"
    site_title = "Electrical Admin"
    index_title = "Electrical Operations"

    def has_permission(self, request):
        user = request.user
        if not user.is_authenticated:
            return False
        profile = getattr(user, "access_profile", None)
        if profile is None:
            return False
        if profile.role == "global_super":
            return True
        if profile.site != "electrical":
            return False
        return profile.role in {"electrical_super", "electrical_admin"}


electricity_admin_site = ElectricityAdminSite(name="electricity_admin")
