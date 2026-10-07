"""Legacy identity tables are read-only and restricted to platform operators."""

from django.contrib import admin

from .models import Usuario


@admin.register(Usuario)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "perfil_ativo", "ativo")
    fields = ("id", "email", "nome_civil", "perfil_ativo", "ativo", "criado_em")
    readonly_fields = fields

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
