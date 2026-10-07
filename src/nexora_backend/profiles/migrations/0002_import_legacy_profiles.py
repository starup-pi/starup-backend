"""Copy supported legacy profiles without deleting original data."""

import secrets

from django.db import migrations


def import_profiles(apps, schema_editor):
    Client = apps.get_model("profiles", "ClientProfile")
    Startup = apps.get_model("profiles", "StartupProfile")
    Investor = apps.get_model("profiles", "InvestorProfile")
    LegacyClient = apps.get_model("usuarios", "PerfilEmpresaCliente")
    LegacyStartup = apps.get_model("usuarios", "PerfilStartup")
    LegacyInvestor = apps.get_model("usuarios", "PerfilInvestidor")
    alias = schema_editor.connection.alias
    seen = set(Client.objects.using(alias).values_list("document", flat=True))
    for old in LegacyClient.objects.using(alias).filter(
        usuario__perfil_ativo="EMPRESA_CLIENTE"
    ):
        document = old.cnpj.strip().upper()
        for char in "./- ":
            document = document.replace(char, "")
        # Frozen validation prevents migration behaviour changing with application code.
        if (
            len(document) != 14
            or len(set(document)) == 1
            or not all(
                char in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for char in document[:12]
            )
            or not document[-2:].isascii()
            or not document[-2:].isdigit()
        ):
            raise RuntimeError(
                "Legacy client document requires correction before migration."
            )
        digits = [ord(char) - 48 for char in document]
        for size, weights in (
            (12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
            (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
        ):
            remainder = sum(a * b for a, b in zip(digits[:size], weights)) % 11
            if digits[size] != (0 if remainder < 2 else 11 - remainder):
                raise RuntimeError(
                    "Legacy client document requires correction before migration."
                )
        if document in seen:
            raise RuntimeError(
                "Legacy document collision requires correction before migration."
            )
        seen.add(document)
        Client.objects.using(alias).create(
            id=old.id,
            user_id=old.usuario_id,
            person_type="PJ",
            document=document,
            display_name=old.nome_fantasia or old.razao_social,
        )
    for old in LegacyStartup.objects.using(alias).filter(
        usuario__perfil_ativo="STARTUP"
    ):
        Startup.objects.using(alias).create(
            id=old.id,
            user_id=old.usuario_id,
            name=old.nome_startup,
            description=old.pitch_resumido,
            website=old.website or "",
            category=old.setor_mercado,
        )
        Startup.objects.using(alias).filter(id=old.id).update(created_at=old.criado_em)
    for old in LegacyInvestor.objects.using(alias).filter(
        usuario__perfil_ativo="INVESTIDOR"
    ):
        Investor.objects.using(alias).create(
            id=old.id, user_id=old.usuario_id, alias=f"Visitor-{secrets.token_hex(12)}"
        )


def reverse_import(apps, schema_editor):
    alias = schema_editor.connection.alias
    for new, old in (
        ("ClientProfile", "PerfilEmpresaCliente"),
        ("StartupProfile", "PerfilStartup"),
        ("InvestorProfile", "PerfilInvestidor"),
    ):
        ids = (
            apps.get_model("usuarios", old)
            .objects.using(alias)
            .values_list("id", flat=True)
        )
        apps.get_model("profiles", new).objects.using(alias).filter(id__in=ids).delete()


class Migration(migrations.Migration):
    dependencies = [("profiles", "0001_initial"), ("usuarios", "0001_initial")]
    operations = [migrations.RunPython(import_profiles, reverse_import)]
