"""Concrete polymorphic references retain database referential integrity."""

import uuid

from django.db import models


class FeedPost(models.Model):
    class Kind(models.TextChoices):
        DEMAND = "DEMAND", "Demanda"
        REVIEWED_SOLUTION = "REVIEWED_SOLUTION", "Solução avaliada"
        STARTUP = "STARTUP", "Startup"

    position = models.BigAutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    published_at = models.DateTimeField(auto_now_add=True)
    demand = models.OneToOneField(
        "demands.Demand", on_delete=models.CASCADE, null=True, blank=True
    )
    review = models.OneToOneField(
        "reviews.Review", on_delete=models.CASCADE, null=True, blank=True
    )
    startup = models.OneToOneField(
        "profiles.StartupProfile", on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        ordering = ["-position"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind="DEMAND",
                        demand__isnull=False,
                        review__isnull=True,
                        startup__isnull=True,
                    )
                    | models.Q(
                        kind="REVIEWED_SOLUTION",
                        demand__isnull=True,
                        review__isnull=False,
                        startup__isnull=True,
                    )
                    | models.Q(
                        kind="STARTUP",
                        demand__isnull=True,
                        review__isnull=True,
                        startup__isnull=False,
                    )
                ),
                name="feed_exactly_one_target",
            ),
        ]
