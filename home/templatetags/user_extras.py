from django import template

register = template.Library()


@register.filter
def is_provider(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False):
        return True
    try:
        return hasattr(user, "provider_profile")
    except Exception:
        return False
