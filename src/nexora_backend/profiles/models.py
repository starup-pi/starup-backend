"""Private client/investor profiles and public startup data."""

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from nexora_backend.common.models import UUIDModel

from .validators import normalize_document, validate_document


def generate_alias() -> str:
    return f"Visitor-{secrets.token_hex(12)}"


class ClientProfile(UUIDModel):
    class PersonType(models.TextChoices):
        INDIVIDUAL = "PF", "Pessoa física"
        COMPANY = "PJ", "Pessoa jurídica"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_profile",
    )
    person_type = models.CharField(max_length=2, choices=PersonType.choices)
    document = models.CharField(
        max_length=14, unique=True, null=True, validators=[validate_document]
    )
    display_name = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(document__isnull=True)
                    | models.Q(person_type="PF", document__regex=r"^[0-9]{11}$")
                    | models.Q(
                        person_type="PJ", document__regex=r"^[A-Z0-9]{12}[0-9]{2}$"
                    )
                ),
                name="client_document_format",
            ),
        ]

    def clean_fields(self, exclude=None) -> None:
        if self.document is not None:
            self.document = normalize_document(self.document)
        super().clean_fields(exclude=exclude)

    def clean(self):
        if self.document is None:
            if self.user.ativo:
                raise ValidationError({"document": "Documento obrigatório."})
            return
        self.document = normalize_document(self.document)
        validate_document(self.document)
        expected = "PF" if len(self.document) == 11 else "PJ"
        if self.person_type != expected:
            raise ValidationError({"person_type": "Tipo incompatível com o documento."})


class StartupProfile(UUIDModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="startup_profile",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    website = models.URLField(blank=True)
    category = models.CharField(max_length=40, blank=True)


class InvestorProfile(UUIDModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="investor_profile",
    )
    alias = models.CharField(
        max_length=32, unique=True, default=generate_alias, editable=False
    )

    def __str__(self) -> str:
        return self.alias
