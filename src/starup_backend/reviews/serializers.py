"""Reject booleans, strings and fractional ratings."""

from rest_framework import serializers

from starup_backend.common.serializers import StrictSerializer


class StrictRatingField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class ReviewCreateSerializer(StrictSerializer):
    solution_id = serializers.UUIDField()
    rating = StrictRatingField(min_value=1, max_value=5)


class ReviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    solution_id = serializers.UUIDField()
    rating = serializers.IntegerField()
    created_at = serializers.DateTimeField()
