"""Review and confirmed completion are committed together."""

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from starup_backend.common.errors import Conflict
from starup_backend.demands.models import Demand
from starup_backend.demands.services import require_client
from starup_backend.feed.models import FeedPost
from starup_backend.notifications.services import enqueue_notification
from starup_backend.solutions.models import Solution
from starup_backend.solutions.services import record_transition
from starup_backend.usuarios.models import Usuario

from .models import Review


@transaction.atomic
def review_solution(*, actor: Usuario, solution_id: UUID, rating: int) -> Review:
    require_client(actor)
    if type(rating) is not int or not 1 <= rating <= 5:
        raise Conflict()
    try:
        info = (
            Solution.objects.filter(demand__client__user_id=actor.pk)
            .values("demand_id")
            .get(pk=solution_id)
        )
        demand = Demand.objects.select_for_update().get(pk=info["demand_id"])
        solution = Solution.objects.select_for_update().get(pk=solution_id)
    except (Solution.DoesNotExist, Demand.DoesNotExist) as exc:
        raise NotFound() from exc
    if (
        solution.status != Solution.Status.DELIVERED
        or demand.status != Demand.Status.IN_PROGRESS
        or Review.objects.filter(solution=solution).exists()
    ):
        raise Conflict()
    review = Review.objects.create(solution=solution, rating=rating)
    record_transition(solution, actor=actor, target=Solution.Status.COMPLETED)
    demand.status = Demand.Status.COMPLETED
    demand.completed_at = timezone.now()
    demand.save(update_fields=["status", "completed_at", "updated_at"])
    if demand.visibility == Demand.Visibility.PUBLIC:
        FeedPost.objects.create(kind=FeedPost.Kind.REVIEWED_SOLUTION, review=review)
    enqueue_notification(user_id=solution.startup.user_id)
    return review
