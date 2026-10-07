"""Versioned policy acknowledgement and optional purpose-specific consent."""

from django.conf import settings
from django.db import models

from starup_backend.common.models import UUIDModel


class ConsentRecord(UUIDModel):
    class Purpose(models.TextChoices):
        POLICY_ACKNOWLEDGEMENT = "POLICY_ACKNOWLEDGEMENT", "Ciência da política"
        WEB_PUSH = "WEB_PUSH", "Notificações push"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consents"
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    policy_version = models.CharField(max_length=32)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
