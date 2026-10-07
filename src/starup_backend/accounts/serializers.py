"""Private account input and representation are separate from public profiles."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from starup_backend.common.roles import REGISTRATION_ROLES, ROLE_NAMES
from starup_backend.common.serializers import StrictSerializer
from starup_backend.profiles.validators import (
    normalize_document,
    validate_cnpj,
    validate_cpf,
)


class RegistrationSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )
    role = serializers.ChoiceField(choices=list(REGISTRATION_ROLES))
    policy_version = serializers.CharField(max_length=32)
    legal_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    person_type = serializers.ChoiceField(choices=["PF", "PJ"], required=False)
    document = serializers.CharField(max_length=32, required=False)
    display_name = serializers.CharField(max_length=120, required=False)
    startup_name = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(
        max_length=300, required=False, allow_blank=True
    )
    website = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["policy_version"] != settings.PRIVACY_POLICY_VERSION:
            raise serializers.ValidationError({"policy_version": "Versão inválida."})
        user = get_user_model()(
            email=attrs["email"], nome_civil=attrs.get("legal_name", "")
        )
        try:
            validate_password(attrs["password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        role_fields = {
            "CLIENT": {"person_type", "document", "display_name", "legal_name"},
            "STARTUP": {"startup_name", "description", "website", "legal_name"},
            "INVESTOR": set(),
        }
        supplied_profile = set(attrs) - {"email", "password", "role", "policy_version"}
        if supplied_profile - role_fields[attrs["role"]]:
            raise serializers.ValidationError("Campos incompatíveis com o papel.")
        required = {
            "CLIENT": {"person_type", "document", "display_name"},
            "STARTUP": {"startup_name"},
            "INVESTOR": set(),
        }[attrs["role"]]
        if missing := required - set(attrs):
            raise serializers.ValidationError(
                {name: "Campo obrigatório." for name in missing}
            )
        if attrs["role"] == "CLIENT":
            try:
                document = normalize_document(attrs["document"])
                validator = (
                    validate_cpf if attrs["person_type"] == "PF" else validate_cnpj
                )
                validator(document)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"document": exc.messages}) from exc
            attrs["document"] = document
        return attrs


class LoginSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class CsrfSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()
    policy_version = serializers.CharField(required=False)


class PrivateAccountSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    role = serializers.CharField()
    legal_name = serializers.CharField()
    profile = serializers.DictField()


def private_account(user) -> dict:
    profile = {}
    if hasattr(user, "client_profile"):
        client = user.client_profile
        profile = {
            "person_type": client.person_type,
            "document": client.document,
            "display_name": client.display_name,
        }
    elif hasattr(user, "startup_profile"):
        startup = user.startup_profile
        profile = {
            "id": str(startup.id),
            "name": startup.name,
            "description": startup.description,
            "website": startup.website,
        }
    elif hasattr(user, "investor_profile"):
        profile = {"alias": user.investor_profile.alias}
    return {
        "id": user.id,
        "email": user.email,
        "role": ROLE_NAMES.get(user.perfil_ativo, "INTERNAL"),
        "legal_name": user.nome_civil,
        "profile": profile,
    }
