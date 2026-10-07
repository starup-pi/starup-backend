"""A small initial taxonomy with reversible inserts."""

from django.db import migrations

CATEGORIES = [
    ("operations", "Operações"),
    ("logistics", "Logística"),
    ("finance", "Finanças"),
    ("sales", "Vendas"),
    ("technology", "Tecnologia"),
]


def seed(apps, schema_editor):
    Category = apps.get_model("demands", "Category")
    for slug, name in CATEGORIES:
        Category.objects.using(schema_editor.connection.alias).get_or_create(
            slug=slug, defaults={"name": name}
        )


def reverse_seed(apps, schema_editor):
    Category = apps.get_model("demands", "Category")
    Category.objects.using(schema_editor.connection.alias).filter(
        slug__in=[slug for slug, _ in CATEGORIES], demand__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("demands", "0001_initial")]
    operations = [migrations.RunPython(seed, reverse_seed)]
