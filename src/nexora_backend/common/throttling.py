"""Fixed-window auth limits backed by Redis atomic add/incr operations."""

import hashlib
import hmac
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import Throttled


def enforce_auth_limit(request, *, scope: str, limit: int = 10) -> None:
    address = request.META.get("REMOTE_ADDR", "")
    digest = hmac.new(
        settings.SECRET_KEY.encode(), address.encode(), hashlib.sha256
    ).hexdigest()
    key = f"auth:{scope}:{int(time.time() // 60)}:{digest}"
    if cache.add(key, 1, timeout=120):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:
            cache.add(key, 1, timeout=120)
            count = 1
    if count > limit:
        raise Throttled(wait=60)
