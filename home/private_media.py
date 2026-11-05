from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe
from PIL import Image, UnidentifiedImageError


@login_required
@require_safe
def private_media(request, path):
    from accounts.models import ChatMessage, Incident, BookingRequestFixAttachment
    from home.models import Application, Contact, EmailRequest, BookingMedia, PrivateBooking, BusinessBooking

    if ".." in Path(path).parts or path.startswith(("/", "\\")):
        raise Http404
    routes = {
        "contact_files": (Contact, "file"), "applications": (Application, "cv"),
        "email_attachments": (EmailRequest, "attachment"), "incidents": (Incident, "evidence"),
        "chat_files": (ChatMessage, "file"), "request_fixes": (BookingRequestFixAttachment, "file"),
        "booking_media": (BookingMedia, "file"),
    }
    config = routes.get(path.split("/", 1)[0])
    if not config:
        raise Http404
    model, field = config
    obj = get_object_or_404(model, **{field: path})
    user = request.user
    allowed = user.is_active and user.is_staff and (
        user.is_superuser or user.has_perm("accounts.access_dashboard")
        or user.has_perm(f"{model._meta.app_label}.view_{model._meta.model_name}"))
    if isinstance(obj, ChatMessage):
        allowed = allowed or user.pk in (obj.thread.customer_id, obj.thread.provider_id)
    elif isinstance(obj, Incident):
        allowed = allowed or obj.customer_id == user.pk
    elif isinstance(obj, BookingRequestFixAttachment):
        allowed = allowed or obj.request_fix.customer_id == user.pk
    elif isinstance(obj, BookingMedia):
        booking_model = PrivateBooking if obj.booking_type == "private" else BusinessBooking
        allowed = allowed or booking_model.objects.filter(pk=obj.booking_id, user=user).exists()
        allowed = allowed or booking_model.objects.filter(pk=obj.booking_id, provider=user).exists()
    if not allowed:
        raise Http404
    file = getattr(obj, field)
    try:
        stream = file.open("rb")
    except (OSError, SuspiciousFileOperation) as exc:
        raise Http404 from exc
    content_type = "application/octet-stream"
    attachment = True
    try:
        image = Image.open(stream)
        mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}.get(image.format)
        if mime:
            content_type, attachment = mime, False
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        pass
    finally:
        stream.seek(0)
    response = FileResponse(stream, as_attachment=attachment, filename=Path(file.name).name, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
