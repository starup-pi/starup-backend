"""Erase direct identifiers and withdraw public content without breaking history."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from starup_backend.demands.models import Demand
from starup_backend.profiles.models import (
    ClientProfile,
    InvestorProfile,
    StartupProfile,
)
from starup_backend.solutions.models import Solution, SolutionStatusEvent
from starup_backend.usuarios.models import (
    PerfilEmpresaCliente,
    PerfilEntidadeFomento,
    PerfilInvestidor,
    PerfilStartup,
)


@transaction.atomic
def erase_account(*, actor) -> None:
    user = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if user.is_staff or user.is_superuser:
        raise PermissionDenied()
    demands = list(Demand.objects.select_for_update().filter(client__user_id=user.pk))
    for demand in demands:
        demand.visibility = Demand.Visibility.PRIVATE
        demand.title = "Conteúdo removido"
        demand.description = ""
        demand.save(update_fields=["visibility", "title", "description", "updated_at"])
    # Proposal/delivery text may contain identifiers, including details about clients.
    Solution.objects.filter(demand__client__user_id=user.pk).update(
        proposal="Conteúdo removido", delivery=""
    )
    Solution.objects.filter(startup__user_id=user.pk).update(
        proposal="Conteúdo removido", delivery=""
    )
    ClientProfile.objects.filter(user=user).update(
        document=None, display_name="Conta removida"
    )
    StartupProfile.objects.filter(user=user).update(
        name="Startup removida", description="", website="", category=""
    )
    InvestorProfile.objects.filter(user=user).delete()
    # Original profiles remain during migration, so erasure must cover them too.
    PerfilStartup.objects.filter(usuario=user).update(
        cnpj=None, website=None, pitch_resumido="", nome_startup="Startup removida"
    )
    PerfilEmpresaCliente.objects.filter(usuario=user).delete()
    PerfilInvestidor.objects.filter(usuario=user).delete()
    PerfilEntidadeFomento.objects.filter(usuario=user).delete()
    user.push_subscriptions.all().delete()
    user.push_messages.all().delete()
    user.consents.all().delete()
    SolutionStatusEvent.objects.filter(actor=user).update(actor=None)
    user.email = f"{user.pk}@deleted.invalid"
    user.nome_civil = ""
    user.telefone = None
    user.ativo = False
    user.termo_privacidade_aceito = False
    user.set_unusable_password()
    user.atualizado_em = timezone.now()
    user.save()
