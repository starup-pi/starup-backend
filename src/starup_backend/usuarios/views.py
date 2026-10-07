from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from . import forms, models


class PainelHomeView(ListView):
    """Página inicial do painel: um atalho para o CRUD de cada entidade base."""

    template_name = 'usuarios/painel_home.html'
    queryset = models.Usuario.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cards'] = [
            {
                'titulo': 'Usuários',
                'descricao': 'Identidade canônica de acesso (USUARIO).',
                'url': 'usuarios:usuario-list',
                'total': models.Usuario.objects.count(),
            },
            {
                'titulo': 'Perfis de Startup',
                'descricao': 'Startups que publicam ofertas de teste.',
                'url': 'usuarios:perfil-startup-list',
                'total': models.PerfilStartup.objects.count(),
            },
            {
                'titulo': 'Perfis de Empresa Cliente',
                'descricao': 'PMEs que testam as soluções.',
                'url': 'usuarios:perfil-empresa-cliente-list',
                'total': models.PerfilEmpresaCliente.objects.count(),
            },
            {
                'titulo': 'Perfis de Investidor',
                'descricao': 'Investidores em modo leitor discreto.',
                'url': 'usuarios:perfil-investidor-list',
                'total': models.PerfilInvestidor.objects.count(),
            },
            {
                'titulo': 'Perfis de Entidade de Fomento',
                'descricao': 'Entidades que publicam editais e eventos.',
                'url': 'usuarios:perfil-entidade-fomento-list',
                'total': models.PerfilEntidadeFomento.objects.count(),
            },
        ]
        return context


class BaseEntidadeMixin:
    """
    Mixin com o mínimo necessário para reaproveitar 4 templates genéricos
    (list / detail / form / confirm_delete) entre as 5 entidades base.
    """

    list_fields: list[tuple[str, str]] = []
    entidade_nome = ''
    url_namespace = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['entidade_nome'] = self.entidade_nome
        context['list_fields'] = self.list_fields
        context['url_namespace'] = self.url_namespace
        return context


# ---------------------------------------------------------------------------
# USUARIO
# ---------------------------------------------------------------------------
class UsuarioListView(BaseEntidadeMixin, ListView):
    model = models.Usuario
    template_name = 'usuarios/object_list.html'
    paginate_by = 20
    entidade_nome = 'Usuário'
    url_namespace = 'usuarios:usuario'
    list_fields = [
        ('email', 'E-mail'),
        ('nome_civil', 'Nome'),
        ('perfil_ativo', 'Perfil ativo'),
        ('ativo', 'Ativo'),
    ]


class UsuarioDetailView(BaseEntidadeMixin, DetailView):
    model = models.Usuario
    template_name = 'usuarios/object_detail.html'
    entidade_nome = 'Usuário'
    url_namespace = 'usuarios:usuario'
    list_fields = UsuarioListView.list_fields + [
        ('telefone', 'Telefone'),
        ('termo_privacidade_aceito', 'Termo de privacidade aceito'),
        ('criado_em', 'Criado em'),
    ]


class UsuarioCreateView(BaseEntidadeMixin, CreateView):
    model = models.Usuario
    form_class = forms.UsuarioForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:usuario-list')
    entidade_nome = 'Usuário'
    url_namespace = 'usuarios:usuario'

    def form_valid(self, form):
        messages.success(self.request, 'Usuário criado com sucesso.')
        return super().form_valid(form)


class UsuarioUpdateView(BaseEntidadeMixin, UpdateView):
    model = models.Usuario
    form_class = forms.UsuarioForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:usuario-list')
    entidade_nome = 'Usuário'
    url_namespace = 'usuarios:usuario'

    def form_valid(self, form):
        messages.success(self.request, 'Usuário atualizado com sucesso.')
        return super().form_valid(form)


