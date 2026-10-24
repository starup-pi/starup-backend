"""Verified raster uploads and permission-scoped image delivery."""

import warnings
from contextlib import contextmanager
from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import permissions, serializers, views
from rest_framework.exceptions import NotFound

from .models import DemandImage
from .selectors import visible_demands

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 4
MAX_IMAGE_PIXELS = 20_000_000


def prepare_image(upload):
    """Decode trusted raster formats and produce a fresh, metadata-free image."""
    if upload.size > MAX_IMAGE_BYTES:
        raise serializers.ValidationError("Cada imagem deve ter no máximo 5 MB.")
    upload.seek(0)
    data = upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise serializers.ValidationError("Cada imagem deve ter no máximo 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                    raise ValueError("unsupported raster format")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValueError("image dimensions exceed the decoding limit")
                source.verify()
            with Image.open(BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((2560, 2560))
                mode = (
                    "RGBA"
                    if "A" in oriented.getbands() or "transparency" in oriented.info
                    else "RGB"
                )
                converted = oriented.convert(mode)
                clean = Image.new(mode, converted.size)
                clean.paste(converted)
                output = BytesIO()
                image_format = "PNG" if mode == "RGBA" else "JPEG"
                clean.save(output, format=image_format, quality=85, optimize=True)
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise serializers.ValidationError(
            "Envie uma imagem JPEG, PNG, WebP ou GIF válida, com até 20 megapixels."
        ) from exc
    encoded = output.getvalue()
    if len(encoded) > MAX_IMAGE_BYTES:
        raise serializers.ValidationError("A imagem processada excede 5 MB.")
    extension = "png" if image_format == "PNG" else "jpg"
    result = ContentFile(encoded, name=f"{uuid4().hex}.{extension}")
    result.content_type = "image/png" if extension == "png" else "image/jpeg"
    return result


@contextmanager
def image_write_transaction(has_uploads):
    """Compensate storage writes if the database operation or commit fails.

    Uploads require the outermost transaction, since storage has no database
    rollback hook. Durable atomic prevents an enclosing transaction from later
    rolling back committed references while leaving files behind.
    """
    written = []
    try:
        with transaction.atomic(durable=has_uploads):
            yield written
    except BaseException:
        for storage, name in written:
            storage.delete(name)
        raise


def save_images(*, demand, images, written, offset=0):
    for index, content in enumerate(images, start=offset):
        image = DemandImage(
            demand=demand, ordering=index, content_type=content.content_type
        )
        image.image.save(content.name, content, save=False)
        written.append((image.image.storage, image.image.name))
        image.save()


def remove_images(queryset):
    """Delete references now, and stored files only after successful commit."""
    files = [(row.image.storage, row.image.name) for row in queryset]
    queryset.delete()
    for storage, name in files:
        transaction.on_commit(
            lambda storage=storage, name=name: storage.delete(name), robust=True
        )


class DemandImageView(views.APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={
            (200, "image/jpeg"): OpenApiTypes.BINARY,
            (200, "image/png"): OpenApiTypes.BINARY,
        }
    )
    def get(self, request, image_id):
        try:
            image = DemandImage.objects.filter(
                demand_id__in=visible_demands(request.user).values("id")
            ).get(pk=image_id)
            source = image.image.open("rb")
        except (DemandImage.DoesNotExist, FileNotFoundError) as exc:
            raise NotFound() from exc
        response = FileResponse(source, content_type=image.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
