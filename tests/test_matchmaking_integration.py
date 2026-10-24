"""Exercise matchmaking through the session API and the full delivery lifecycle."""

import pytest
from rest_framework.test import APIClient

from starup_backend.demands.models import Category
from starup_backend.profiles.models import StartupProfile

pytestmark = pytest.mark.django_db


def register_and_login(email, role, **profile):
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/v1/auth/csrf/").json()
    client.credentials(HTTP_X_CSRFTOKEN=csrf["csrf_token"])
    response = client.post(
        "/api/v1/auth/register/",
        {
            "email": email,
            "password": "Strong-Password-42!",
            "role": role,
            "policy_version": csrf["policy_version"],
            **profile,
        },
        format="json",
    )
    assert response.status_code == 202, response.data
    response = client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": "Strong-Password-42!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    client.credentials(HTTP_X_CSRFTOKEN=response.json()["csrf_token"])
    return client


def test_matchmaking_from_registration_to_review():
    logistics = Category.objects.get(slug="logistics")
    finance = Category.objects.get(slug="finance")
    customer = register_and_login(
        "customer@example.test",
        "CLIENT",
        person_type="PF",
        document="52998224725",
        display_name="Customer",
    )
    startup = register_and_login(
        "startup@example.test",
        "STARTUP",
        startup_name="Logistics Partner",
        category=logistics.slug,
    )
    investor = register_and_login("reader@example.test", "INVESTOR")
    profile = startup.get("/api/v1/me/").json()["profile"]
    assert profile["category"] == logistics.slug
    profile_url = f"/api/v1/my-startups/{profile['id']}/"

    demand_ids = {}
    for category in (logistics, finance):
        response = customer.post(
            "/api/v1/demands/",
            {
                "title": f"Improve {category.name}",
                "description": "A concrete customer requirement",
                "category_id": str(category.pk),
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        demand_ids[category.slug] = response.json()["id"]

    recommendations_url = "/api/v1/matchmaking/recommended-demands/"
    recommendations = startup.get(recommendations_url).json()
    assert recommendations[0]["demand_id"] == demand_ids[logistics.slug]
    assert not recommendations[0]["has_seal"]
    assert investor.get(recommendations_url).status_code == 403

    # An editable sector changes the order and survives the private /me round trip.
    response = startup.patch(profile_url, {"category": finance.slug}, format="json")
    assert response.status_code == 204
    assert startup.get("/api/v1/me/").json()["profile"]["category"] == finance.slug
    assert (
        startup.get(recommendations_url).json()[0]["demand_id"]
        == demand_ids[finance.slug]
    )
    assert (
        startup.patch(
            profile_url, {"category": logistics.slug}, format="json"
        ).status_code
        == 204
    )

    demand_id = demand_ids[logistics.slug]
    matches_url = f"/api/v1/matchmaking/demands/{demand_id}/"
    matches = customer.get(matches_url).json()
    assert matches[0]["startup_id"] == profile["id"]
    initial_score = matches[0]["score"]

    proposal = startup.post(
        "/api/v1/solutions/",
        {"demand_id": demand_id, "proposal": "Private logistics proposal"},
        format="json",
    )
    assert proposal.status_code == 201, proposal.data
    solution_id = proposal.json()["id"]
    assert demand_id not in [
        item["demand_id"] for item in startup.get(recommendations_url).json()
    ]
    transition_url = f"/api/v1/solutions/{solution_id}/transition/"
    assert (
        customer.post(transition_url, {"status": "ACCEPTED"}, format="json").status_code
        == 200
    )
    assert (
        startup.post(
            transition_url, {"status": "IN_PROGRESS"}, format="json"
        ).status_code
        == 200
    )
    assert (
        startup.post(
            transition_url,
            {"status": "DELIVERED", "delivery": "Private delivery evidence"},
            format="json",
        ).status_code
        == 200
    )
    response = customer.post(
        "/api/v1/reviews/",
        {"solution_id": solution_id, "rating": 5},
        format="json",
    )
    assert response.status_code == 201, response.data
    demand = customer.get(f"/api/v1/demands/{demand_id}/").json()
    assert demand["status"] == "COMPLETED"

    showcase_url = "/api/v1/matchmaking/traction-showcase/?min_score=75"
    ranked = investor.get(showcase_url).json()
    assert ranked[0]["startup_id"] == profile["id"]
    assert ranked[0]["score"] > initial_score
    assert ranked[0]["has_seal"]
    assert ranked[0]["completed_tests"] == 1
    assert ranked[0]["average_rating"] == 5.0
    assert ranked[0]["review_count"] == 1
    assert "Private logistics proposal" not in str(ranked)
    assert "Private delivery evidence" not in str(ranked)
    assert "customer@example.test" not in str(ranked)
    assert "reader@example.test" not in str(ranked)
    assert "no-store" in startup.get(recommendations_url)["Cache-Control"]

    assert startup.post("/api/v1/auth/logout/").status_code == 204
    assert startup.get(recommendations_url).status_code == 403


def test_startup_category_is_optional_and_bounded(csrf_client):
    body = {
        "email": "category@example.test",
        "password": "Strong-Password-42!",
        "role": "STARTUP",
        "policy_version": "2026-10",
        "startup_name": "New Partner",
        "category": "x" * 41,
    }
    response = csrf_client.post("/api/v1/auth/register/", body, format="json")
    assert response.status_code == 400
    assert "category" in response.json()["fields"]
    assert not StartupProfile.objects.exists()
    body.pop("category")
    assert (
        csrf_client.post("/api/v1/auth/register/", body, format="json").status_code
        == 202
    )
    assert StartupProfile.objects.get().category == ""


def test_non_startup_cannot_register_sector(csrf_client):
    response = csrf_client.post(
        "/api/v1/auth/register/",
        {
            "email": "private@example.test",
            "password": "Strong-Password-42!",
            "role": "INVESTOR",
            "policy_version": "2026-10",
            "category": "logistics",
        },
        format="json",
    )
    assert response.status_code == 400
