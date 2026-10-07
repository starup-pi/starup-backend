"""Explicit public projections never select authentication columns."""

from django.db.models import Avg, Count

from nexora_backend.common.roles import Role

from .models import StartupProfile


def public_startups():
    return (
        StartupProfile.objects.filter(user__ativo=True, user__perfil_ativo=Role.STARTUP)
        .annotate(
            average_rating=Avg("solutions__review__rating"),
            review_count=Count("solutions__review"),
        )
        .values(
            "id",
            "name",
            "description",
            "website",
            "category",
            "average_rating",
            "review_count",
        )
        .order_by("name", "id")
    )
