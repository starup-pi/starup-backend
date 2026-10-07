"""Proposals, deliveries and explicit status history."""

from django.conf import settings
from django.db import models

from starup_backend.common.models import UUIDModel


class Solution(UUIDModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Enviada"
        ACCEPTED = "ACCEPTED", "Aceita"
        IN_PROGRESS = "IN_PROGRESS", "Em andamento"
        DELIVERED = "DELIVERED", "Entregue"
        COMPLETED = "COMPLETED", "Concluída"
        REJECTED = "REJECTED", "Rejeitada"
        WITHDRAWN = "WITHDRAWN", "Retirada"

    demand = models.ForeignKey(
        "demands.Demand", on_delete=models.PROTECT, related_name="solutions"
    )
    startup = models.ForeignKey(
        "profiles.StartupProfile", on_delete=models.PROTECT, related_name="solutions"
    )
    proposal = models.TextField(max_length=10000)
    delivery = models.TextField(max_length=10000, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUBMITTED
    )

    class Meta:
        indexes = [
            models.Index(fields=["startup", "status"], name="solution_startup_status")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["demand", "startup"], name="one_startup_proposal"
            ),
            models.UniqueConstraint(
                fields=["demand"],
                condition=models.Q(
                    status__in=["ACCEPTED", "IN_PROGRESS", "DELIVERED", "COMPLETED"]
                ),
                name="one_accepted_solution",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "SUBMITTED",
                        "ACCEPTED",
                        "IN_PROGRESS",
                        "DELIVERED",
                        "COMPLETED",
                        "REJECTED",
                        "WITHDRAWN",
                    ]
                ),
                name="solution_valid_status",
            ),
        ]


class SolutionStatusEvent(UUIDModel):
    solution = models.ForeignKey(
        Solution, on_delete=models.CASCADE, related_name="history"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    previous_status = models.CharField(max_length=16, blank=True)
    new_status = models.CharField(max_length=16)

    class Meta:
        ordering = ["created_at", "id"]
