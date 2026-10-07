"""Reject unknown and server-controlled input fields explicitly."""

from rest_framework import serializers


class StrictInputMixin:
    def to_internal_value(self, data):
        if isinstance(data, dict):
            writable = {
                name for name, field in self.fields.items() if not field.read_only
            }
            unexpected = set(data) - writable
            if unexpected:
                raise serializers.ValidationError(
                    {name: "Campo não permitido." for name in sorted(unexpected)}
                )
        return super().to_internal_value(data)


class StrictSerializer(StrictInputMixin, serializers.Serializer):
    pass


class StrictModelSerializer(StrictInputMixin, serializers.ModelSerializer):
    pass
