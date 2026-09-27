from django.urls import path

from . import views

app_name = 'usuarios'

urlpatterns = [
    path('', views.PainelHomeView.as_view(), name='home'),
    # USUARIO
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario-list'),
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario-create'),
    path('usuarios/<uuid:pk>/', views.UsuarioDetailView.as_view(), name='usuario-detail'),
    path('usuarios/<uuid:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario-update'),
    path('usuarios/<uuid:pk>/remover/', views.UsuarioDeleteView.as_view(), name='usuario-delete'),
    # PERFIL_STARTUP
    path('perfis-startup/', views.PerfilStartupListView.as_view(), name='perfil-startup-list'),
    path('perfis-startup/novo/', views.PerfilStartupCreateView.as_view(), name='perfil-startup-create'),
    path('perfis-startup/<uuid:pk>/', views.PerfilStartupDetailView.as_view(), name='perfil-startup-detail'),
    path('perfis-startup/<uuid:pk>/editar/', views.PerfilStartupUpdateView.as_view(), name='perfil-startup-update'),
    path('perfis-startup/<uuid:pk>/remover/', views.PerfilStartupDeleteView.as_view(), name='perfil-startup-delete'),
    # PERFIL_EMPRESA_CLIENTE
    path(
        'perfis-empresa-cliente/',
        views.PerfilEmpresaClienteListView.as_view(),
        name='perfil-empresa-cliente-list',
    ),
    path(
        'perfis-empresa-cliente/novo/',
        views.PerfilEmpresaClienteCreateView.as_view(),
        name='perfil-empresa-cliente-create',
    ),
    path(
        'perfis-empresa-cliente/<uuid:pk>/',
        views.PerfilEmpresaClienteDetailView.as_view(),
        name='perfil-empresa-cliente-detail',
    ),
    path(
        'perfis-empresa-cliente/<uuid:pk>/editar/',
        views.PerfilEmpresaClienteUpdateView.as_view(),
        name='perfil-empresa-cliente-update',
    ),
    path(
        'perfis-empresa-cliente/<uuid:pk>/remover/',
        views.PerfilEmpresaClienteDeleteView.as_view(),
        name='perfil-empresa-cliente-delete',
    ),
    # PERFIL_INVESTIDOR
    path('perfis-investidor/', views.PerfilInvestidorListView.as_view(), name='perfil-investidor-list'),
    path(
        'perfis-investidor/novo/',
        views.PerfilInvestidorCreateView.as_view(),
        name='perfil-investidor-create',
    ),
    path(
        'perfis-investidor/<uuid:pk>/',
        views.PerfilInvestidorDetailView.as_view(),
        name='perfil-investidor-detail',
    ),
    path(
        'perfis-investidor/<uuid:pk>/editar/',
        views.PerfilInvestidorUpdateView.as_view(),
        name='perfil-investidor-update',
    ),
    path(
        'perfis-investidor/<uuid:pk>/remover/',
        views.PerfilInvestidorDeleteView.as_view(),
        name='perfil-investidor-delete',
    ),
    # PERFIL_ENTIDADE_FOMENTO
    path(
        'perfis-entidade-fomento/',
        views.PerfilEntidadeFomentoListView.as_view(),
        name='perfil-entidade-fomento-list',
    ),
    path(
        'perfis-entidade-fomento/novo/',
        views.PerfilEntidadeFomentoCreateView.as_view(),
        name='perfil-entidade-fomento-create',
    ),
    path(
        'perfis-entidade-fomento/<uuid:pk>/',
        views.PerfilEntidadeFomentoDetailView.as_view(),
        name='perfil-entidade-fomento-detail',
    ),
    path(
        'perfis-entidade-fomento/<uuid:pk>/editar/',
        views.PerfilEntidadeFomentoUpdateView.as_view(),
        name='perfil-entidade-fomento-update',
    ),
    path(
        'perfis-entidade-fomento/<uuid:pk>/remover/',
        views.PerfilEntidadeFomentoDeleteView.as_view(),
        name='perfil-entidade-fomento-delete',
    ),
]
