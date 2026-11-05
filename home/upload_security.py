from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.core.files.uploadhandler import FileUploadHandler
from django.http import HttpResponseBadRequest
from PIL import Image, UnidentifiedImageError


ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png", ".webp", ".gif"}


def validate_attachment(upload):
    if not upload:
        return
    limit = getattr(settings, "MAX_UPLOAD_SIZE", 10 * 1024 * 1024)
    if upload.size > limit:
        raise ValidationError("Each file must be at most 10 MB.")
    extension = Path(upload.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Allowed files: PDF, DOC, DOCX, TXT, JPG, PNG, WEBP and GIF.")
    position = upload.tell()
    try:
        upload.seek(0)
        prefix = upload.read(512)
        upload.seek(0)
        if extension in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            with Image.open(upload) as image:
                expected = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".gif": "GIF"}
                if image.format != expected[extension] or image.width * image.height > 25_000_000:
                    raise ValidationError("Invalid image format or dimensions.")
                image.verify()
        elif extension == ".pdf" and not prefix.startswith(b"%PDF-"):
            raise ValidationError("The file is not a valid PDF.")
        elif extension == ".doc" and not prefix.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
            raise ValidationError("The file is not a valid Word document.")
        elif extension == ".docx":
            with ZipFile(upload) as archive:
                if "word/document.xml" not in archive.namelist() or sum(i.file_size for i in archive.infolist()) > 30 * 1024 * 1024:
                    raise ValidationError("Invalid or oversized Word document.")
        elif extension == ".txt":
            content = upload.read(limit + 1).decode("utf-8")
            if "\x00" in content or any(tag in content.lower() for tag in ("<html", "<script", "<!doctype", "<svg")):
                raise ValidationError("Only plain UTF-8 text is allowed.")
    except (OSError, ValueError, UnicodeError, BadZipFile, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValidationError("The attachment is damaged or its contents do not match its type.") from exc
    finally:
        upload.seek(position)


class UploadSizeLimitHandler(FileUploadHandler):
    """Limit the entire upload stream before memory or disk handlers store it."""
    def __init__(self, request=None):
        super().__init__(request)
        self.received = 0

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > getattr(settings, "MAX_UPLOAD_SIZE", 10 * 1024 * 1024):
            raise RequestDataTooBig("Combined attachments must be at most 10 MB.")
        return raw_data

    def file_complete(self, file_size):
        return None


class ValidateUploadsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        try:
            for values in request.FILES.lists():
                for upload in values[1]:
                    validate_attachment(upload)
        except ValidationError as exc:
            return HttpResponseBadRequest(" ".join(exc.messages), content_type="text/plain; charset=utf-8")
