"""Tests isolate cache state while exercising real PostgreSQL constraints."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def isolate_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    result = client.get("/api/v1/auth/csrf/").json()
    client.credentials(HTTP_X_CSRFTOKEN=result["csrf_token"])
    return client
