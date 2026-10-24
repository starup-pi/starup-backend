"""The public timeline connects authors, topics and completed work safely."""

from urllib.parse import urlsplit

import pytest

from starup_backend.feed.models import FeedPost
from starup_backend.reviews.services import review_solution
from tests.factories import DemandFactory, StartupFactory
from tests.test_marketplace import delivered_solution

pytestmark = pytest.mark.django_db


def test_feed_author_is_public_profile_not_account_identity(api_client):
    demand = DemandFactory(tags=["logística", "rotas"])
    FeedPost.objects.create(kind="DEMAND", demand=demand)
    startup = StartupFactory()
    FeedPost.objects.create(kind="STARTUP", startup=startup)
    results = api_client.get("/api/v1/feed/").json()["results"]
    authors = {post["kind"]: post for post in results}
    assert authors["DEMAND"]["author_type"] == "CLIENT"
    assert authors["DEMAND"]["author_id"] == str(demand.client_id)
    assert authors["DEMAND"]["author_name"] == demand.client.display_name
    assert authors["DEMAND"]["content"]["tags"] == ["logística", "rotas"]
    assert authors["STARTUP"]["author_type"] == "STARTUP"
    assert authors["STARTUP"]["author_id"] == str(startup.pk)
    assert authors["STARTUP"]["author_name"] == startup.name
    for private in (
        demand.client.user.email,
        str(demand.client.user_id),
        demand.client.document,
        startup.user.email,
        str(startup.user_id),
    ):
        assert private not in str(results)


def test_reviewed_feed_includes_public_demand_context(api_client):
    client, startup, solution = delivered_solution()
    solution.refresh_from_db()
    demand = solution.demand
    demand.tags = ["automação"]
    demand.save(update_fields=["tags"])
    review_solution(actor=client.user, solution_id=solution.pk, rating=3)
    rows = api_client.get("/api/v1/feed/").json()["results"]
    result = next(post for post in rows if post["kind"] == "REVIEWED_SOLUTION")
    assert result["author_id"] == str(startup.pk)
    assert result["author_type"] == "STARTUP"
    content = result["content"]
    assert content["rating"] == 3
    assert content["client_id"] == str(client.pk)
    assert content["client_name"] == client.display_name
    assert content["demand_description"] == demand.description
    assert content["category_name"] == demand.category.name
    assert content["tags"] == ["automação"]
    assert content["images"] == []
    assert solution.proposal not in str(content)
    assert solution.delivery not in str(content)


def test_feed_topic_filter_covers_demand_and_result_and_respects_privacy(api_client):
    client, _, solution = delivered_solution()
    solution.demand.tags = ["rotas"]
    solution.demand.save(update_fields=["tags"])
    review_solution(actor=client.user, solution_id=solution.pk, rating=5)
    FeedPost.objects.create(kind="DEMAND", demand=DemandFactory(tags=["rota"]))
    FeedPost.objects.create(
        kind="DEMAND", demand=DemandFactory(tags=["rotas"], visibility="PRIVATE")
    )
    response = api_client.get("/api/v1/feed/", {"tag": "#ROTAS"})
    assert response.status_code == 200
    assert {post["kind"] for post in response.json()["results"]} == {
        "DEMAND",
        "REVIEWED_SOLUTION",
    }
    assert all(
        post["content"]["tags"] == ["rotas"] for post in response.json()["results"]
    )
    response = api_client.get("/api/v1/feed/", {"tag": "rotas", "kind": "DEMAND"})
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["kind"] == "DEMAND"


def test_feed_type_filter_applies_before_cursor_pagination(api_client):
    for _ in range(24):
        FeedPost.objects.create(kind="DEMAND", demand=DemandFactory())
        FeedPost.objects.create(kind="STARTUP", startup=StartupFactory())
    first = api_client.get("/api/v1/feed/", {"kind": "DEMAND"}).json()
    assert len(first["results"]) == 20
    parsed = urlsplit(first["next"])
    second = api_client.get(parsed.path + "?" + parsed.query).json()
    assert len(second["results"]) == 4
    assert second["next"] is None
    assert all(
        post["kind"] == "DEMAND" for post in first["results"] + second["results"]
    )
    assert not {row["id"] for row in first["results"]} & {
        row["id"] for row in second["results"]
    }


@pytest.mark.parametrize("query", [{"kind": "CLIENT"}, {"tag": "#"}, {"tag": "x" * 31}])
def test_feed_invalid_filters_are_validation_errors(api_client, query):
    response = api_client.get("/api/v1/feed/", query)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_input"


@pytest.mark.django_db(transaction=True)
def test_images_follow_visibility_and_account_erasure(csrf_client, settings, tmp_path):
    import io
    import json

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    from rest_framework.test import APIClient

    from starup_backend.demands.models import DemandImage
    from tests.factories import CategoryFactory, ClientFactory

    settings.MEDIA_ROOT = tmp_path
    owner = ClientFactory()
    category = CategoryFactory()
    csrf_client.force_login(owner.user)
    token = csrf_client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    csrf_client.credentials(HTTP_X_CSRFTOKEN=token)
    source = io.BytesIO()
    Image.new("RGB", (80, 50), color="gold").save(source, format="PNG")
    response = csrf_client.post(
        "/api/v1/demands/",
        {
            "title": "A visual brief",
            "description": "Public context with an image",
            "category_id": str(category.id),
            "tags": json.dumps(["#Rotas", "logística"]),
            "images": [
                SimpleUploadedFile("reference.png", source.getvalue(), "image/png")
            ],
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    content = response.json()
    assert content["tags"] == ["rotas", "logística"]
    url = content["images"][0]["url"]
    assert url.startswith("/api/v1/demand-images/")
    stored = DemandImage.objects.get()
    name, storage = stored.image.name, stored.image.storage
    assert storage.exists(name)
    visitor = APIClient()
    image = visitor.get(url)
    assert image.status_code == 200
    assert image["Content-Type"] == "image/jpeg"
    assert "no-store" in image["Cache-Control"]
    assert b"".join(image.streaming_content)
    image.close()
    feed = visitor.get("/api/v1/feed/", {"tag": "rotas"}).json()["results"]
    assert feed[0]["content"]["images"] == content["images"]
    history_url = f"/api/v1/clients/{owner.pk}/demands/"
    assert visitor.get(history_url).json()["results"][0]["images"] == content["images"]

    response = csrf_client.patch(
        f"/api/v1/demands/{content['id']}/", {"visibility": "PRIVATE"}, format="json"
    )
    assert response.status_code == 200
    assert visitor.get(url).status_code == 404
    assert not visitor.get("/api/v1/feed/", {"tag": "rotas"}).json()["results"]
    assert not visitor.get(history_url).json()["results"]
    owned_image = csrf_client.get(url)
    assert owned_image.status_code == 200
    owned_image.close()
    response = csrf_client.delete("/api/v1/me/")
    assert response.status_code == 204
    assert not DemandImage.objects.exists()
    assert not storage.exists(name)
    assert visitor.get(url).status_code == 404
