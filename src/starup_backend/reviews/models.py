"""One immutable integer rating per delivered solution."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from starup_backend.common.models import UUIDModel


class Review(UUIDModel):
    solution = models.OneToOneField(
        "solutions.Solution", on_delete=models.PROTECT, related_name="review"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_range",
            ),
        ]
