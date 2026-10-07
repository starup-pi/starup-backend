"""Authorized and serialized demand mutations."""

from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from nexora_backend.accounts.services import require_role
from nexora_backend.common.errors import Conflict
from nexora_backend.common.roles import Role
from nexora_backend.feed.models import FeedPost
from nexora_backend.profiles.models import ClientProfile
from nexora_backend.usuarios.models import Usuario

from .models import Demand


def require_client(actor: Usuario) -> None:
    require_role(actor, Role.CLIENT)


@transaction.atomic
def create_demand(*, actor: Usuario, data: dict[str, Any]) -> Demand:
    require_client(actor)
    try:
        profile = ClientProfile.objects.get(user=actor)
    except ClientProfile.DoesNotExist as exc:
        raise Conflict() from exc
    demand = Demand.objects.create(client=profile, **data)
    if demand.visibility == Demand.Visibility.PUBLIC:
        FeedPost.objects.create(kind=FeedPost.Kind.DEMAND, demand=demand)
    return demand


@transaction.atomic
def update_demand(*, actor: Usuario, demand_id: UUID, data: dict[str, Any]) -> Demand:
    require_client(actor)
    try:
        demand = Demand.objects.select_for_update().get(
            pk=demand_id, client__user_id=actor.pk
        )
    except Demand.DoesNotExist as exc:
        raise NotFound() from exc
    if demand.status != Demand.Status.OPEN and set(data) - {"visibility"}:
        raise Conflict()
    for field, value in data.items():
        setattr(demand, field, value)
    demand.save()
    if demand.visibility == Demand.Visibility.PUBLIC:
        FeedPost.objects.get_or_create(
            demand=demand, defaults={"kind": FeedPost.Kind.DEMAND}
        )
        from nexora_backend.reviews.models import Review

        review = Review.objects.filter(solution__demand=demand).first()
        if review:
            FeedPost.objects.get_or_create(
                review=review, defaults={"kind": FeedPost.Kind.REVIEWED_SOLUTION}
            )
    return demand


@transaction.atomic
def cancel_demand(*, actor: Usuario, demand_id) -> Demand:
    require_client(actor)
    try:
        demand = Demand.objects.select_for_update().get(
            pk=demand_id, client__user_id=actor.pk
        )
    except Demand.DoesNotExist as exc:
        raise NotFound() from exc
    if demand.status != Demand.Status.OPEN:
        raise Conflict()
    from nexora_backend.solutions.models import Solution, SolutionStatusEvent

    for solution in demand.solutions.select_for_update().filter(status="SUBMITTED"):
        solution.status = Solution.Status.REJECTED
        solution.updated_at = timezone.now()
        solution.save(update_fields=["status", "updated_at"])
        SolutionStatusEvent.objects.create(
            solution=solution,
            actor=actor,
            previous_status="SUBMITTED",
            new_status="REJECTED",
        )
    demand.status = Demand.Status.CANCELLED
    demand.save(update_fields=["status", "updated_at"])
    return demand
