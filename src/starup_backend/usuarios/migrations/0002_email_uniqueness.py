"""Fail atomically on existing case-folded collisions; never rewrite email data."""

from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower


def check_emails(apps, schema_editor):
    User = apps.get_model("usuarios", "Usuario")
    duplicates = (
        User.objects.using(schema_editor.connection.alias)
        .annotate(normalized=Lower("email"))
        .values("normalized")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )
    if duplicates.exists():
        raise RuntimeError("Email collisions require correction before migration.")


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0001_initial")]
    operations = [
        migrations.RunPython(check_emails, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="usuario",
            constraint=models.UniqueConstraint(
                Lower("email"), name="user_email_case_insensitive"
            ),
        ),
    ]
