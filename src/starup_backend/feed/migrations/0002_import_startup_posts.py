"""Publish migrated startups once, preserving their original registration dates."""

from django.db import migrations


def publish_startups(apps, schema_editor):
    Startup = apps.get_model("profiles", "StartupProfile")
    FeedPost = apps.get_model("feed", "FeedPost")
    alias = schema_editor.connection.alias
    for startup in (
        Startup.objects.using(alias)
        .filter(user__ativo=True, user__perfil_ativo="STARTUP")
        .order_by("created_at", "id")
    ):
        post = FeedPost.objects.using(alias).create(kind="STARTUP", startup=startup)
        FeedPost.objects.using(alias).filter(pk=post.pk).update(
            published_at=startup.created_at
        )


def reverse_posts(apps, schema_editor):
    alias = schema_editor.connection.alias
    ids = (
        apps.get_model("usuarios", "PerfilStartup")
        .objects.using(alias)
        .values_list("id", flat=True)
    )
    apps.get_model("feed", "FeedPost").objects.using(alias).filter(
        startup_id__in=ids
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feed", "0001_initial"),
        ("profiles", "0002_import_legacy_profiles"),
    ]
    operations = [migrations.RunPython(publish_startups, reverse_posts)]
