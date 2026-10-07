"""Consent-aware subscription lifecycle and bounded push dispatch."""

import json
from typing import Any
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from pywebpush import WebPushException, webpush
from requests import Session
from requests.exceptions import RequestException
from rest_framework.exceptions import NotFound, PermissionDenied

from nexora_backend.common.errors import Conflict
from nexora_backend.privacy.models import ConsentRecord
from nexora_backend.usuarios.models import Usuario

from .models import PushMessage, PushSubscription


class PushSession(Session):
    """Do not follow redirects outside the validated push destination."""

    def post(self, url, data=None, json=None, **kwargs):
        kwargs["allow_redirects"] = False
        return super().post(url, data=data, json=json, **kwargs)


def send_subscription(subscription: PushSubscription) -> None:
    with PushSession() as session:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(
                {"title": "Nexora", "body": "Há uma atualização na plataforma."}
            ),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            requests_session=session,
            timeout=5,
            ttl=300,
        )


@transaction.atomic
def subscribe(*, actor: Usuario, data: dict[str, Any]) -> PushSubscription:
    user = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if not user.ativo:
        raise PermissionDenied()
    if (
        not user.push_subscriptions.filter(endpoint=data["endpoint"]).exists()
        and user.push_subscriptions.count() >= 10
    ):
        raise Conflict()
    try:
        with transaction.atomic():
            subscription, _ = PushSubscription.objects.update_or_create(
                user=user,
                endpoint=data["endpoint"],
                defaults=data["keys"],
            )
    except IntegrityError as exc:
        raise Conflict() from exc
    if not user.consents.filter(purpose="WEB_PUSH", revoked_at__isnull=True).exists():
        ConsentRecord.objects.create(
            user=user,
            purpose="WEB_PUSH",
            policy_version=settings.PRIVACY_POLICY_VERSION,
        )
    return subscription


@transaction.atomic
def unsubscribe(*, actor: Usuario, subscription_id: UUID) -> None:
    user = get_user_model().objects.select_for_update().get(pk=actor.pk)
    count, _ = PushSubscription.objects.filter(pk=subscription_id, user=user).delete()
    if not count:
        raise NotFound()
    if not user.push_subscriptions.exists():
        user.consents.filter(purpose="WEB_PUSH", revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        user.push_messages.all().delete()


def enqueue_notification(*, user_id: UUID) -> None:
    if PushSubscription.objects.filter(user_id=user_id).exists():
        PushMessage.objects.create(user_id=user_id)


def dispatch_pending(*, limit: int = 50) -> int:
    """Called by a worker command; failed jobs retry at most three times."""
    if not all((settings.VAPID_PRIVATE_KEY, settings.VAPID_SUBJECT)):
        raise RuntimeError("VAPID configuration is required.")
    sent = 0
    # A per-message transaction avoids locking an entire backlog during network IO.
    candidates = list(
        PushMessage.objects.filter(sent_at__isnull=True, attempts__lt=3)
        .order_by("created_at")
        .values("id", "user_id")[:limit]
    )
    for candidate in candidates:
        with transaction.atomic():
            # Owner before outbox row matches erasure and unsubscribe lock order.
            user = (
                get_user_model()
                .objects.select_for_update()
                .get(pk=candidate["user_id"])
            )
            message = (
                PushMessage.objects.select_for_update(skip_locked=True)
                .filter(pk=candidate["id"], sent_at__isnull=True, attempts__lt=3)
                .first()
            )
            if message is None:
                continue
            if not user.ativo:
                message.delete()
                continue
            subscriptions = user.push_subscriptions.all()
            succeeded = True
            for subscription in subscriptions:
                try:
                    send_subscription(subscription)
                except WebPushException as exc:
                    code = (
                        exc.response.status_code if exc.response is not None else None
                    )
                    if code in (404, 410):
                        subscription.delete()
                    else:
                        succeeded = False
                except RequestException:
                    succeeded = False
            message.attempts += 1
            if succeeded:
                message.sent_at = timezone.now()
                sent += 1
            message.save(update_fields=["attempts", "sent_at"])
    return sent
