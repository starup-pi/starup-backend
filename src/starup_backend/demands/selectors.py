"""Scope reads before any detail lookup."""

from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import CharField, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast, Concat, JSONObject

from starup_backend.common.roles import Role
from starup_backend.solutions.models import Solution

from .models import Demand, DemandImage


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
    selected = Solution.objects.filter(
        demand_id=OuterRef("pk"),
        status__in=["ACCEPTED", "IN_PROGRESS", "DELIVERED", "COMPLETED"],
        startup__user__ativo=True,
        startup__user__perfil_ativo=Role.STARTUP,
    ).order_by("id")
    images = DemandImage.objects.filter(demand_id=OuterRef("pk")).values(
        item=JSONObject(
            id=F("id"),
            url=Concat(
                Value("/api/v1/demand-images/"),
                Cast("id", output_field=CharField()),
                Value("/"),
            ),
        )
    )
    return (
        visible_demands(user)
        .annotate(
            client_name=F("client__display_name"),
            selected_startup_id=Subquery(selected.values("startup_id")[:1]),
            selected_startup_name=Subquery(selected.values("startup__name")[:1]),
            rating=Subquery(
                selected.filter(status="COMPLETED", demand__status="COMPLETED").values(
                    "review__rating"
                )[:1]
            ),
            image_items=ArraySubquery(images),
        )
        .values(
            "id",
            "title",
            "description",
            "tags",
            "client_id",
            "client_name",
            "rating",
            "selected_startup_id",
            "selected_startup_name",
            "image_items",
            "category_id",
            "category__name",
            "status",
            "visibility",
            "created_at",
            "updated_at",
            "completed_at",
        )
    )
