from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    PerfilEmpresaCliente,
    PerfilEntidadeFomento,
    PerfilInvestidor,
    PerfilStartup,
    Usuario,
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ['-criado_em']
    list_display = ('email', 'nome_civil', 'perfil_ativo', 'ativo', 'is_staff')
    list_filter = ('perfil_ativo', 'ativo', 'is_staff')
    search_fields = ('email', 'nome_civil')
    readonly_fields = ('id', 'criado_em', 'atualizado_em', 'data_aceite_termos')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Dados pessoais', {'fields': ('nome_civil', 'telefone')}),
        (
            'Perfil e conformidade LGPD',
            {
                'fields': (
                    'perfil_ativo',
                    'termo_privacidade_aceito',
                    'data_aceite_termos',
                    'ativo',
                )
            },
        ),
        ('Permissões', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas', {'fields': ('criado_em', 'atualizado_em', 'last_login')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'nome_civil',
                    'perfil_ativo',
                    'password1',
                    'password2',
                ),
            },
        ),
    )


@admin.register(PerfilStartup)
class PerfilStartupAdmin(admin.ModelAdmin):
    list_display = ('nome_startup', 'usuario', 'setor_mercado', 'estagio_desenvolvimento')
    search_fields = ('nome_startup', 'cnpj', 'usuario__email')
    list_filter = ('setor_mercado', 'estagio_desenvolvimento')


@admin.register(PerfilEmpresaCliente)
class PerfilEmpresaClienteAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'razao_social', 'usuario', 'segmento_operacional', 'porte_empresa')
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj', 'usuario__email')
    list_filter = ('segmento_operacional', 'porte_empresa')


@admin.register(PerfilInvestidor)
class PerfilInvestidorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo_investidor', 'confidencialidade_ativa')
    search_fields = ('instituicao_origem', 'usuario__email')
    list_filter = ('tipo_investidor', 'confidencialidade_ativa')


@admin.register(PerfilEntidadeFomento)
class PerfilEntidadeFomentoAdmin(admin.ModelAdmin):
    list_display = ('nome_instituicao', 'usuario', 'tipo_entidade', 'verificado_por_admin')
    search_fields = ('nome_instituicao', 'cnpj', 'usuario__email')
    list_filter = ('tipo_entidade', 'verificado_por_admin')
