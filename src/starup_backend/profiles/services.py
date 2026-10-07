"""Owner-only startup profile updates."""

from typing import Any
from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import NotFound

from starup_backend.accounts.services import require_role
from starup_backend.common.roles import Role
from starup_backend.usuarios.models import Usuario

from .models import StartupProfile


@transaction.atomic
def update_startup(*, actor: Usuario, startup_id: UUID, data: dict[str, Any]) -> None:
    require_role(actor, Role.STARTUP)
    try:
        profile = StartupProfile.objects.select_for_update().get(
            pk=startup_id, user_id=actor.pk
        )
    except StartupProfile.DoesNotExist as exc:
        raise NotFound() from exc
    for field, value in data.items():
        setattr(profile, field, value)
    profile.save()
