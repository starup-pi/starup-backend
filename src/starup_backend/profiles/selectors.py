"""Explicit public projections never select authentication columns."""

from django.contrib.auth.models import AnonymousUser
from django.db.models import Avg, Count, Q

from starup_backend.common.roles import Role
from starup_backend.demands.models import Demand
from starup_backend.demands.selectors import demand_projection
from starup_backend.solutions.models import Solution

from .models import ClientProfile, StartupProfile

SELECTED_SOLUTION_STATUSES = (
    Solution.Status.ACCEPTED,
    Solution.Status.IN_PROGRESS,
    Solution.Status.DELIVERED,
    Solution.Status.COMPLETED,
)


def public_startups():
    public_work = Q(
        solutions__demand__visibility=Demand.Visibility.PUBLIC,
        solutions__demand__client__user__ativo=True,
        solutions__demand__client__user__perfil_ativo=Role.CLIENT,
    )
    return (
        StartupProfile.objects.filter(user__ativo=True, user__perfil_ativo=Role.STARTUP)
        .annotate(
            average_rating=Avg("solutions__review__rating"),
            review_count=Count("solutions__review"),
            completed_count=Count(
                "solutions",
                filter=public_work
                & Q(
                    solutions__status=Solution.Status.COMPLETED,
                    solutions__demand__status=Demand.Status.COMPLETED,
                ),
                distinct=True,
            ),
            in_progress_count=Count(
                "solutions",
                filter=public_work
                & Q(
                    solutions__status__in=SELECTED_SOLUTION_STATUSES[:-1],
                    solutions__demand__status=Demand.Status.IN_PROGRESS,
                ),
                distinct=True,
            ),
        )
        .values(
            "id",
            "name",
            "description",
            "website",
            "category",
            "average_rating",
            "review_count",
            "completed_count",
            "in_progress_count",
        )
        .order_by("name", "id")
    )


def public_clients():
    """Expose a display name and public work statistics, never civil identity."""
    public_work = Q(demands__visibility=Demand.Visibility.PUBLIC)
    reviewed_work = public_work & Q(
        demands__status=Demand.Status.COMPLETED,
        demands__solutions__status=Solution.Status.COMPLETED,
    )
    return (
        ClientProfile.objects.filter(user__ativo=True, user__perfil_ativo=Role.CLIENT)
        .annotate(
            open_count=Count(
                "demands",
                filter=public_work & Q(demands__status=Demand.Status.OPEN),
                distinct=True,
            ),
            completed_count=Count(
                "demands",
                filter=public_work & Q(demands__status=Demand.Status.COMPLETED),
                distinct=True,
            ),
            average_rating=Avg(
                "demands__solutions__review__rating", filter=reviewed_work
            ),
            review_count=Count(
                "demands__solutions__review", filter=reviewed_work, distinct=True
            ),
        )
        .values(
            "id",
            "display_name",
            "open_count",
            "completed_count",
            "average_rating",
            "review_count",
        )
        .order_by("display_name", "id")
    )


def public_client_demands(client_id):
    return demand_projection(AnonymousUser()).filter(client_id=client_id)


def public_startup_demands(startup_id):
    """Public history includes selected work, never private proposal activity."""
    return demand_projection(AnonymousUser()).filter(
        solutions__startup_id=startup_id,
        solutions__status__in=SELECTED_SOLUTION_STATUSES,
    )
