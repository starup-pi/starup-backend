"""Regression cases found during the final review."""

import pytest

from nexora_backend.demands.services import update_demand
from nexora_backend.reviews.services import review_solution
from tests.factories import ClientFactory, DemandFactory
from tests.test_marketplace import delivered_solution

pytestmark = pytest.mark.django_db


def test_completed_demand_can_withdraw_and_restore_publication(api_client):
    client, _, solution = delivered_solution()
    review_solution(actor=client.user, solution_id=solution.pk, rating=5)
    update_demand(
        actor=client.user, demand_id=solution.demand_id, data={"visibility": "PRIVATE"}
    )
    assert not api_client.get("/api/v1/feed/").json()["results"]
    update_demand(
        actor=client.user, demand_id=solution.demand_id, data={"visibility": "PUBLIC"}
    )
    assert {
        post["kind"] for post in api_client.get("/api/v1/feed/").json()["results"]
    } == {"DEMAND", "REVIEWED_SOLUTION"}


def test_initially_private_review_is_published_when_owner_restores_visibility(
    api_client,
):
    client, _, solution = delivered_solution()
    update_demand(
        actor=client.user, demand_id=solution.demand_id, data={"visibility": "PRIVATE"}
    )
    review_solution(actor=client.user, solution_id=solution.pk, rating=5)
    update_demand(
        actor=client.user, demand_id=solution.demand_id, data={"visibility": "PUBLIC"}
    )
    assert {
        post["kind"] for post in api_client.get("/api/v1/feed/").json()["results"]
    } == {"DEMAND", "REVIEWED_SOLUTION"}


def test_mine_filter_is_scoped_to_authenticated_client(api_client):
    owner = ClientFactory()
    private = DemandFactory(client=owner, visibility="PRIVATE")
    DemandFactory(visibility="PRIVATE")
    for _ in range(25):
        DemandFactory()
    api_client.force_authenticate(owner.user)
    response = api_client.get("/api/v1/demands/?mine=true&visibility=PRIVATE").json()
    assert [row["id"] for row in response["results"]] == [str(private.pk)]
    api_client.force_authenticate(None)
    assert not api_client.get("/api/v1/demands/?mine=true").json()["results"]


def test_private_filter_does_not_expand_scope(api_client):
    DemandFactory(visibility="PRIVATE")
    assert not api_client.get("/api/v1/demands/?visibility=PRIVATE").json()["results"]
