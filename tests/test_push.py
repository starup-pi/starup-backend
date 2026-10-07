"""Push consent, owner scope, SSRF limits and mocked transport."""

import base64
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import override_settings
from pywebpush import WebPushException
from requests import Session
from requests.exceptions import Timeout

from nexora_backend.notifications.models import PushMessage, PushSubscription
from nexora_backend.notifications.services import (
    PushSession,
    dispatch_pending,
    subscribe,
)
from tests.factories import InvestorFactory, UserFactory

pytestmark = pytest.mark.django_db


def push_data(endpoint="https://fcm.googleapis.com/push/test"):
    key = (
        ec.derive_private_key(1, ec.SECP256R1())
        .public_key()
        .public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": base64.urlsafe_b64encode(key).decode().rstrip("="),
            "auth": base64.urlsafe_b64encode(bytes(range(16))).decode().rstrip("="),
        },
        "consent": True,
    }


def test_subscription_consent_and_owner_scope(api_client):
    owner = InvestorFactory().user
    api_client.force_authenticate(owner)
    response = api_client.post(
        "/api/v1/push/subscriptions/", push_data(), format="json"
    )
    assert response.status_code == 201, response.content
    assert owner.consents.get().purpose == "WEB_PUSH"
    subscription_id = response.json()["id"]
    api_client.force_authenticate(UserFactory())
    assert (
        api_client.delete(f"/api/v1/push/subscriptions/{subscription_id}/").status_code
        == 404
    )
    api_client.force_authenticate(owner)
    assert (
        api_client.delete(f"/api/v1/push/subscriptions/{subscription_id}/").status_code
        == 204
    )
    assert owner.consents.get().revoked_at is not None


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/x",
        "https://127.0.0.1/x",
        "https://fcm.googleapis.com.evil.test/x",
        "https://fcm.googleapis.com:8443/x",
        "https://fcm.googleapis.com:65536/x",
        "https://user:pass@fcm.googleapis.com/x",
        "https://169.254.169.254/latest/meta-data/",
        "https://fcm.googleapis.com/x#fragment",
    ],
)
def test_push_ssrf_rejected(api_client, endpoint):
    api_client.force_authenticate(InvestorFactory().user)
    assert (
        api_client.post(
            "/api/v1/push/subscriptions/", push_data(endpoint), format="json"
        ).status_code
        == 400
    )
    assert not PushSubscription.objects.exists()


def test_push_requires_consent_and_valid_keys(api_client):
    api_client.force_authenticate(InvestorFactory().user)
    data = push_data()
    assert (
        api_client.post(
            "/api/v1/push/subscriptions/", {**data, "consent": False}, format="json"
        ).status_code
        == 400
    )
    data["keys"]["auth"] = "bad"
    assert (
        api_client.post("/api/v1/push/subscriptions/", data, format="json").status_code
        == 400
    )


def test_subscribe_does_not_transfer_another_users_endpoint(api_client):
    first, second = InvestorFactory().user, InvestorFactory().user
    subscribe(actor=first, data=push_data())
    api_client.force_authenticate(second)
    assert (
        api_client.post(
            "/api/v1/push/subscriptions/", push_data(), format="json"
        ).status_code
        == 409
    )
    assert PushSubscription.objects.get().user == first


@override_settings(
    VAPID_PRIVATE_KEY="test-private-key", VAPID_SUBJECT="mailto:operator@example.test"
)
def test_push_dispatch_is_generic_and_marks_job():
    user = InvestorFactory().user
    subscribe(actor=user, data=push_data())
    message = PushMessage.objects.create(user=user)
    with patch("nexora_backend.notifications.services.webpush") as send:
        assert dispatch_pending() == 1
    message.refresh_from_db()
    assert message.sent_at is not None
    payload = send.call_args.kwargs["data"]
    assert user.email not in payload
    assert str(user.id) not in payload
    assert "Há uma atualização" in payload or "\\u00e1 uma atualiza" in payload


@override_settings(
    VAPID_PRIVATE_KEY="test-private-key", VAPID_SUBJECT="mailto:operator@example.test"
)
def test_expired_push_endpoint_is_removed():
    user = InvestorFactory().user
    subscribe(actor=user, data=push_data())
    PushMessage.objects.create(user=user)
    error = WebPushException("Expired", response=SimpleNamespace(status_code=410))
    with patch("nexora_backend.notifications.services.webpush", side_effect=error):
        dispatch_pending()
    assert not PushSubscription.objects.exists()


@override_settings(
    VAPID_PRIVATE_KEY="test-private-key", VAPID_SUBJECT="mailto:operator@example.test"
)
def test_push_timeout_keeps_job_for_retry():
    user = InvestorFactory().user
    subscribe(actor=user, data=push_data())
    message = PushMessage.objects.create(user=user)
    with patch("nexora_backend.notifications.services.webpush", side_effect=Timeout()):
        assert dispatch_pending() == 0
    message.refresh_from_db()
    assert message.sent_at is None
    assert message.attempts == 1


def test_push_missing_vapid_fails_before_transport():
    with (
        pytest.raises(RuntimeError),
        patch("nexora_backend.notifications.services.webpush") as send,
    ):
        dispatch_pending()
    send.assert_not_called()


def test_push_rejects_invalid_curve_point(api_client):
    api_client.force_authenticate(InvestorFactory().user)
    data = push_data()
    data["keys"]["p256dh"] = base64.urlsafe_b64encode(bytes([4]) + bytes(64)).decode()
    response = api_client.post("/api/v1/push/subscriptions/", data, format="json")
    assert response.status_code == 400


def test_push_transport_does_not_follow_redirects():
    with patch.object(Session, "post") as transport, PushSession() as session:
        session.post("https://fcm.googleapis.com/push/test")
    assert transport.call_args.kwargs["allow_redirects"] is False


def test_push_subscription_limit_is_serialized(api_client):
    owner = InvestorFactory().user
    for index in range(10):
        subscribe(
            actor=owner, data=push_data(f"https://fcm.googleapis.com/push/{index}")
        )
    api_client.force_authenticate(owner)
    response = api_client.post(
        "/api/v1/push/subscriptions/", push_data(), format="json"
    )
    assert response.status_code == 409
    assert owner.push_subscriptions.count() == 10
