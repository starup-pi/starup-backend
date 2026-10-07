"""Stable pagination, revoked visibility and constant query count."""

from urllib.parse import urlsplit

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from starup_backend.demands.services import update_demand
from starup_backend.feed.models import FeedPost
from tests.factories import DemandFactory, StartupFactory
from tests.test_marketplace import delivered_solution

pytestmark = pytest.mark.django_db


def local_path(url):
    parsed = urlsplit(url)
    return parsed.path + "?" + parsed.query


def test_cursor_survives_new_insert_without_duplicates(api_client):
    startup = StartupFactory()
    for _ in range(25):
        # Different startups are necessary because each source appears only once.
        FeedPost.objects.create(kind="STARTUP", startup=StartupFactory())
    first = api_client.get("/api/v1/feed/").json()
    first_ids = {post["id"] for post in first["results"]}
    FeedPost.objects.create(kind="STARTUP", startup=startup)
    second = api_client.get(local_path(first["next"])).json()
    second_ids = {post["id"] for post in second["results"]}
    assert len(first_ids) == 20 and len(second_ids) == 5
    assert first_ids.isdisjoint(second_ids)
    assert all("position" not in post for post in first["results"])
    assert second["next"] is None


def test_feed_query_count_does_not_grow_with_page_size(api_client):
    for _ in range(20):
        FeedPost.objects.create(kind="DEMAND", demand=DemandFactory())
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get("/api/v1/feed/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 20
    assert len(queries) <= 3


def test_mixed_feed_hydrates_in_batches(api_client):
    from starup_backend.reviews.services import review_solution

    client, startup, solution = delivered_solution()
    review_solution(actor=client.user, solution_id=solution.pk, rating=4)
    FeedPost.objects.create(kind="STARTUP", startup=startup)
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get("/api/v1/feed/")
    assert {post["kind"] for post in response.json()["results"]} == {
        "STARTUP",
        "DEMAND",
        "REVIEWED_SOLUTION",
    }
    assert len(queries) <= 4


def test_private_visibility_revokes_all_related_feed_posts(api_client):
    from starup_backend.reviews.services import review_solution

    client, _, solution = delivered_solution()
    update_demand(
        actor=client.user, demand_id=solution.demand_id, data={"visibility": "PRIVATE"}
    )
    review_solution(actor=client.user, solution_id=solution.pk, rating=5)
    assert not api_client.get("/api/v1/feed/").json()["results"]
    assert not FeedPost.objects.filter(review__solution=solution).exists()


def test_invalid_cursor_is_standard_error(api_client):
    response = api_client.get("/api/v1/feed/?cursor=malformed")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_feed_uses_public_names_instead_of_orm_keys(api_client):
    demand = DemandFactory()
    FeedPost.objects.create(kind="DEMAND", demand=demand)
    content = api_client.get("/api/v1/feed/").json()["results"][0]["content"]
    assert content["category_name"] == demand.category.name
    assert "category__name" not in content
