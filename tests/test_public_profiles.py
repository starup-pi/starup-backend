"""Public profiles expose public work without revealing account or proposal data."""

import pytest
from django.utils import timezone

from starup_backend.common.roles import Role
from starup_backend.demands.models import Demand
from starup_backend.reviews.models import Review
from starup_backend.solutions.models import Solution
from tests.factories import (
    ClientFactory,
    DemandFactory,
    SolutionFactory,
    StartupFactory,
)

pytestmark = pytest.mark.django_db


def completed_work(*, rating=5, **kwargs):
    solution = SolutionFactory(
        status=Solution.Status.COMPLETED,
        demand__status=Demand.Status.COMPLETED,
        demand__completed_at=timezone.now(),
        **kwargs,
    )
    Review.objects.create(solution=solution, rating=rating)
    return solution


def test_client_profile_contains_only_public_name_and_work_statistics(api_client):
    client = ClientFactory(display_name="Public client")
    open_demand = DemandFactory(client=client)
    # Multiple proposals cannot multiply the number of public demands.
    SolutionFactory.create_batch(3, demand=open_demand)
    completed_work(demand__client=client, rating=1)
    completed_work(demand__client=client, rating=5)
    completed_work(demand__client=client, demand__visibility="PRIVATE", rating=5)
    DemandFactory(client=client, visibility="PRIVATE")
    DemandFactory(client=client, status="CANCELLED")

    response = api_client.get(f"/api/v1/clients/{client.id}/")
    assert response.status_code == 200
    assert response.json() == {
        "id": str(client.id),
        "display_name": "Public client",
        "open_count": 1,
        "completed_count": 2,
        "average_rating": 3.0,
        "review_count": 2,
    }
    serialized = response.content.decode()
    for private_value in (client.document, client.user.email, str(client.user_id)):
        assert private_value not in serialized
    assert "Private legal name" not in serialized
    assert "person_type" not in serialized


def test_client_profile_without_public_work_has_empty_statistics(api_client):
    client = ClientFactory()
    DemandFactory(client=client, visibility="PRIVATE")
    response = api_client.get(f"/api/v1/clients/{client.id}/")
    assert response.status_code == 200
    assert response.json()["open_count"] == response.json()["completed_count"] == 0
    assert response.json()["average_rating"] is None
    assert response.json()["review_count"] == 0


@pytest.mark.parametrize("kind", ["client", "startup"])
@pytest.mark.parametrize("changes", [{"ativo": False}, {"perfil_ativo": Role.INVESTOR}])
def test_hidden_profile_and_history_are_not_found_even_for_owner(
    api_client, kind, changes
):
    profile = ClientFactory() if kind == "client" else StartupFactory()
    for field, value in changes.items():
        setattr(profile.user, field, value)
    profile.user.save(update_fields=list(changes))
    api_client.force_authenticate(profile.user)
    prefix = "clients" if kind == "client" else "startups"
    url = f"/api/v1/{prefix}/{profile.id}/"
    assert api_client.get(url).status_code == 404
    assert api_client.get(url + "demands/").status_code == 404


