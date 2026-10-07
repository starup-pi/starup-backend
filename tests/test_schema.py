"""OpenAPI accurately describes the public feed and excludes identity APIs."""

from drf_spectacular.generators import SchemaGenerator


def test_openapi_feed_has_explicit_discriminator():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    mapping = schema["components"]["schemas"]["FeedPost"]["discriminator"]["mapping"]
    assert set(mapping) == {"DEMAND", "STARTUP", "REVIEWED_SOLUTION"}
    assert "/api/v1/perfis-investidor/" not in schema["paths"]
    assert "/api/v1/usuarios/" not in schema["paths"]
