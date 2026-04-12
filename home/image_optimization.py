from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


def optimize_uploaded_image_fields(instance, field_names, update_fields=None, quality=82):
    if update_fields is not None:
        allowed_fields = set(update_fields)
        field_names = [field_name for field_name in field_names if field_name in allowed_fields]
    if not field_names:
        return

    for field_name in field_names:
        field_file = getattr(instance, field_name, None)
        if not field_file or getattr(field_file, "_committed", True):
            continue
        _optimize_field_file(field_file, quality=quality)


def _optimize_field_file(field_file, quality=82):
    original_name = field_file.name or ""
    original_suffix = Path(original_name).suffix.lower()
    output = BytesIO()

    try:
        field_file.open("rb")
        image = Image.open(field_file)
        image = ImageOps.exif_transpose(image)
        image.load()
    except (FileNotFoundError, UnidentifiedImageError, OSError):
        return
    finally:
        try:
            field_file.close()
        except Exception:
            pass

    image_format = (image.format or "").upper()
    if image_format in {"JPG", "JPEG"} or original_suffix in {".jpg", ".jpeg"}:
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(
            output,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
        )
    elif image_format == "WEBP" or original_suffix == ".webp":
        if image.mode not in {"RGB", "RGBA", "L"}:
            image = image.convert("RGBA" if "A" in image.mode else "RGB")
        image.save(
            output,
            format="WEBP",
            quality=quality,
            method=6,
        )
    elif image_format == "PNG" or original_suffix == ".png":
        image.save(
            output,
            format="PNG",
            optimize=True,
        )
    else:
        return

    output.seek(0)
    field_file.save(original_name, ContentFile(output.read()), save=False)
