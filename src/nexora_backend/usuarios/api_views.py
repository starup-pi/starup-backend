from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import (
    PerfilEmpresaCliente,
    PerfilEntidadeFomento,
    PerfilInvestidor,
    PerfilStartup,
    Usuario,
)
from .serializers import (
    PerfilEmpresaClienteSerializer,
    PerfilEntidadeFomentoSerializer,
    PerfilInvestidorSerializer,
    PerfilStartupSerializer,
    UsuarioSerializer,
)


@extend_schema_view(
    list=extend_schema(summary='Lista usuários', tags=['Usuários']),
    retrieve=extend_schema(summary='Detalha um usuário', tags=['Usuários']),
    create=extend_schema(summary='Cria um usuário', tags=['Usuários']),
    update=extend_schema(summary='Atualiza um usuário (completo)', tags=['Usuários']),
    partial_update=extend_schema(summary='Atualiza um usuário (parcial)', tags=['Usuários']),
    destroy=extend_schema(summary='Remove um usuário', tags=['Usuários']),
)
class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD da entidade USUARIO (identidade canônica de acesso)."""

    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ['perfil_ativo', 'ativo']
    search_fields = ['email', 'nome_civil']
    ordering_fields = ['criado_em', 'nome_civil']


@extend_schema_view(
    list=extend_schema(summary='Lista perfis de startup', tags=['Perfil Startup']),
    retrieve=extend_schema(summary='Detalha um perfil de startup', tags=['Perfil Startup']),
    create=extend_schema(summary='Cria um perfil de startup', tags=['Perfil Startup']),
    update=extend_schema(summary='Atualiza um perfil de startup (completo)', tags=['Perfil Startup']),
    partial_update=extend_schema(summary='Atualiza um perfil de startup (parcial)', tags=['Perfil Startup']),
    destroy=extend_schema(summary='Remove um perfil de startup', tags=['Perfil Startup']),
)
class PerfilStartupViewSet(viewsets.ModelViewSet):
    """CRUD da entidade PERFIL_STARTUP."""

    queryset = PerfilStartup.objects.select_related('usuario').all()
    serializer_class = PerfilStartupSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ['setor_mercado', 'estagio_desenvolvimento']
    search_fields = ['nome_startup', 'cnpj']
    ordering_fields = ['criado_em', 'pontuacao_reputacao']


@extend_schema_view(
    list=extend_schema(summary='Lista perfis de empresa cliente', tags=['Perfil Empresa Cliente']),
    retrieve=extend_schema(summary='Detalha um perfil de empresa cliente', tags=['Perfil Empresa Cliente']),
    create=extend_schema(summary='Cria um perfil de empresa cliente', tags=['Perfil Empresa Cliente']),
    update=extend_schema(summary='Atualiza um perfil de empresa cliente (completo)', tags=['Perfil Empresa Cliente']),
    partial_update=extend_schema(summary='Atualiza um perfil de empresa cliente (parcial)', tags=['Perfil Empresa Cliente']),
    destroy=extend_schema(summary='Remove um perfil de empresa cliente', tags=['Perfil Empresa Cliente']),
)
class PerfilEmpresaClienteViewSet(viewsets.ModelViewSet):
    """CRUD da entidade PERFIL_EMPRESA_CLIENTE."""

    queryset = PerfilEmpresaCliente.objects.select_related('usuario').all()
    serializer_class = PerfilEmpresaClienteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ['segmento_operacional', 'porte_empresa']
    search_fields = ['nome_fantasia', 'razao_social', 'cnpj']
    ordering_fields = ['criado_em']


@extend_schema_view(
    list=extend_schema(summary='Lista perfis de investidor', tags=['Perfil Investidor']),
    retrieve=extend_schema(summary='Detalha um perfil de investidor', tags=['Perfil Investidor']),
    create=extend_schema(summary='Cria um perfil de investidor', tags=['Perfil Investidor']),
    update=extend_schema(summary='Atualiza um perfil de investidor (completo)', tags=['Perfil Investidor']),
    partial_update=extend_schema(summary='Atualiza um perfil de investidor (parcial)', tags=['Perfil Investidor']),
    destroy=extend_schema(summary='Remove um perfil de investidor', tags=['Perfil Investidor']),
)
class PerfilInvestidorViewSet(viewsets.ModelViewSet):
    """CRUD da entidade PERFIL_INVESTIDOR."""

    queryset = PerfilInvestidor.objects.select_related('usuario').all()
    serializer_class = PerfilInvestidorSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ['tipo_investidor', 'confidencialidade_ativa']
    ordering_fields = ['criado_em']


@extend_schema_view(
    list=extend_schema(summary='Lista perfis de entidade de fomento', tags=['Perfil Entidade de Fomento']),
    retrieve=extend_schema(summary='Detalha um perfil de entidade de fomento', tags=['Perfil Entidade de Fomento']),
    create=extend_schema(summary='Cria um perfil de entidade de fomento', tags=['Perfil Entidade de Fomento']),
    update=extend_schema(summary='Atualiza um perfil de entidade de fomento (completo)', tags=['Perfil Entidade de Fomento']),
    partial_update=extend_schema(summary='Atualiza um perfil de entidade de fomento (parcial)', tags=['Perfil Entidade de Fomento']),
    destroy=extend_schema(summary='Remove um perfil de entidade de fomento', tags=['Perfil Entidade de Fomento']),
)
class PerfilEntidadeFomentoViewSet(viewsets.ModelViewSet):
    """CRUD da entidade PERFIL_ENTIDADE_FOMENTO."""

    queryset = PerfilEntidadeFomento.objects.select_related('usuario').all()
    serializer_class = PerfilEntidadeFomentoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ['tipo_entidade', 'verificado_por_admin']
    search_fields = ['nome_instituicao', 'cnpj']
    ordering_fields = ['criado_em']
