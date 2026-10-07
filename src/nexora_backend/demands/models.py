"""Client demands and their publication policy."""

from django.db import models

from nexora_backend.common.models import UUIDModel


class Category(UUIDModel):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)


class Demand(UUIDModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        IN_PROGRESS = "IN_PROGRESS", "Em andamento"
        COMPLETED = "COMPLETED", "Concluída"
        CANCELLED = "CANCELLED", "Cancelada"

    class Visibility(models.TextChoices):
        PUBLIC = "PUBLIC", "Pública"
        PRIVATE = "PRIVATE", "Privada"

    client = models.ForeignKey(
        "profiles.ClientProfile", on_delete=models.PROTECT, related_name="demands"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=10000)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN
    )
    visibility = models.CharField(
        max_length=8, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "-created_at"], name="demand_status_created"
            ),
            models.Index(fields=["category", "status"], name="demand_category_status"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
                ),
                name="demand_valid_status",
            ),
            models.CheckConstraint(
                condition=models.Q(visibility__in=["PUBLIC", "PRIVATE"]),
                name="demand_valid_visibility",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="COMPLETED", completed_at__isnull=False)
                    | (
                        ~models.Q(status="COMPLETED")
                        & models.Q(completed_at__isnull=True)
                    )
                ),
                name="demand_completion_date",
            ),
        ]
