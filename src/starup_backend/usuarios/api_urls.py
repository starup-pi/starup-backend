from rest_framework.routers import DefaultRouter

from . import api_views

app_name = 'usuarios_api'

router = DefaultRouter()
router.register('usuarios', api_views.UsuarioViewSet, basename='usuario')
router.register('perfis-startup', api_views.PerfilStartupViewSet, basename='perfil-startup')
router.register(
    'perfis-empresa-cliente',
    api_views.PerfilEmpresaClienteViewSet,
    basename='perfil-empresa-cliente',
)
router.register(
    'perfis-investidor', api_views.PerfilInvestidorViewSet, basename='perfil-investidor'
)
router.register(
    'perfis-entidade-fomento',
    api_views.PerfilEntidadeFomentoViewSet,
    basename='perfil-entidade-fomento',
)

urlpatterns = router.urls
