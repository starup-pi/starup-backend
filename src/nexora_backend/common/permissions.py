"""Role checks complement scoped querysets and service authorization."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .roles import Role


class ClientWritePermission(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or (
            request.user.is_authenticated and request.user.perfil_ativo == Role.CLIENT
        )


class ParticipantWritePermission(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.method in SAFE_METHODS
            or request.user.perfil_ativo in (Role.CLIENT, Role.STARTUP)
        )
