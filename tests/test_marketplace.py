"""Complete public/private workflows and authorization failures."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from nexora_backend.common.errors import Conflict
from nexora_backend.demands.models import Demand
from nexora_backend.demands.services import create_demand, update_demand
from nexora_backend.feed.models import FeedPost
from nexora_backend.profiles.selectors import public_startups
from nexora_backend.reviews.models import Review
from nexora_backend.reviews.services import review_solution
from nexora_backend.solutions.models import Solution
from nexora_backend.solutions.services import submit_solution, transition_solution
from tests.factories import (
    CategoryFactory,
    ClientFactory,
    DemandFactory,
    InvestorFactory,
    SolutionFactory,
    StartupFactory,
)

pytestmark = pytest.mark.django_db


def test_complete_api_flow(api_client):
    client, startup, category = ClientFactory(), StartupFactory(), CategoryFactory()
    api_client.force_authenticate(client.user)
    response = api_client.post(
        "/api/v1/demands/",
        {
            "title": "Reduce delays",
            "description": "Improve order processing",
            "category_id": str(category.id),
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    demand_id = response.json()["id"]
    api_client.force_authenticate(startup.user)
    response = api_client.post(
        "/api/v1/solutions/",
        {"demand_id": demand_id, "proposal": "Private execution plan"},
        format="json",
    )
    assert response.status_code == 201, response.content
    solution_id = response.json()["id"]
    api_client.force_authenticate(client.user)
    assert (
        api_client.post(
            f"/api/v1/solutions/{solution_id}/transition/",
            {"status": "ACCEPTED"},
            format="json",
        ).status_code
        == 200
    )
    api_client.force_authenticate(startup.user)
    assert (
        api_client.post(
            f"/api/v1/solutions/{solution_id}/transition/",
            {"status": "IN_PROGRESS"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            f"/api/v1/solutions/{solution_id}/transition/",
            {"status": "DELIVERED", "delivery": "Private delivery details"},
            format="json",
        ).status_code
        == 200
    )
    api_client.force_authenticate(client.user)
    response = api_client.post(
        "/api/v1/reviews/", {"solution_id": solution_id, "rating": 5}, format="json"
    )
    assert response.status_code == 201, response.content
    assert Demand.objects.get(id=demand_id).status == "COMPLETED"
    assert Solution.objects.get(id=solution_id).status == "COMPLETED"
    assert list(
        Solution.objects.get(id=solution_id).history.values_list(
            "new_status", flat=True
        )
    ) == ["SUBMITTED", "ACCEPTED", "IN_PROGRESS", "DELIVERED", "COMPLETED"]
    api_client.force_authenticate(None)
    feed = api_client.get("/api/v1/feed/").json()
    assert {post["kind"] for post in feed["results"]} == {"DEMAND", "REVIEWED_SOLUTION"}
    assert "Private delivery" not in str(feed)
    assert "Private execution" not in str(feed)
    directory = api_client.get("/api/v1/startups/").json()["results"]
    assert directory[0]["average_rating"] == 5.0
    assert directory[0]["review_count"] == 1


def delivered_solution():
    client, startup = ClientFactory(), StartupFactory()
    demand = create_demand(
        actor=client.user,
        data={
            "title": "Problem",
            "description": "Context",
            "category": CategoryFactory(),
        },
    )
    solution = submit_solution(actor=startup.user, demand_id=demand.pk, proposal="Plan")
    transition_solution(actor=client.user, solution_id=solution.pk, target="ACCEPTED")
    transition_solution(
        actor=startup.user, solution_id=solution.pk, target="IN_PROGRESS"
    )
    transition_solution(
        actor=startup.user, solution_id=solution.pk, target="DELIVERED", delivery="Done"
    )
    return client, startup, solution


@pytest.mark.parametrize("rating", [0, 6, -1, 2.5, 3.0, True, "5", None])
def test_invalid_rating_inputs(api_client, rating):
    client, _, solution = delivered_solution()
    api_client.force_authenticate(client.user)
    response = api_client.post(
        "/api/v1/reviews/",
        {"solution_id": str(solution.pk), "rating": rating},
        format="json",
    )
    assert response.status_code == 400
    assert not Review.objects.exists()


@pytest.mark.parametrize("rating", [0, 6])
def test_review_database_constraint(rating):
    solution = SolutionFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(solution=solution, rating=rating)


def test_review_once_only():
    client, _, solution = delivered_solution()
    review_solution(actor=client.user, solution_id=solution.pk, rating=4)
    with pytest.raises(Conflict):
        review_solution(actor=client.user, solution_id=solution.pk, rating=1)
    assert Review.objects.count() == 1


def test_review_database_uniqueness():
    solution = SolutionFactory()
    Review.objects.create(solution=solution, rating=4)
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(solution=solution, rating=5)


def test_review_before_delivery_fails(api_client):
    solution = SolutionFactory()
    api_client.force_authenticate(solution.demand.client.user)
    assert (
        api_client.post(
            "/api/v1/reviews/",
            {"solution_id": str(solution.pk), "rating": 5},
            format="json",
        ).status_code
        == 409
    )


def test_only_demand_owner_can_review(api_client):
    _, startup, solution = delivered_solution()
    stranger = ClientFactory()
    for actor, status in ((stranger.user, 404), (startup.user, 403)):
        api_client.force_authenticate(actor)
        response = api_client.post(
            "/api/v1/reviews/",
            {"solution_id": str(solution.pk), "rating": 5},
            format="json",
        )
        assert response.status_code == status


def test_accept_rejects_other_proposals():
    first = SolutionFactory()
    second = SolutionFactory(demand=first.demand)
    transition_solution(
        actor=first.demand.client.user, solution_id=first.pk, target="ACCEPTED"
    )
    second.refresh_from_db()
    assert second.status == "REJECTED"
    assert second.history.get().new_status == "REJECTED"
    with pytest.raises(Conflict):
        transition_solution(
            actor=first.demand.client.user, solution_id=second.pk, target="ACCEPTED"
        )


def test_unique_accepted_solution_at_database():
    first = SolutionFactory(status="ACCEPTED")
    with pytest.raises(IntegrityError), transaction.atomic():
        SolutionFactory(demand=first.demand, status="IN_PROGRESS")


def test_proposal_duplicate_conflicts():
    solution = SolutionFactory()
    with pytest.raises(Conflict):
        submit_solution(
            actor=solution.startup.user,
            demand_id=solution.demand_id,
            proposal="Another",
        )


@pytest.mark.parametrize(
    "extra", [{"client": "spoof"}, {"status": "COMPLETED"}, {"author": "spoof"}]
)
def test_demand_mass_assignment(api_client, extra):
    client = ClientFactory()
    api_client.force_authenticate(client.user)
    response = api_client.post(
        "/api/v1/demands/",
        {
            "title": "T",
            "description": "D",
            "category_id": str(CategoryFactory().id),
            **extra,
        },
        format="json",
    )
    assert response.status_code == 400


def test_private_demand_idor(api_client):
    demand = DemandFactory(visibility="PRIVATE")
    for actor in (
        None,
        ClientFactory().user,
        StartupFactory().user,
        InvestorFactory().user,
    ):
        api_client.force_authenticate(actor)
        assert api_client.get(f"/api/v1/demands/{demand.pk}/").status_code == 404
    api_client.force_authenticate(demand.client.user)
    assert api_client.get(f"/api/v1/demands/{demand.pk}/").status_code == 200


def test_private_proposal_idor(api_client):
    solution = SolutionFactory()
    api_client.force_authenticate(StartupFactory().user)
    assert api_client.get(f"/api/v1/solutions/{solution.pk}/").status_code == 404
    assert (
        api_client.get(f"/api/v1/solutions/{solution.pk}/history/").status_code == 404
    )
    assert (
        api_client.post(
            f"/api/v1/solutions/{solution.pk}/transition/",
            {"status": "ACCEPTED"},
            format="json",
        ).status_code
        == 404
    )


def test_startup_cannot_propose_private_demand(api_client):
    demand = DemandFactory(visibility="PRIVATE")
    api_client.force_authenticate(StartupFactory().user)
    assert (
        api_client.post(
            "/api/v1/solutions/",
            {"demand_id": str(demand.id), "proposal": "Plan"},
            format="json",
        ).status_code
        == 404
    )


def test_selected_startup_retains_access_when_demand_becomes_private(api_client):
    solution = SolutionFactory()
    transition_solution(
        actor=solution.demand.client.user, solution_id=solution.pk, target="ACCEPTED"
    )
    update_demand(
        actor=solution.demand.client.user,
        demand_id=solution.demand_id,
        data={"visibility": "PRIVATE"},
    )
    api_client.force_authenticate(solution.startup.user)
    assert api_client.get(f"/api/v1/demands/{solution.demand_id}/").status_code == 200
    assert not api_client.get("/api/v1/feed/").json()["results"]


def test_demand_cancellation_rejects_proposals(api_client):
    solution = SolutionFactory()
    api_client.force_authenticate(solution.demand.client.user)
    assert (
        api_client.post(f"/api/v1/demands/{solution.demand_id}/cancel/").status_code
        == 200
    )
    solution.refresh_from_db()
    assert solution.status == "REJECTED"


def test_stranger_cannot_edit_or_cancel_demand(api_client):
    demand = DemandFactory()
    api_client.force_authenticate(ClientFactory().user)
    assert (
        api_client.patch(
            f"/api/v1/demands/{demand.id}/", {"title": "Spoof"}, format="json"
        ).status_code
        == 404
    )
    assert api_client.post(f"/api/v1/demands/{demand.id}/cancel/").status_code == 404


def test_frozen_requirements_after_acceptance(api_client):
    solution = SolutionFactory()
    transition_solution(
        actor=solution.demand.client.user, solution_id=solution.pk, target="ACCEPTED"
    )
    api_client.force_authenticate(solution.demand.client.user)
    assert (
        api_client.patch(
            f"/api/v1/demands/{solution.demand_id}/",
            {"description": "Changed"},
            format="json",
        ).status_code
        == 409
    )


def test_empty_delivery_and_skipped_transitions_fail(api_client):
    solution = SolutionFactory()
    api_client.force_authenticate(solution.startup.user)
    assert (
        api_client.post(
            f"/api/v1/solutions/{solution.id}/transition/",
            {"status": "DELIVERED"},
            format="json",
        ).status_code
        == 409
    )
    assert (
        api_client.post(
            f"/api/v1/solutions/{solution.id}/transition/",
            {"status": "COMPLETED"},
            format="json",
        ).status_code
        == 400
    )


def test_startup_owner_updates_public_fields_only(api_client):
    startup = StartupFactory()
    api_client.force_authenticate(startup.user)
    assert (
        api_client.patch(
            f"/api/v1/my-startups/{startup.pk}/", {"name": "Updated"}, format="json"
        ).status_code
        == 204
    )
    assert (
        api_client.patch(
            f"/api/v1/my-startups/{startup.pk}/", {"average_rating": 5}, format="json"
        ).status_code
        == 400
    )
    api_client.force_authenticate(StartupFactory().user)
    assert (
        api_client.patch(
            f"/api/v1/my-startups/{startup.pk}/", {"name": "Spoof"}, format="json"
        ).status_code
        == 404
    )


def test_startup_without_reviews_has_null_average():
    startup = StartupFactory()
    result = public_startups().get(id=startup.id)
    assert result["average_rating"] is None
    assert result["review_count"] == 0


def test_demand_completion_date_constraint():
    with pytest.raises(IntegrityError), transaction.atomic():
        DemandFactory(status="COMPLETED", completed_at=None)
    demand = DemandFactory(status="COMPLETED", completed_at=timezone.now())
    assert demand.completed_at is not None


def test_feed_target_constraint():
    with pytest.raises(IntegrityError), transaction.atomic():
        FeedPost.objects.create(kind="DEMAND")
    with pytest.raises(IntegrityError), transaction.atomic():
        FeedPost.objects.create(
            kind="DEMAND", demand=DemandFactory(), startup=StartupFactory()
        )
