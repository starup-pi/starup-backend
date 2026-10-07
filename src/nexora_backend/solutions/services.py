"""Transitions lock demand before solution to serialize concurrent acceptance."""

from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from nexora_backend.accounts.services import require_role
from nexora_backend.common.errors import Conflict
from nexora_backend.common.roles import Role
from nexora_backend.demands.models import Demand
from nexora_backend.demands.selectors import visible_demands
from nexora_backend.notifications.services import enqueue_notification
from nexora_backend.profiles.models import StartupProfile
from nexora_backend.usuarios.models import Usuario

from .models import Solution, SolutionStatusEvent
from .selectors import participant_solutions


def record_transition(solution: Solution, *, actor: Usuario, target: str) -> None:
    previous = solution.status
    solution.status = target
    solution.save(update_fields=["status", "delivery", "updated_at"])
    SolutionStatusEvent.objects.create(
        solution=solution, actor=actor, previous_status=previous, new_status=target
    )


@transaction.atomic
def submit_solution(*, actor: Usuario, demand_id: UUID, proposal: str) -> Solution:
    require_role(actor, Role.STARTUP)
    try:
        demand = Demand.objects.select_for_update().get(
            pk=demand_id, pk__in=visible_demands(actor).values("id")
        )
        startup = StartupProfile.objects.get(user=actor)
    except (Demand.DoesNotExist, StartupProfile.DoesNotExist) as exc:
        raise NotFound() from exc
    if demand.status != Demand.Status.OPEN:
        raise Conflict()
    try:
        with transaction.atomic():
            solution = Solution.objects.create(
                demand=demand, startup=startup, proposal=proposal
            )
    except IntegrityError as exc:
        raise Conflict() from exc
    SolutionStatusEvent.objects.create(
        solution=solution, actor=actor, previous_status="", new_status=solution.status
    )
    enqueue_notification(user_id=demand.client.user_id)
    return solution


@transaction.atomic
def transition_solution(
    *, actor: Usuario, solution_id: UUID, target: str, delivery: str = ""
) -> Solution:
    if actor.perfil_ativo not in (Role.CLIENT, Role.STARTUP):
        raise PermissionDenied()
    require_role(actor, Role(actor.perfil_ativo))
    try:
        scoped = participant_solutions(actor).values("demand_id").get(pk=solution_id)
        demand = Demand.objects.select_for_update().get(pk=scoped["demand_id"])
        solution = Solution.objects.select_for_update().get(pk=solution_id)
    except (Solution.DoesNotExist, Demand.DoesNotExist) as exc:
        raise NotFound() from exc
    is_client = actor.perfil_ativo == Role.CLIENT and demand.client.user_id == actor.pk
    is_startup = (
        actor.perfil_ativo == Role.STARTUP and solution.startup.user_id == actor.pk
    )
    allowed = {
        ("SUBMITTED", "ACCEPTED"): is_client,
        ("SUBMITTED", "REJECTED"): is_client,
        ("SUBMITTED", "WITHDRAWN"): is_startup,
        ("ACCEPTED", "IN_PROGRESS"): is_startup,
        ("IN_PROGRESS", "DELIVERED"): is_startup,
    }
    if not (is_client or is_startup):
        raise PermissionDenied()
    if not allowed.get((solution.status, target)):
        raise Conflict()
    if target == "ACCEPTED":
        if not solution.startup.user.ativo:
            raise Conflict()
        if demand.status != Demand.Status.OPEN:
            raise Conflict()
        demand.status = Demand.Status.IN_PROGRESS
        demand.save(update_fields=["status", "updated_at"])
        for other in (
            demand.solutions.select_for_update()
            .filter(status="SUBMITTED")
            .exclude(pk=solution.pk)
        ):
            record_transition(other, actor=actor, target="REJECTED")
    if target == "DELIVERED":
        if not delivery.strip():
            raise Conflict()
        solution.delivery = delivery
    record_transition(solution, actor=actor, target=target)
    recipient = solution.startup.user_id if is_client else demand.client.user_id
    enqueue_notification(user_id=recipient)
    return solution
