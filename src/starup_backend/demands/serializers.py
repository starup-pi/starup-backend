"""Public demand projection and strict write input."""

import json

from rest_framework import serializers

from starup_backend.common.serializers import StrictSerializer

from .media import MAX_IMAGES, prepare_image
from .models import Category


class DemandWriteSerializer(StrictSerializer):
    title = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=10000)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all()
    )
    visibility = serializers.ChoiceField(
        choices=["PUBLIC", "PRIVATE"], default="PUBLIC"
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=31), max_length=8, required=False
    )
    images = serializers.ListField(
        child=serializers.FileField(),
        max_length=MAX_IMAGES,
        required=False,
        write_only=True,
    )
    keep_image_ids = serializers.ListField(
        child=serializers.UUIDField(),
        max_length=MAX_IMAGES,
        required=False,
        write_only=True,
    )

    def to_internal_value(self, data):
        if hasattr(data, "getlist"):
            values = data.dict()
            for field in ("tags", "images", "keep_image_ids"):
                if field not in data:
                    continue
                items = data.getlist(field)
                if field != "images" and len(items) == 1 and items[0].startswith("["):
                    try:
                        items = json.loads(items[0])
                    except (TypeError, ValueError) as exc:
                        raise serializers.ValidationError(
                            {field: "Informe uma lista válida."}
                        ) from exc
                values[field] = items
            data = values
        return super().to_internal_value(data)

    def validate_tags(self, values):
        tags, seen = [], set()
        for value in values:
            tag = value.strip().lstrip("#").strip().casefold()
            if not tag or len(tag) > 30 or "#" in tag:
                raise serializers.ValidationError(
                    "Use tags de 1 a 30 caracteres, sem # no conteúdo."
                )
            if tag.casefold() not in seen:
                tags.append(tag)
                seen.add(tag.casefold())
        return tags

    def validate_images(self, values):
        return [prepare_image(value) for value in values]

    def validate_keep_image_ids(self, values):
        if not self.partial:
            raise serializers.ValidationError("Disponível apenas ao editar a demanda.")
        if len(values) != len(set(values)):
            raise serializers.ValidationError("Não repita imagens existentes.")
        return values


class DemandQuerySerializer(StrictSerializer):
    mine = serializers.BooleanField(default=False)
    visibility = serializers.ChoiceField(choices=["PUBLIC", "PRIVATE"], required=False)
    status = serializers.ChoiceField(
        choices=["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"], required=False
    )
    page = serializers.IntegerField(min_value=1, required=False)


class DemandImageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    url = serializers.CharField()


class DemandSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    images = DemandImageSerializer(many=True, source="image_items")
    client_id = serializers.UUIDField()
    client_name = serializers.CharField()
    rating = serializers.IntegerField(allow_null=True)
    selected_startup_id = serializers.UUIDField(allow_null=True)
    selected_startup_name = serializers.CharField(allow_null=True)
    category_id = serializers.UUIDField()
    category_name = serializers.CharField(source="category__name")
    status = serializers.CharField()
    visibility = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "slug", "name"]
        read_only_fields = fields
