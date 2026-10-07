"""Public demand projection and strict write input."""

from rest_framework import serializers

from starup_backend.common.serializers import StrictSerializer

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


class DemandQuerySerializer(StrictSerializer):
    mine = serializers.BooleanField(default=False)
    visibility = serializers.ChoiceField(choices=["PUBLIC", "PRIVATE"], required=False)
    status = serializers.ChoiceField(
        choices=["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"], required=False
    )
    page = serializers.IntegerField(min_value=1, required=False)


class DemandSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
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
