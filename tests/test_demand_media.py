"""Demand tags, verified images, access controls, and storage compensation."""

from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, PngImagePlugin

from starup_backend.demands.media import MAX_IMAGE_BYTES, prepare_image, remove_images
from starup_backend.demands.models import Demand, DemandImage
from starup_backend.demands.selectors import demand_projection
from starup_backend.demands.serializers import DemandSerializer, DemandWriteSerializer
from starup_backend.demands.services import create_demand, update_demand
from starup_backend.feed.models import FeedPost
from starup_backend.reviews.models import Review
from tests.factories import (
    CategoryFactory,
    ClientFactory,
    DemandFactory,
    SolutionFactory,
    StartupFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def temporary_media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")


def upload(*, name="evidence.png", image_format="PNG", mode="RGB", metadata=False):
    output = BytesIO()
    kwargs = {}
    if metadata and image_format == "PNG":
        info = PngImagePlugin.PngInfo()
        info.add_text("Author", "Private camera owner")
        kwargs["pnginfo"] = info
    if metadata and image_format == "JPEG":
        exif = Image.Exif()
        exif[315] = "Private camera owner"
        kwargs["exif"] = exif
    Image.new(mode, (40, 24), "red").save(output, format=image_format, **kwargs)
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def payload(**extra):
    return {
        "title": "Improve operations",
        "description": "A public problem with supporting evidence",
        "category_id": str(CategoryFactory().id),
        **extra,
    }


def create_with_images(api_client, *, count=1, visibility="PUBLIC"):
    owner = ClientFactory()
    api_client.force_authenticate(owner.user)
    response = api_client.post(
        "/api/v1/demands/",
        payload(images=[upload() for _ in range(count)], visibility=visibility),
        format="multipart",
    )
    assert response.status_code == 201, response.content
    return owner, response.json()


def stored_files(settings):
    return [path for path in Path(settings.MEDIA_ROOT).rglob("*") if path.is_file()]


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP", "GIF"])
def test_verified_rasters_are_reencoded_without_metadata(image_format):
    source = upload(image_format=image_format, metadata=True)
    result = prepare_image(source)
    with Image.open(result) as decoded:
        assert decoded.format in {"PNG", "JPEG"}
        assert decoded.size == (40, 24)
        assert not decoded.getexif()
        assert "Author" not in decoded.info
    assert b"Private camera owner" not in result.read()
    assert result.name != source.name
    assert result.content_type in {"image/png", "image/jpeg"}


def test_transparency_is_preserved_in_sanitized_png():
    image = prepare_image(upload(mode="RGBA"))
    assert image.content_type == "image/png"
    with Image.open(image) as decoded:
        assert decoded.mode == "RGBA"


@pytest.mark.parametrize(
    "data",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"not an image",
        b"\xff\xd8\xff\xe0corrupt-jpeg",
    ],
)
def test_invalid_or_active_content_is_rejected(api_client, data, settings):
    api_client.force_authenticate(ClientFactory().user)
    response = api_client.post(
        "/api/v1/demands/",
        payload(
            images=[SimpleUploadedFile("photo.png", data, content_type="image/png")]
        ),
        format="multipart",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_input"
    assert "images" in response.json()["fields"]
    assert not Demand.objects.exists()
    assert not stored_files(settings)


def test_image_limit_applies_before_decoding(api_client):
    api_client.force_authenticate(ClientFactory().user)
    oversized = SimpleUploadedFile("huge.png", b"x" * (MAX_IMAGE_BYTES + 1))
    response = api_client.post(
        "/api/v1/demands/", payload(images=[oversized]), format="multipart"
    )
    assert response.status_code == 400
    assert "images" in response.json()["fields"]


def test_png_with_invalid_chunk_checksum_returns_validation_error(api_client):
    source = upload()
    corrupt = bytearray(source.read())
    chunk = corrupt.index(b"IDAT")
    length = int.from_bytes(corrupt[chunk - 4 : chunk], "big")
    corrupt[chunk + 4 + length] ^= 1
    api_client.force_authenticate(ClientFactory().user)
    response = api_client.post(
        "/api/v1/demands/",
        payload(images=[SimpleUploadedFile("corrupt.png", bytes(corrupt))]),
        format="multipart",
    )
    assert response.status_code == 400
    assert "images" in response.json()["fields"]
    assert not Demand.objects.exists()


def test_image_dimensions_are_bounded():
    with patch("starup_backend.demands.media.MAX_IMAGE_PIXELS", 10):
        serializer = DemandWriteSerializer(data=payload(images=[upload()]))
        assert not serializer.is_valid()
        assert "images" in serializer.errors


@pytest.mark.parametrize(
    "tags",
    [[""], ["#"], ["inside#tag"], ["a" * 31], [str(i) for i in range(9)], "not-a-list"],
)
def test_invalid_tags_are_rejected(api_client, tags):
    api_client.force_authenticate(ClientFactory().user)
    response = api_client.post("/api/v1/demands/", payload(tags=tags), format="json")
    assert response.status_code == 400
    assert "tags" in response.json()["fields"]
    assert not Demand.objects.exists()


def test_json_tags_are_canonicalized_and_publication_remains_compatible(api_client):
    owner = ClientFactory()
    api_client.force_authenticate(owner.user)
    response = api_client.post(
        "/api/v1/demands/",
        payload(tags=[" #Logística ", "LOGÍSTICA", "dados"]),
        format="json",
    )
    assert response.status_code == 201
    result = response.json()
    assert result["tags"] == ["logística", "dados"]
    assert result["images"] == []
    assert result["client_id"] == str(owner.id)
    assert result["client_name"] == owner.display_name
    assert result["rating"] is None
    assert result["selected_startup_id"] is None
    assert FeedPost.objects.filter(demand_id=result["id"]).exists()
    assert "Private legal name" not in str(result)


def test_multipart_repeated_tags_and_image_urls(api_client, settings):
    owner = ClientFactory()
    api_client.force_authenticate(owner.user)
    response = api_client.post(
        "/api/v1/demands/",
        payload(tags=["#processos", "DADOS"], images=[upload(metadata=True), upload()]),
        format="multipart",
    )
    assert response.status_code == 201, response.content
    result = response.json()
    assert result["tags"] == ["processos", "dados"]
    assert len(result["images"]) == 2
    assert len(stored_files(settings)) == 2
    assert len({image["id"] for image in result["images"]}) == 2
    for image in result["images"]:
        assert image["url"] == f"/api/v1/demand-images/{image['id']}/"
    api_client.force_authenticate(None)
    response = api_client.get(result["images"][0]["url"])
    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in response["Cache-Control"]
    content = b"".join(response.streaming_content)
    assert b"Private camera owner" not in content
    with Image.open(BytesIO(content)) as decoded:
        assert decoded.format == "JPEG"


def test_private_images_retain_existing_demand_access_rules(api_client):
    owner, demand = create_with_images(api_client, visibility="PRIVATE")
    image_url = demand["images"][0]["url"]
    outsider = StartupFactory()
    for actor in (None, ClientFactory().user, outsider.user):
        api_client.force_authenticate(actor)
        assert api_client.get(image_url).status_code == 404
    selected = SolutionFactory(demand_id=demand["id"], status="ACCEPTED")
    for actor in (owner.user, selected.startup.user):
        api_client.force_authenticate(actor)
        response = api_client.get(image_url)
        assert response.status_code == 200
        assert b"".join(response.streaming_content)
    owner.user.ativo = False
    owner.user.save(update_fields=["ativo"])
    api_client.force_authenticate(None)
    assert api_client.get(image_url).status_code == 404


def test_images_are_retained_by_default_and_append_in_order(api_client):
    _, demand = create_with_images(api_client, count=2)
    response = api_client.patch(
        f"/api/v1/demands/{demand['id']}/", {"images": [upload()]}, format="multipart"
    )
    assert response.status_code == 200
    images = response.json()["images"]
    assert images[:2] == demand["images"]
    assert len(images) == 3
    assert list(DemandImage.objects.values_list("ordering", flat=True)) == [0, 1, 2]


def test_keep_ids_allow_replacement_and_clear_after_commit(
    api_client, django_capture_on_commit_callbacks, settings
):
    _, demand = create_with_images(api_client, count=2)
    old_files = set(stored_files(settings))
    keep_id = demand["images"][1]["id"]
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.patch(
            f"/api/v1/demands/{demand['id']}/",
            {"keep_image_ids": [keep_id], "images": [upload()]},
            format="multipart",
        )
    assert response.status_code == 200
    assert response.json()["images"][0]["id"] == keep_id
    assert len(response.json()["images"]) == 2
    assert len(old_files & set(stored_files(settings))) == 1
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        response = api_client.patch(
            f"/api/v1/demands/{demand['id']}/",
            {"keep_image_ids": "[]", "tags": "[]"},
            format="multipart",
        )
    assert response.status_code == 200
    assert response.json()["images"] == response.json()["tags"] == []
    assert not DemandImage.objects.exists()
    assert len(stored_files(settings)) == 2
    for callback in callbacks:
        callback()
    assert not stored_files(settings)


def test_max_four_applies_to_retained_and_new_images(api_client, settings):
    _, demand = create_with_images(api_client, count=4)
    response = api_client.patch(
        f"/api/v1/demands/{demand['id']}/", {"images": [upload()]}, format="multipart"
    )
    assert response.status_code == 400
    assert len(stored_files(settings)) == DemandImage.objects.count() == 4
    serializer = DemandWriteSerializer(
        data=payload(images=[upload() for _ in range(5)])
    )
    assert not serializer.is_valid()
    assert "images" in serializer.errors


def test_keep_ids_cannot_reference_other_demand_or_repeat(api_client):
    owner, first = create_with_images(api_client)
    _, other = create_with_images(api_client)
    api_client.force_authenticate(owner.user)
    for ids in ([other["images"][0]["id"]], [first["images"][0]["id"]] * 2):
        response = api_client.patch(
            f"/api/v1/demands/{first['id']}/", {"keep_image_ids": ids}, format="json"
        )
        assert response.status_code == 400
    assert DemandImage.objects.count() == 2


def test_completed_demand_images_and_tags_are_frozen(api_client):
    _, demand = create_with_images(api_client)
    Demand.objects.filter(pk=demand["id"]).update(status="IN_PROGRESS")
    for data, format in (
        ({"tags": ["new"]}, "json"),
        ({"images": [upload()]}, "multipart"),
    ):
        response = api_client.patch(
            f"/api/v1/demands/{demand['id']}/", data, format=format
        )
        assert response.status_code == 409
    assert DemandImage.objects.count() == 1


def test_failed_creation_removes_files_and_rolls_back_database(settings):
    owner = ClientFactory()
    category = CategoryFactory()
    with patch(
        "starup_backend.demands.services.FeedPost.objects.create",
        side_effect=RuntimeError("feed failure"),
    ):
        with pytest.raises(RuntimeError, match="feed failure"):
            create_demand(
                actor=owner.user,
                data={
                    "title": "Problem",
                    "description": "Context",
                    "category": category,
                    "images": [prepare_image(upload())],
                },
            )
    assert not Demand.objects.exists()
    assert not DemandImage.objects.exists()
    assert not stored_files(settings)


def test_failed_replacement_preserves_old_images_and_removes_new(api_client, settings):
    owner, demand = create_with_images(api_client)
    files = stored_files(settings)
    with patch(
        "starup_backend.demands.services.FeedPost.objects.get_or_create",
        side_effect=RuntimeError("feed failure"),
    ):
        with pytest.raises(RuntimeError, match="feed failure"):
            update_demand(
                actor=owner.user,
                demand_id=demand["id"],
                data={"keep_image_ids": [], "images": [prepare_image(upload())]},
            )
    assert stored_files(settings) == files
    assert DemandImage.objects.count() == 1
    assert str(DemandImage.objects.get().id) == demand["images"][0]["id"]


def test_uploads_reject_enclosing_transaction_before_writing_files(settings):
    owner, category = ClientFactory(), CategoryFactory()
    with transaction.atomic(), pytest.raises(RuntimeError, match="durable atomic"):
        create_demand(
            actor=owner.user,
            data={
                "title": "Problem",
                "description": "Context",
                "category": category,
                "images": [prepare_image(upload())],
            },
        )
    assert not Demand.objects.exists()
    assert not stored_files(settings)


def test_removed_file_is_preserved_when_transaction_rolls_back(api_client, settings):
    _, demand = create_with_images(api_client)
    files = stored_files(settings)
    with pytest.raises(RuntimeError, match="rollback"):
        with transaction.atomic():
            remove_images(DemandImage.objects.filter(demand_id=demand["id"]))
            raise RuntimeError("rollback")
    assert DemandImage.objects.count() == 1
    assert stored_files(settings) == files


def test_demand_projection_ratings_and_selected_startup_are_public_only():
    solution = SolutionFactory(
        status="COMPLETED",
        demand__status="COMPLETED",
        demand__completed_at=timezone.now(),
    )
    Review.objects.create(solution=solution, rating=5)
    result = DemandSerializer(
        demand_projection(AnonymousUser()).get(id=solution.demand_id)
    ).data
    assert result["rating"] == 5
    assert result["selected_startup_id"] == str(solution.startup_id)
    assert result["selected_startup_name"] == solution.startup.name
    solution.startup.user.ativo = False
    solution.startup.user.save(update_fields=["ativo"])
    result = DemandSerializer(
        demand_projection(AnonymousUser()).get(id=solution.demand_id)
    ).data
    assert (
        result["selected_startup_id"]
        is result["selected_startup_name"]
        is result["rating"]
        is None
    )


def test_image_enriched_projection_has_constant_query_count(django_assert_num_queries):
    for _ in range(4):
        DemandFactory()
    with django_assert_num_queries(1):
        result = list(
            DemandSerializer(demand_projection(AnonymousUser()), many=True).data
        )
    assert len(result) == 4
    assert all(row["images"] == [] for row in result)


def test_missing_image_returns_scoped_not_found(api_client):
    response = api_client.get(f"/api/v1/demand-images/{uuid4()}/")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_session_multipart_upload_and_removal_commit_normally(csrf_client, settings):
    owner = ClientFactory()
    response = csrf_client.post(
        "/api/v1/auth/login/",
        {"email": owner.user.email, "password": "Strong-Password-42!"},
        format="json",
    )
    assert response.status_code == 200
    csrf_client.credentials(HTTP_X_CSRFTOKEN=response.json()["csrf_token"])
    response = csrf_client.post(
        "/api/v1/demands/", payload(images=[upload()]), format="multipart"
    )
    assert response.status_code == 201, response.content
    demand = response.json()
    assert DemandImage.objects.filter(demand_id=demand["id"]).count() == 1
    assert len(stored_files(settings)) == 1
    response = csrf_client.patch(
        f"/api/v1/demands/{demand['id']}/",
        {"keep_image_ids": "[]"},
        format="multipart",
    )
    assert response.status_code == 200
    assert response.json()["images"] == []
    assert not stored_files(settings)
