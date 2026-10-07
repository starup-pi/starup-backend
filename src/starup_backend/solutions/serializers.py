"""Proposal and delivery bodies stay private to participants."""

from rest_framework import serializers

from starup_backend.common.serializers import StrictSerializer


class SolutionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    demand_id = serializers.UUIDField()
    startup_id = serializers.UUIDField()
    startup_name = serializers.CharField(source="startup__name")
    proposal = serializers.CharField()
    delivery = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SolutionCreateSerializer(StrictSerializer):
    demand_id = serializers.UUIDField()
    proposal = serializers.CharField(max_length=10000)


class SolutionTransitionSerializer(StrictSerializer):
    status = serializers.ChoiceField(
        choices=["ACCEPTED", "REJECTED", "WITHDRAWN", "IN_PROGRESS", "DELIVERED"]
    )
    delivery = serializers.CharField(required=False, max_length=10000)


class StatusEventSerializer(serializers.Serializer):
    previous_status = serializers.CharField()
    new_status = serializers.CharField()
    created_at = serializers.DateTimeField()
