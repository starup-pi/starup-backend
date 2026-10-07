"""Private push capabilities and a durable notification outbox."""

from django.conf import settings
from django.db import models

from starup_backend.common.models import UUIDModel


class PushSubscription(UUIDModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=128)
    auth = models.CharField(max_length=64)


class PushMessage(UUIDModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_messages"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["sent_at", "created_at"], name="push_pending")]
