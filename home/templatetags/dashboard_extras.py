from django import template

register = template.Library()

@register.filter
def is_dict(value):
    return isinstance(value, dict)

@register.filter
def is_list(value):
    return isinstance(value, (list, tuple))

@register.filter
def attr(obj, name):
    if obj is None or not name:
        return ""
    try:
        return getattr(obj, name)
    except Exception:
        return ""