def test_startup_counts_describe_public_work_and_keep_existing_rating_aggregates(
    api_client,
):
    startup = StartupFactory()
    completed_work(startup=startup, rating=1)
    completed_work(startup=startup, demand__visibility="PRIVATE", rating=5)
    hidden_client_work = completed_work(startup=startup, rating=3)
    hidden_client_work.demand.client.user.ativo = False
    hidden_client_work.demand.client.user.save(update_fields=["ativo"])
    for status in ("ACCEPTED", "IN_PROGRESS", "DELIVERED"):
        SolutionFactory(
            startup=startup,
            status=status,
            demand__status=Demand.Status.IN_PROGRESS,
        )
    SolutionFactory(startup=startup, status="ACCEPTED", demand__visibility="PRIVATE")
    SolutionFactory(startup=startup, status="SUBMITTED")

    response = api_client.get(f"/api/v1/startups/{startup.id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["completed_count"] == 1
    assert data["in_progress_count"] == 3
    # Existing public rating aggregates intentionally include private work.
    assert data["average_rating"] == 3.0
    assert data["review_count"] == 3
    assert "user" not in data
    assert "email" not in data


def test_client_history_is_public_only_with_ratings_and_selected_startup(api_client):
    client = ClientFactory()
    open_demand = DemandFactory(client=client)
    cancelled = DemandFactory(client=client, status="CANCELLED")
    completed = completed_work(demand__client=client, rating=4)
    DemandFactory(client=client, visibility="PRIVATE", title="Private demand")
    DemandFactory()
    # Owning the account must not expand the public profile history.
    api_client.force_authenticate(client.user)
    url = f"/api/v1/clients/{client.id}/demands/"
    response = api_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    rows = {row["id"]: row for row in data["results"]}
    assert set(rows) == {
        str(open_demand.id),
        str(cancelled.id),
        str(completed.demand_id),
    }
    assert rows[str(open_demand.id)]["rating"] is None
    assert rows[str(open_demand.id)]["selected_startup_id"] is None
    reviewed = rows[str(completed.demand_id)]
    assert reviewed["rating"] == 4
    assert reviewed["selected_startup_id"] == str(completed.startup_id)
    assert reviewed["selected_startup_name"] == completed.startup.name
    assert reviewed["client_id"] == str(client.id)
    assert reviewed["client_name"] == client.display_name
    assert "Private demand" not in str(data)
    assert "Private proposal" not in str(data)
    assert "Private legal name" not in str(data)
    assert [
        row["id"] for row in api_client.get(url, {"status": "OPEN"}).json()["results"]
    ] == [str(open_demand.id)]
    assert [
        row["id"]
        for row in api_client.get(url, {"status": "COMPLETED"}).json()["results"]
    ] == [str(completed.demand_id)]


def test_startup_history_excludes_unselected_private_and_hidden_client_work(api_client):
    startup = StartupFactory()
    selected = []
    for status in ("ACCEPTED", "IN_PROGRESS", "DELIVERED"):
        selected.append(SolutionFactory(startup=startup, status=status).demand_id)
    completed = completed_work(startup=startup, rating=2)
    selected.append(completed.demand_id)
    for status in ("SUBMITTED", "WITHDRAWN", "REJECTED"):
        SolutionFactory(startup=startup, status=status)
    SolutionFactory(startup=startup, status="ACCEPTED", demand__visibility="PRIVATE")
    SolutionFactory(
        startup=startup, status="ACCEPTED", demand__client__user__ativo=False
    )
    SolutionFactory(
        startup=startup,
        status="ACCEPTED",
        demand__client__user__perfil_ativo=Role.INVESTOR,
    )
    SolutionFactory(status="ACCEPTED")
    api_client.force_authenticate(startup.user)
    url = f"/api/v1/startups/{startup.id}/demands/"
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert {row["id"] for row in response.json()["results"]} == {
        str(pk) for pk in selected
    }
    assert "proposal" not in str(response.json())
    assert "delivery" not in str(response.json())
    assert (
        api_client.get(url, {"status": "COMPLETED"}).json()["results"][0]["rating"] == 2
    )


def test_history_pagination_and_query_validation(api_client):
    client = ClientFactory()
    DemandFactory.create_batch(21, client=client)
    url = f"/api/v1/clients/{client.id}/demands/"
    first = api_client.get(url).json()
    assert first["count"] == 21
    assert len(first["results"]) == 20
    assert first["next"] is not None
    second = api_client.get(url, {"page": 2}).json()
    assert len(second["results"]) == 1
    assert second["previous"] is not None
    assert not {row["id"] for row in first["results"]} & {
        row["id"] for row in second["results"]
    }
    for query in ({"status": "PRIVATE"}, {"page": "0"}, {"mine": "true"}):
        assert api_client.get(url, query).status_code == 400


def test_unselected_or_inactive_startup_is_not_named_in_public_history(api_client):
    demand = DemandFactory()
    SolutionFactory(demand=demand, status="SUBMITTED")
    selected = SolutionFactory(
        demand=demand, status="ACCEPTED", startup__user__ativo=False
    )
    response = api_client.get(f"/api/v1/clients/{demand.client_id}/demands/")
    row = response.json()["results"][0]
    assert row["selected_startup_id"] is None
    assert row["selected_startup_name"] is None
    assert str(selected.startup_id) not in str(row)
