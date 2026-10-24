"""Authorized and serialized demand mutations."""

from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from starup_backend.accounts.services import require_role
from starup_backend.common.errors import Conflict
from starup_backend.common.roles import Role
from starup_backend.feed.models import FeedPost
from starup_backend.profiles.models import ClientProfile
from starup_backend.usuarios.models import Usuario

from .media import MAX_IMAGES, image_write_transaction, remove_images, save_images
from .models import Demand


def require_client(actor: Usuario) -> None:
    require_role(actor, Role.CLIENT)


def create_demand(*, actor: Usuario, data: dict[str, Any]) -> Demand:
    data = data.copy()
    images = data.pop("images", [])
    if len(images) > MAX_IMAGES:
        raise ValidationError({"images": "Use no máximo 4 imagens."})
    with image_write_transaction(bool(images)) as written:
        require_client(actor)
        try:
            profile = ClientProfile.objects.get(user=actor)
        except ClientProfile.DoesNotExist as exc:
            raise Conflict() from exc
        demand = Demand.objects.create(client=profile, **data)
        save_images(demand=demand, images=images, written=written)
        if demand.visibility == Demand.Visibility.PUBLIC:
            FeedPost.objects.create(kind=FeedPost.Kind.DEMAND, demand=demand)
        return demand


def update_demand(*, actor: Usuario, demand_id: UUID, data: dict[str, Any]) -> Demand:
    data = data.copy()
    images = data.pop("images", [])
    keep_ids = data.pop("keep_image_ids", None)
    changed = set(data)
    if images or keep_ids is not None:
        changed.add("images")
    with image_write_transaction(bool(images)) as written:
        require_client(actor)
        try:
            demand = Demand.objects.select_for_update().get(
                pk=demand_id, client__user_id=actor.pk
            )
        except Demand.DoesNotExist as exc:
            raise NotFound() from exc
        if demand.status != Demand.Status.OPEN and changed - {"visibility"}:
            raise Conflict()
        existing = list(demand.images.select_for_update())
        existing_ids = {row.id for row in existing}
        if keep_ids is not None and (
            not set(keep_ids) <= existing_ids or len(set(keep_ids)) != len(keep_ids)
        ):
            raise ValidationError(
                {"keep_image_ids": "Selecione imagens desta demanda."}
            )
        kept = [row for row in existing if keep_ids is None or row.id in keep_ids]
        if len(kept) + len(images) > MAX_IMAGES:
            raise ValidationError({"images": "Use no máximo 4 imagens por demanda."})
        for field, value in data.items():
            setattr(demand, field, value)
        demand.save()
        if keep_ids is not None:
            remove_images(demand.images.exclude(id__in=keep_ids))
        for index, image in enumerate(kept):
            if image.ordering != index:
                image.ordering = index
                image.save(update_fields=["ordering", "updated_at"])
        save_images(demand=demand, images=images, written=written, offset=len(kept))
        if demand.visibility == Demand.Visibility.PUBLIC:
            FeedPost.objects.get_or_create(
                demand=demand, defaults={"kind": FeedPost.Kind.DEMAND}
            )
            from starup_backend.reviews.models import Review

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
    from starup_backend.solutions.models import Solution, SolutionStatusEvent

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
