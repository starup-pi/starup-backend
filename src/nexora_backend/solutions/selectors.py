"""Proposals are private to their startup and the demand owner."""

from django.db.models import Q

from .models import Solution


def participant_solutions(user):
    if not user.is_authenticated:
        return Solution.objects.none()
    return Solution.objects.filter(
        Q(startup__user_id=user.pk) | Q(demand__client__user_id=user.pk)
    ).order_by("-created_at", "id")


def solution_projection(user):
    return participant_solutions(user).values(
        "id",
        "demand_id",
        "startup_id",
        "startup__name",
        "proposal",
        "delivery",
        "status",
        "created_at",
        "updated_at",
    )
