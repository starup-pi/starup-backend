"""Startup public output contains no user or document fields."""

from rest_framework import serializers

from starup_backend.common.serializers import StrictSerializer


class PublicStartupSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    website = serializers.CharField()
    category = serializers.CharField()
    average_rating = serializers.FloatField(allow_null=True)
    review_count = serializers.IntegerField()


class StartupUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(
        max_length=300, required=False, allow_blank=True
    )
    website = serializers.URLField(required=False, allow_blank=True)
