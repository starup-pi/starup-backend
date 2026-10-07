"""Exercise legacy data imports and rollback against historical model states."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def old_state():
    executor = MigrationExecutor(connection)
    executor.migrate([("profiles", "0001_initial")])
    return executor.loader.project_state([("profiles", "0001_initial")]).apps


def restore():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def legacy_user(apps, role, email):
    return apps.get_model("usuarios", "Usuario").objects.create(
        email=email,
        nome_civil="Legacy identity",
        perfil_ativo=role,
    )


def test_legacy_copy_preserves_originals_and_reverse_removes_only_imports():
    apps = old_state()
    try:
        client_user = legacy_user(apps, "EMPRESA_CLIENTE", "legacy-client@example.test")
        startup_user = legacy_user(apps, "STARTUP", "legacy-startup@example.test")
        investor_user = legacy_user(apps, "INVESTIDOR", "legacy-investor@example.test")
        old_client = apps.get_model("usuarios", "PerfilEmpresaCliente").objects.create(
            usuario=client_user,
            cnpj="11.222.333/0001-81",
            nome_fantasia="Legacy Client",
        )
        old_startup = apps.get_model("usuarios", "PerfilStartup").objects.create(
            usuario=startup_user,
            nome_startup="Legacy Startup",
            pitch_resumido="Legacy pitch",
            setor_mercado="OUTROS",
            estagio_desenvolvimento="MVP",
        )
        old_investor = apps.get_model("usuarios", "PerfilInvestidor").objects.create(
            usuario=investor_user,
            tipo_investidor="ANJO",
            instituicao_origem="Private fund",
        )
        # A legacy investor incorrectly linked to a startup must remain invisible.
        apps.get_model("usuarios", "PerfilStartup").objects.create(
            usuario=investor_user,
            nome_startup="Hidden",
            pitch_resumido="Private fund",
            setor_mercado="OUTROS",
            estagio_desenvolvimento="MVP",
        )
        restore()
        from nexora_backend.feed.models import FeedPost
        from nexora_backend.profiles.models import (
            ClientProfile,
            InvestorProfile,
            StartupProfile,
        )

        assert ClientProfile.objects.get(pk=old_client.pk).document == "11222333000181"
        assert (
            StartupProfile.objects.get(pk=old_startup.pk).created_at
            == old_startup.criado_em
        )
        assert InvestorProfile.objects.filter(pk=old_investor.pk).exists()
        assert not StartupProfile.objects.filter(user_id=investor_user.pk).exists()
        assert (
            apps.get_model("usuarios", "PerfilEmpresaCliente")
            .objects.filter(pk=old_client.pk)
            .exists()
        )
        assert FeedPost.objects.filter(startup_id=old_startup.pk).exists()
        old_state()
        assert not ClientProfile.objects.exists()
        assert not StartupProfile.objects.exists()
        assert not InvestorProfile.objects.exists()
        assert (
            apps.get_model("usuarios", "PerfilInvestidor")
            .objects.filter(pk=old_investor.pk)
            .exists()
        )
    finally:
        restore()


@pytest.mark.parametrize("document", ["invalid-document", "11.222.333/0001-80"])
def test_invalid_legacy_documents_abort_without_exposing_value(document):
    apps = old_state()
    old = None
    try:
        user = legacy_user(apps, "EMPRESA_CLIENTE", "legacy-invalid@example.test")
        old = apps.get_model("usuarios", "PerfilEmpresaCliente").objects.create(
            usuario=user, cnpj=document, nome_fantasia="Legacy Client"
        )
        with pytest.raises(RuntimeError) as error:
            restore()
        assert document not in str(error.value)
        assert (
            apps.get_model("usuarios", "PerfilEmpresaCliente")
            .objects.filter(pk=old.pk)
            .exists()
        )
        assert not apps.get_model("profiles", "ClientProfile").objects.exists()
    finally:
        if old:
            old.delete()
        restore()
