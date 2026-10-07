"""Known CPF/CNPJ cases, normalization and database uniqueness."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from starup_backend.accounts.serializers import RegistrationSerializer
from starup_backend.profiles.models import ClientProfile
from starup_backend.profiles.validators import (
    normalize_document,
    validate_cnpj,
    validate_cpf,
)
from tests.factories import ClientFactory, UserFactory


@pytest.mark.parametrize("value", ["52998224725", "11144477735"])
def test_valid_cpf(value):
    validate_cpf(value)


@pytest.mark.parametrize(
    "value",
    [
        "00000000000",
        "11111111111",
        "52998224724",
        "１２３４５６７８９００",
        "5299822472",
    ],
)
def test_invalid_cpf(value):
    with pytest.raises(ValidationError):
        validate_cpf(value)


@pytest.mark.parametrize(
    "value", ["11222333000181", "12ABC34501DE35", "00000000E08G12"]
)
def test_valid_cnpj(value):
    validate_cnpj(value)


@pytest.mark.parametrize(
    "value", ["00000000000000", "12ABC34501DE34", "11222333000180", "12abc34501DE35"]
)
def test_invalid_cnpj(value):
    with pytest.raises(ValidationError):
        validate_cnpj(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("529.982.247-25", "52998224725"),
        ("12.abc.345/01de-35", "12ABC34501DE35"),
        ("11.222.333/0001-81", "11222333000181"),
    ],
)
def test_normalization(value, expected):
    assert normalize_document(value) == expected


@pytest.mark.parametrize(
    "value", ["52998224725<script>", "529_982_247_25", "12ＡBC34501DE35"]
)
def test_normalization_rejects_invalid_characters(value):
    with pytest.raises(ValidationError):
        normalize_document(value)


@pytest.mark.django_db
def test_canonical_document_unique():
    first = ClientFactory(document="52998224725")
    with pytest.raises(IntegrityError), transaction.atomic():
        ClientFactory(document=first.document)


@pytest.mark.django_db
def test_document_shape_constraint():
    with pytest.raises(IntegrityError), transaction.atomic():
        ClientProfile.objects.create(
            user=UserFactory(),
            person_type="PF",
            document="12ABC34501DE35",
            display_name="Bad",
        )


@pytest.mark.django_db
def test_model_clean_normalizes_and_checks_person_type():
    client = ClientFactory.build(document="529.982.247-25", user=UserFactory())
    client.full_clean()
    assert client.document == "52998224725"
    client.person_type = "PJ"
    with pytest.raises(ValidationError):
        client.clean()


@pytest.mark.django_db
def test_active_client_cannot_validate_erased_document():
    client = ClientFactory()
    client.document = None
    with pytest.raises(ValidationError):
        client.clean()


@pytest.mark.django_db
def test_registration_rejects_wrong_person_type():
    serializer = RegistrationSerializer(
        data={
            "email": "new@example.test",
            "password": "Strong-Password-42!",
            "role": "CLIENT",
            "policy_version": "2026-10",
            "person_type": "PF",
            "document": "12ABC34501DE35",
            "display_name": "Client",
        }
    )
    assert not serializer.is_valid()
    assert "document" in serializer.errors
