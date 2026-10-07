"""Explicit registration and role checks over the existing user model."""

from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from starup_backend.common.roles import REGISTRATION_ROLES, Role
from starup_backend.feed.models import FeedPost
from starup_backend.privacy.models import ConsentRecord
from starup_backend.profiles.models import (
    ClientProfile,
    InvestorProfile,
    StartupProfile,
)
from starup_backend.usuarios.models import Usuario


def require_role(actor: Usuario, role: Role) -> None:
    if not actor.is_authenticated:
        raise PermissionDenied()
    current = (
        get_user_model()
        .objects.select_for_update()
        .filter(pk=actor.pk, ativo=True, perfil_ativo=role)
        .exists()
    )
    if not current:
        raise PermissionDenied()


def register_account(*, data: dict[str, Any]) -> None:
    """Duplicate identity returns the same public outcome as successful registration."""
    role = REGISTRATION_ROLES[data["role"]]
    User = get_user_model()
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=data["email"].strip().lower(),
                password=data["password"],
                nome_civil=data.get("legal_name", ""),
                perfil_ativo=role,
                termo_privacidade_aceito=True,
                data_aceite_termos=timezone.now(),
            )
            if role == Role.CLIENT:
                profile = ClientProfile(
                    user=user,
                    person_type=data["person_type"],
                    document=data["document"],
                    display_name=data["display_name"],
                )
                profile.full_clean(validate_unique=False)
                profile.save()
            elif role == Role.STARTUP:
                profile = StartupProfile.objects.create(
                    user=user,
                    name=data["startup_name"],
                    description=data.get("description", ""),
                    website=data.get("website", ""),
                )
                FeedPost.objects.create(kind=FeedPost.Kind.STARTUP, startup=profile)
            else:
                InvestorProfile.objects.create(user=user)
            ConsentRecord.objects.create(
                user=user,
                purpose=ConsentRecord.Purpose.POLICY_ACKNOWLEDGEMENT,
                policy_version=settings.PRIVACY_POLICY_VERSION,
            )
    except IntegrityError:
        return
