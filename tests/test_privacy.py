"""Investor identity isolation, erasure and public projection boundaries."""

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from starup_backend.common.roles import Role
from starup_backend.feed.models import FeedPost
from starup_backend.privacy.services import erase_account
from starup_backend.profiles.models import InvestorProfile, StartupProfile
from starup_backend.usuarios.models import PerfilInvestidor
from tests.factories import (
    ClientFactory,
    DemandFactory,
    InvestorFactory,
    StartupFactory,
    UserFactory,
)
from tests.test_marketplace import delivered_solution

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("actor_role", [None, Role.CLIENT, Role.STARTUP, Role.INVESTOR])
def test_investor_identity_never_appears_in_public_content(api_client, actor_role):
    investor = InvestorFactory(
        user__email="secret-investor@example.test",
        user__nome_civil="Secret Investor Civil Name",
    )
    # Even malformed legacy role/profile combinations must never become public.
    startup = StartupProfile.objects.create(
        user=investor.user,
        name="Sensitive Investor Startup",
        description="Sensitive institution",
    )
    FeedPost.objects.create(kind="STARTUP", startup=startup)
    visible = StartupFactory()
    FeedPost.objects.create(kind="STARTUP", startup=visible)
    demand = DemandFactory()
    FeedPost.objects.create(kind="DEMAND", demand=demand)
    if actor_role:
        api_client.force_authenticate(UserFactory(perfil_ativo=actor_role))
    for path in ("/api/v1/feed/", "/api/v1/startups/", "/api/v1/demands/"):
        response = api_client.get(path)
        assert response.status_code == 200
        text = response.content.decode()
        for secret in (
            investor.user.email,
            investor.user.nome_civil,
            investor.alias,
            str(investor.user.pk),
            "Sensitive Investor Startup",
            "Sensitive institution",
        ):
            assert secret not in text
    assert api_client.get(f"/api/v1/startups/{startup.id}/").status_code == 404


def test_public_queries_do_not_select_identity_columns(api_client):
    investor = InvestorFactory()
    startup = StartupFactory()
    FeedPost.objects.create(kind="STARTUP", startup=startup)
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get("/api/v1/feed/")
    assert response.status_code == 200
    for query in queries:
        selected = query["sql"].split(" FROM ")[0].lower()
        for column in (
            '"email"',
            '"nome_civil"',
            '"telefone"',
            '"document"',
            '"alias"',
            '"password"',
        ):
            assert column not in selected
    assert investor.user.email not in response.content.decode()


@pytest.mark.parametrize(
    "method, path, data",
    [
        ("post", "/api/v1/demands/", {}),
        ("post", "/api/v1/solutions/", {}),
        ("post", "/api/v1/reviews/", {}),
        (
            "patch",
            "/api/v1/my-startups/00000000-0000-0000-0000-000000000001/",
            {"name": "Revealed"},
        ),
    ],
)
def test_investor_cannot_create_identifying_domain_content(
    api_client, method, path, data
):
    api_client.force_authenticate(InvestorFactory().user)
    assert getattr(api_client, method)(path, data, format="json").status_code == 403


def test_private_cache_headers(api_client):
    investor = InvestorFactory()
    api_client.force_authenticate(investor.user)
    for path in ("/api/v1/me/", "/api/v1/push/config/"):
        assert "no-store" in api_client.get(path)["Cache-Control"]
    assert "public" in api_client.get("/api/v1/feed/")["Cache-Control"]


def test_user_string_never_includes_identity():
    investor = InvestorFactory()
    assert investor.user.email not in str(investor.user)
    assert investor.user.nome_civil not in str(investor.user)


def test_investor_erasure_covers_legacy_profile_and_sessions(csrf_client):
    investor = InvestorFactory()
    user = investor.user
    legacy = PerfilInvestidor.objects.create(
        usuario=user,
        tipo_investidor="ANJO",
        instituicao_origem="Private fund",
        cargo_funcao="Private position",
    )
    response = csrf_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "Strong-Password-42!"},
        format="json",
    )
    csrf_client.credentials(HTTP_X_CSRFTOKEN=response.json()["csrf_token"])
    assert csrf_client.delete("/api/v1/me/").status_code == 204
    user.refresh_from_db()
    assert not user.ativo
    assert not user.has_usable_password()
    assert user.nome_civil == ""
    assert user.email.endswith("@deleted.invalid")
    assert not PerfilInvestidor.objects.filter(pk=legacy.pk).exists()
    assert not user.consents.exists()
    assert not InvestorProfile.objects.filter(user=user).exists()
    assert csrf_client.get("/api/v1/me/").status_code == 403


def test_client_erasure_scrubs_history_text_and_withdraws_feed(api_client):
    client, _, solution = delivered_solution()
    from starup_backend.reviews.services import review_solution

    review_solution(actor=client.user, solution_id=solution.pk, rating=5)
    original_document = client.document
    erase_account(actor=client.user)
    client.refresh_from_db()
    solution.refresh_from_db()
    solution.demand.refresh_from_db()
    assert client.document is None
    assert solution.proposal == "Conteúdo removido"
    assert solution.delivery == ""
    assert solution.demand.visibility == "PRIVATE"
    assert not api_client.get("/api/v1/feed/").json()["results"]
    assert original_document not in json.dumps(
        api_client.get("/api/v1/startups/").json()
    )
    assert solution.review.rating == 5


def test_erased_user_cannot_authenticate_other_existing_session(api_client):
    client = ClientFactory()
    api_client.force_login(client.user)
    erase_account(actor=client.user)
    assert api_client.get("/api/v1/me/").status_code == 403


def test_erased_startup_is_not_public(api_client):
    startup = StartupFactory()
    FeedPost.objects.create(kind="STARTUP", startup=startup)
    erase_account(actor=startup.user)
    assert api_client.get(f"/api/v1/startups/{startup.pk}/").status_code == 404
    assert not api_client.get("/api/v1/feed/").json()["results"]


def test_unknown_identity_filters_cannot_reveal_investors(api_client):
    investor = InvestorFactory()
    response = api_client.get(
        "/api/v1/startups/",
        {"search": investor.user.email, "ordering": "user__email", "role": "INVESTOR"},
    )
    assert response.status_code == 200
    assert response.json()["results"] == []
