import re

from django import template
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import mark_safe

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


SECTION_PATTERNS = [
    ("What's included", re.compile(r"what[^A-Za-z0-9_]?s included", re.IGNORECASE)),
    ("Why it matters", re.compile(r"why it matters", re.IGNORECASE)),
]


@register.filter
def format_service_available_description(value):
    text = (value or "").strip()
    if not text:
        return ""

    sections = []
    matches = []
    for title, pattern in SECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            matches.append((match.start(), match.end(), title))

    if matches:
        matches.sort(key=lambda item: item[0])
        for index, (start, end, title) in enumerate(matches):
            next_start = matches[index + 1][0] if index + 1 < len(matches) else len(text)
            body = text[end:next_start].strip(" :\n\r\t-")
            sections.append((title, body))
    else:
        sections.append(("", text))

    html_parts = []
    for title, body in sections:
        escaped_body = conditional_escape(body).replace("\n", "<br>")
        if title:
            html_parts.append(
                format_html(
                    '<div class="service-description-section"><strong>{}</strong><p>{}</p></div>',
                    title,
                    mark_safe(escaped_body),
                )
            )
        else:
            html_parts.append(
                format_html(
                    '<div class="service-description-section"><p>{}</p></div>',
                    mark_safe(escaped_body),
                )
            )

    return format_html_join("", "{}", ((part,) for part in html_parts))


@register.filter
def lines_to_green_bullets(value):
    text = (value or "").strip()
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    return format_html(
        '<ul class="green-bullet-list">{}</ul>',
        format_html_join(
            "",
            "<li>{}</li>",
            ((line,) for line in lines),
        ),
    )