class UsuarioDeleteView(BaseEntidadeMixin, DeleteView):
    model = models.Usuario
    template_name = 'usuarios/object_confirm_delete.html'
    success_url = reverse_lazy('usuarios:usuario-list')
    entidade_nome = 'Usuário'
    url_namespace = 'usuarios:usuario'

    def form_valid(self, form):
        messages.success(self.request, 'Usuário removido com sucesso.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# PERFIL_STARTUP
# ---------------------------------------------------------------------------
class PerfilStartupListView(BaseEntidadeMixin, ListView):
    model = models.PerfilStartup
    template_name = 'usuarios/object_list.html'
    paginate_by = 20
    entidade_nome = 'Perfil de Startup'
    url_namespace = 'usuarios:perfil-startup'
    list_fields = [
        ('nome_startup', 'Startup'),
        ('setor_mercado', 'Setor'),
        ('estagio_desenvolvimento', 'Estágio'),
        ('pontuacao_reputacao', 'Reputação'),
    ]


class PerfilStartupDetailView(BaseEntidadeMixin, DetailView):
    model = models.PerfilStartup
    template_name = 'usuarios/object_detail.html'
    entidade_nome = 'Perfil de Startup'
    url_namespace = 'usuarios:perfil-startup'
    list_fields = PerfilStartupListView.list_fields + [
        ('usuario', 'Usuário responsável'),
        ('cnpj', 'CNPJ'),
        ('website', 'Website'),
        ('pitch_resumido', 'Pitch resumido'),
        ('total_testes_concluidos', 'Testes concluídos'),
        ('criado_em', 'Criado em'),
    ]


class PerfilStartupCreateView(BaseEntidadeMixin, CreateView):
    model = models.PerfilStartup
    form_class = forms.PerfilStartupForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-startup-list')
    entidade_nome = 'Perfil de Startup'
    url_namespace = 'usuarios:perfil-startup'


class PerfilStartupUpdateView(BaseEntidadeMixin, UpdateView):
    model = models.PerfilStartup
    form_class = forms.PerfilStartupForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-startup-list')
    entidade_nome = 'Perfil de Startup'
    url_namespace = 'usuarios:perfil-startup'


class PerfilStartupDeleteView(BaseEntidadeMixin, DeleteView):
    model = models.PerfilStartup
    template_name = 'usuarios/object_confirm_delete.html'
    success_url = reverse_lazy('usuarios:perfil-startup-list')
    entidade_nome = 'Perfil de Startup'
    url_namespace = 'usuarios:perfil-startup'


# ---------------------------------------------------------------------------
# PERFIL_EMPRESA_CLIENTE
# ---------------------------------------------------------------------------
class PerfilEmpresaClienteListView(BaseEntidadeMixin, ListView):
    model = models.PerfilEmpresaCliente
    template_name = 'usuarios/object_list.html'
    paginate_by = 20
    entidade_nome = 'Perfil de Empresa Cliente'
    url_namespace = 'usuarios:perfil-empresa-cliente'
    list_fields = [
        ('nome_fantasia', 'Nome fantasia'),
        ('cnpj', 'CNPJ'),
        ('segmento_operacional', 'Segmento'),
        ('porte_empresa', 'Porte'),
    ]


class PerfilEmpresaClienteDetailView(BaseEntidadeMixin, DetailView):
    model = models.PerfilEmpresaCliente
    template_name = 'usuarios/object_detail.html'
    entidade_nome = 'Perfil de Empresa Cliente'
    url_namespace = 'usuarios:perfil-empresa-cliente'
    list_fields = PerfilEmpresaClienteListView.list_fields + [
        ('usuario', 'Usuário responsável'),
        ('razao_social', 'Razão social'),
        ('endereco_cidade_uf', 'Cidade / UF'),
        ('criado_em', 'Criado em'),
    ]


class PerfilEmpresaClienteCreateView(BaseEntidadeMixin, CreateView):
    model = models.PerfilEmpresaCliente
    form_class = forms.PerfilEmpresaClienteForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-empresa-cliente-list')
    entidade_nome = 'Perfil de Empresa Cliente'
    url_namespace = 'usuarios:perfil-empresa-cliente'


class PerfilEmpresaClienteUpdateView(BaseEntidadeMixin, UpdateView):
    model = models.PerfilEmpresaCliente
    form_class = forms.PerfilEmpresaClienteForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-empresa-cliente-list')
    entidade_nome = 'Perfil de Empresa Cliente'
    url_namespace = 'usuarios:perfil-empresa-cliente'


class PerfilEmpresaClienteDeleteView(BaseEntidadeMixin, DeleteView):
    model = models.PerfilEmpresaCliente
    template_name = 'usuarios/object_confirm_delete.html'
    success_url = reverse_lazy('usuarios:perfil-empresa-cliente-list')
    entidade_nome = 'Perfil de Empresa Cliente'
    url_namespace = 'usuarios:perfil-empresa-cliente'


# ---------------------------------------------------------------------------
# PERFIL_INVESTIDOR
# ---------------------------------------------------------------------------
class PerfilInvestidorListView(BaseEntidadeMixin, ListView):
    model = models.PerfilInvestidor
    template_name = 'usuarios/object_list.html'
    paginate_by = 20
    entidade_nome = 'Perfil de Investidor'
    url_namespace = 'usuarios:perfil-investidor'
    list_fields = [
        ('usuario', 'Usuário'),
        ('tipo_investidor', 'Tipo'),
        ('confidencialidade_ativa', 'Confidencial'),
    ]


class PerfilInvestidorDetailView(BaseEntidadeMixin, DetailView):
    model = models.PerfilInvestidor
    template_name = 'usuarios/object_detail.html'
    entidade_nome = 'Perfil de Investidor'
    url_namespace = 'usuarios:perfil-investidor'
    list_fields = PerfilInvestidorListView.list_fields + [
        ('instituicao_origem', 'Instituição de origem'),
        ('cargo_funcao', 'Cargo / função'),
        ('ticket_medio_min', 'Ticket médio mínimo'),
        ('ticket_medio_max', 'Ticket médio máximo'),
        ('criado_em', 'Criado em'),
    ]


class PerfilInvestidorCreateView(BaseEntidadeMixin, CreateView):
    model = models.PerfilInvestidor
    form_class = forms.PerfilInvestidorForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-investidor-list')
    entidade_nome = 'Perfil de Investidor'
    url_namespace = 'usuarios:perfil-investidor'


class PerfilInvestidorUpdateView(BaseEntidadeMixin, UpdateView):
    model = models.PerfilInvestidor
    form_class = forms.PerfilInvestidorForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-investidor-list')
    entidade_nome = 'Perfil de Investidor'
    url_namespace = 'usuarios:perfil-investidor'


class PerfilInvestidorDeleteView(BaseEntidadeMixin, DeleteView):
    model = models.PerfilInvestidor
    template_name = 'usuarios/object_confirm_delete.html'
    success_url = reverse_lazy('usuarios:perfil-investidor-list')
    entidade_nome = 'Perfil de Investidor'
    url_namespace = 'usuarios:perfil-investidor'


# ---------------------------------------------------------------------------
# PERFIL_ENTIDADE_FOMENTO
# ---------------------------------------------------------------------------
class PerfilEntidadeFomentoListView(BaseEntidadeMixin, ListView):
    model = models.PerfilEntidadeFomento
    template_name = 'usuarios/object_list.html'
    paginate_by = 20
    entidade_nome = 'Perfil de Entidade de Fomento'
    url_namespace = 'usuarios:perfil-entidade-fomento'
    list_fields = [
        ('nome_instituicao', 'Instituição'),
        ('cnpj', 'CNPJ'),
        ('tipo_entidade', 'Tipo'),
        ('verificado_por_admin', 'Verificado'),
    ]


class PerfilEntidadeFomentoDetailView(BaseEntidadeMixin, DetailView):
    model = models.PerfilEntidadeFomento
    template_name = 'usuarios/object_detail.html'
    entidade_nome = 'Perfil de Entidade de Fomento'
    url_namespace = 'usuarios:perfil-entidade-fomento'
    list_fields = PerfilEntidadeFomentoListView.list_fields + [
        ('usuario', 'Usuário responsável'),
        ('site_institucional', 'Site institucional'),
        ('criado_em', 'Criado em'),
    ]


class PerfilEntidadeFomentoCreateView(BaseEntidadeMixin, CreateView):
    model = models.PerfilEntidadeFomento
    form_class = forms.PerfilEntidadeFomentoForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-entidade-fomento-list')
    entidade_nome = 'Perfil de Entidade de Fomento'
    url_namespace = 'usuarios:perfil-entidade-fomento'


class PerfilEntidadeFomentoUpdateView(BaseEntidadeMixin, UpdateView):
    model = models.PerfilEntidadeFomento
    form_class = forms.PerfilEntidadeFomentoForm
    template_name = 'usuarios/object_form.html'
    success_url = reverse_lazy('usuarios:perfil-entidade-fomento-list')
    entidade_nome = 'Perfil de Entidade de Fomento'
    url_namespace = 'usuarios:perfil-entidade-fomento'


class PerfilEntidadeFomentoDeleteView(BaseEntidadeMixin, DeleteView):
    model = models.PerfilEntidadeFomento
    template_name = 'usuarios/object_confirm_delete.html'
    success_url = reverse_lazy('usuarios:perfil-entidade-fomento-list')
    entidade_nome = 'Perfil de Entidade de Fomento'
    url_namespace = 'usuarios:perfil-entidade-fomento'
