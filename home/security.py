from django.core.exceptions import PermissionDenied


class DashboardPermissionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if not request.path_info.startswith("/dashboard/") or not request.user.is_authenticated:
            return None
        user = request.user
        if not user.is_active or not user.is_staff:
            raise PermissionDenied
        if user.is_superuser or user.has_perm("accounts.access_dashboard"):
            return None
        actions = {
            "dashboard_model_list": "view", "dashboard_model_view": "view",
            "dashboard_model_create": "add", "dashboard_model_edit": "change",
            "dashboard_model_delete": "delete",
        }
        if match and match.url_name == "dashboard_contacts_redirect" and user.has_perm("home.view_contact"):
            return None
        action = actions.get(match.url_name if match else "")
        if action and view_kwargs.get("model"):
            from home.dashboard import get_item_by_slug
            item = get_item_by_slug(view_kwargs["model"])
            if item and user.has_perm(f"{item.model._meta.app_label}.{action}_{item.model._meta.model_name}"):
                return None
        if match and match.url_name == "dashboard_change_password":
            return None
        raise PermissionDenied


def client_ip(request):
    from ipaddress import ip_address
    from django.conf import settings

    peer = request.META.get("REMOTE_ADDR", "")
    trusted = set(getattr(settings, "TRUSTED_PROXY_IPS", ["127.0.0.1", "::1"]))
    if peer in trusted:
        chain = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        for entry in reversed(chain):
            candidate = entry.strip()
            try:
                candidate = str(ip_address(candidate))
            except ValueError:
                continue
            if candidate not in trusted:
                return candidate
    try:
        return str(ip_address(peer))
    except ValueError:
        return None
