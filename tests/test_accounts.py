"""Session authentication, CSRF, role immutability and private identity."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from nexora_backend.accounts.serializers import RegistrationSerializer
from nexora_backend.profiles.models import InvestorProfile
from tests.factories import ClientFactory, InvestorFactory, StartupFactory, UserFactory

pytestmark = pytest.mark.django_db


def registration(**overrides):
    return {
        "email": "investor@example.test",
        "password": "Strong-Password-42!",
        "role": "INVESTOR",
        "policy_version": "2026-10",
        **overrides,
    }


def test_investor_registration_is_minimal_and_private(csrf_client):
    response = csrf_client.post("/api/v1/auth/register/", registration(), format="json")
    assert response.status_code == 202
    user = get_user_model().objects.get(email="investor@example.test")
    assert user.nome_civil == ""
    assert not hasattr(user, "client_profile")
    assert InvestorProfile.objects.filter(user=user).exists()
    assert user.consents.get().purpose == "POLICY_ACKNOWLEDGEMENT"
    assert user.check_password("Strong-Password-42!")
    assert csrf_client.get("/api/v1/me/").status_code == 403


@pytest.mark.parametrize(
    "role, extra",
    [
        (
            "CLIENT",
            {
                "person_type": "PF",
                "document": "529.982.247-25",
                "display_name": "Client",
            },
        ),
        (
            "CLIENT",
            {
                "person_type": "PJ",
                "document": "12.abc.345/01de-35",
                "display_name": "Company",
            },
        ),
        ("STARTUP", {"startup_name": "New Startup", "website": "https://example.test"}),
    ],
)
def test_registration_creates_matching_profile(csrf_client, role, extra):
    response = csrf_client.post(
        "/api/v1/auth/register/", registration(role=role, **extra), format="json"
    )
    assert response.status_code == 202
    user = get_user_model().objects.get(email="investor@example.test")
    profile = user.startup_profile if role == "STARTUP" else user.client_profile
    assert profile.user_id == user.pk


def test_duplicate_email_has_identical_public_response(csrf_client):
    first = csrf_client.post("/api/v1/auth/register/", registration(), format="json")
    second = csrf_client.post("/api/v1/auth/register/", registration(), format="json")
    assert (first.status_code, first.json()) == (second.status_code, second.json())
    assert get_user_model().objects.count() == 1


def test_duplicate_document_has_identical_public_response(csrf_client):
    data = registration(
        role="CLIENT", person_type="PF", document="52998224725", display_name="Client"
    )
    first = csrf_client.post("/api/v1/auth/register/", data, format="json")
    second = csrf_client.post(
        "/api/v1/auth/register/",
        {**data, "email": "other@example.test", "document": "529.982.247-25"},
        format="json",
    )
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert get_user_model().objects.count() == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"is_superuser": True},
        {"is_staff": True},
        {"id": "spoof"},
        {"legal_name": "Investor Name"},
        {"confidencialidade_ativa": False},
    ],
)
def test_registration_rejects_mass_assignment(csrf_client, extra):
    assert (
        csrf_client.post(
            "/api/v1/auth/register/", registration(**extra), format="json"
        ).status_code
        == 400
    )
    assert not get_user_model().objects.exists()


@pytest.mark.parametrize("role", ["ADMIN", "ENTIDADE_FOMENTO", "unknown"])
def test_internal_roles_cannot_register(csrf_client, role):
    assert (
        csrf_client.post(
            "/api/v1/auth/register/", registration(role=role), format="json"
        ).status_code
        == 400
    )


def test_weak_password_and_wrong_policy_are_rejected():
    serializer = RegistrationSerializer(data=registration(password="12345678"))
    assert not serializer.is_valid()
    serializer = RegistrationSerializer(data=registration(policy_version="old"))
    assert not serializer.is_valid()


def test_login_and_register_require_csrf():
    client = APIClient(enforce_csrf_checks=True)
    for path in ("login", "register"):
        response = client.post(f"/api/v1/auth/{path}/", registration(), format="json")
        assert response.status_code == 403
        assert response.json()["code"] == "csrf_failed"


def test_login_rotates_csrf_and_session_is_private(csrf_client):
    investor = InvestorFactory()
    response = csrf_client.post(
        "/api/v1/auth/login/",
        {"email": investor.user.email, "password": "Strong-Password-42!"},
        format="json",
    )
    assert response.status_code == 200
    csrf_client.credentials(HTTP_X_CSRFTOKEN=response.json()["csrf_token"])
    me = csrf_client.get("/api/v1/me/")
    assert me.json()["profile"]["alias"] == investor.alias
    assert "no-store" in me["Cache-Control"]
    assert csrf_client.cookies["sessionid"]["httponly"]
    assert csrf_client.post("/api/v1/auth/logout/").status_code == 204
    assert csrf_client.get("/api/v1/me/").status_code == 403


def test_legacy_mixed_case_email_can_authenticate(csrf_client):
    user = UserFactory(email="Mixed@Example.Test")
    response = csrf_client.post(
        "/api/v1/auth/login/",
        {"email": "mixed@example.test", "password": "Strong-Password-42!"},
        format="json",
    )
    assert response.status_code == 200
    assert csrf_client.get("/api/v1/me/").json()["id"] == str(user.pk)


def test_email_unique_without_case():
    UserFactory(email="Mixed@Example.Test")
    with pytest.raises(IntegrityError), transaction.atomic():
        UserFactory(email="mixed@example.test")


def test_bad_login_is_generic(csrf_client):
    investor = InvestorFactory()
    bad = csrf_client.post(
        "/api/v1/auth/login/",
        {"email": investor.user.email, "password": "bad"},
        format="json",
    )
    unknown = csrf_client.post(
        "/api/v1/auth/login/",
        {"email": "unknown@example.test", "password": "bad"},
        format="json",
    )
    assert bad.status_code == unknown.status_code == 403
    assert bad.json()["message"] == unknown.json()["message"]
    assert investor.user.email not in bad.content.decode()


def test_auth_rate_limit(csrf_client):
    statuses = [
        csrf_client.post(
            "/api/v1/auth/login/",
            {"email": "unknown@example.test", "password": "bad"},
            format="json",
        ).status_code
        for _ in range(11)
    ]
    assert statuses[-1] == 429


def test_create_user_rejects_privileged_flags():
    with pytest.raises(ValueError):
        get_user_model().objects.create_user("bad@example.test", is_staff=True)


def test_create_superuser_uses_manager():
    user = get_user_model().objects.create_superuser(
        "Admin@Example.test", "Strong-Password-42!"
    )
    assert user.is_superuser and user.is_staff
    assert user.email == "admin@example.test"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/usuarios/",
        "/api/v1/perfis-investidor/",
        "/api/v1/perfis-startup/",
        "/perfis-investidor/",
        "/usuarios/",
    ],
)
def test_legacy_identity_routes_removed(api_client, path):
    InvestorFactory()
    assert api_client.get(path).status_code == 404


def test_identity_cannot_be_modified_by_me(api_client):
    client = ClientFactory()
    api_client.force_authenticate(client.user)
    assert (
        api_client.patch("/api/v1/me/", {"role": "STARTUP"}, format="json").status_code
        == 405
    )


def test_private_profiles_are_separate(api_client):
    investor = InvestorFactory()
    other = StartupFactory()
    api_client.force_authenticate(other.user)
    body = api_client.get("/api/v1/me/").json()
    assert investor.user.email not in str(body)
    assert investor.alias not in str(body)
