"""Scope reads before any detail lookup."""

from django.db.models import Q

from .models import Demand


def visible_demands(user):
    condition = Q(
        visibility=Demand.Visibility.PUBLIC,
        client__user__ativo=True,
        client__user__perfil_ativo="EMPRESA_CLIENTE",
    )
    if user.is_authenticated:
        condition |= Q(client__user_id=user.pk)
        condition |= Q(
            solutions__startup__user_id=user.pk,
            solutions__status__in=["ACCEPTED", "IN_PROGRESS", "DELIVERED", "COMPLETED"],
        )
    return Demand.objects.filter(condition).distinct().order_by("-created_at", "id")


def demand_projection(user):
    return visible_demands(user).values(
        "id",
        "title",
        "description",
        "category_id",
        "category__name",
        "status",
        "visibility",
        "created_at",
        "updated_at",
        "completed_at",
    )
