"""Accept only known HTTPS push services, never arbitrary delivery URLs."""

import base64
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from rest_framework import serializers

from nexora_backend.common.serializers import StrictSerializer


class PushKeysSerializer(StrictSerializer):
    p256dh = serializers.CharField(max_length=128)
    auth = serializers.CharField(max_length=64)

    def validate(self, attrs):
        for name, length in (("p256dh", 65), ("auth", 16)):
            try:
                value = attrs[name]
                decoded = base64.b64decode(
                    value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
                )
            except (ValueError, TypeError) as exc:
                raise serializers.ValidationError({name: "Chave inválida."}) from exc
            if len(decoded) != length or (name == "p256dh" and decoded[0] != 4):
                raise serializers.ValidationError({name: "Chave inválida."})
            if name == "p256dh":
                try:
                    ec.EllipticCurvePublicKey.from_encoded_point(
                        ec.SECP256R1(), decoded
                    )
                except ValueError as exc:
                    raise serializers.ValidationError(
                        {name: "Chave inválida."}
                    ) from exc
        return attrs


class PushSubscriptionSerializer(StrictSerializer):
    endpoint = serializers.URLField(max_length=2048)
    keys = PushKeysSerializer()
    consent = serializers.BooleanField()

    def validate_endpoint(self, value):
        try:
            url = urlsplit(value)
            port = url.port
        except ValueError as exc:
            raise serializers.ValidationError("Serviço de push não permitido.") from exc
        if (
            url.scheme != "https"
            or url.hostname not in settings.PUSH_ALLOWED_HOSTS
            or port not in (None, 443)
            or url.username
            or url.password
            or url.fragment
        ):
            raise serializers.ValidationError("Serviço de push não permitido.")
        return value

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError("Consentimento obrigatório.")
        return value


class PushSubscriptionResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()


class PushConfigSerializer(serializers.Serializer):
    public_key = serializers.CharField()
