"""PostgreSQL integration checks for concurrent writes, using separate connections."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connections

from starup_backend.common.errors import Conflict
from starup_backend.reviews.models import Review
from starup_backend.reviews.services import review_solution
from starup_backend.solutions.models import Solution
from starup_backend.solutions.services import transition_solution
from tests.factories import SolutionFactory
from tests.test_marketplace import delivered_solution

pytestmark = pytest.mark.django_db(transaction=True)


def race(actions):
    barrier = Barrier(len(actions))

    def execute(action):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            action()
            return "success"
        except Conflict:
            return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(execute, actions))


def test_concurrent_acceptance_commits_one_winner():
    first = SolutionFactory()
    second = SolutionFactory(demand=first.demand)
    owner = first.demand.client.user
    result = race(
        [
            lambda: transition_solution(
                actor=owner, solution_id=first.pk, target="ACCEPTED"
            ),
            lambda: transition_solution(
                actor=owner, solution_id=second.pk, target="ACCEPTED"
            ),
        ]
    )
    assert sorted(result) == ["conflict", "success"]
    assert Solution.objects.filter(demand=first.demand, status="ACCEPTED").count() == 1
    assert Solution.objects.filter(demand=first.demand, status="REJECTED").count() == 1


def test_concurrent_reviews_commit_once():
    client, _, solution = delivered_solution()
    result = race(
        [
            lambda: review_solution(
                actor=client.user, solution_id=solution.pk, rating=5
            ),
            lambda: review_solution(
                actor=client.user, solution_id=solution.pk, rating=1
            ),
        ]
    )
    assert sorted(result) == ["conflict", "success"]
    assert Review.objects.filter(solution=solution).count() == 1
