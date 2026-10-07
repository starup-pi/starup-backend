"""Prevent private API and administration responses entering browser caches."""

from django.utils.cache import patch_cache_control


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/admin/")) and not getattr(
            response, "public_representation", False
        ):
            patch_cache_control(response, private=True, no_store=True)
        return response
