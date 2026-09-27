from django import forms

from .models import (
    PerfilEmpresaCliente,
    PerfilEntidadeFomento,
    PerfilInvestidor,
    PerfilStartup,
    Usuario,
)


class UsuarioForm(forms.ModelForm):
    """
    Form de USUARIO para o CRUD via templates. A senha é opcional na edição
    (mantém a atual se deixada em branco) e sempre gravada com set_password
    para preservar o hashing Argon2id.
    """

    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput,
        required=False,
        min_length=8,
        help_text='Deixe em branco para manter a senha atual (na edição).',
    )

    class Meta:
        model = Usuario
        fields = [
            'email',
            'nome_civil',
            'telefone',
            'perfil_ativo',
            'termo_privacidade_aceito',
            'ativo',
        ]
        widgets = {
            'perfil_ativo': forms.Select(),
        }

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password and self.instance._state.adding:
            raise forms.ValidationError('A senha é obrigatória para novos usuários.')
        return password

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            usuario.set_password(password)
        if commit:
            usuario.save()
        return usuario


class PerfilStartupForm(forms.ModelForm):
    class Meta:
        model = PerfilStartup
        fields = [
            'usuario',
            'nome_startup',
            'cnpj',
            'website',
            'setor_mercado',
            'estagio_desenvolvimento',
            'pitch_resumido',
            'pontuacao_reputacao',
            'total_testes_concluidos',
        ]


class PerfilEmpresaClienteForm(forms.ModelForm):
    class Meta:
        model = PerfilEmpresaCliente
        fields = [
            'usuario',
            'razao_social',
            'nome_fantasia',
            'cnpj',
            'segmento_operacional',
            'porte_empresa',
            'endereco_cidade_uf',
        ]


class PerfilInvestidorForm(forms.ModelForm):
    class Meta:
        model = PerfilInvestidor
        fields = [
            'usuario',
            'instituicao_origem',
            'cargo_funcao',
            'tipo_investidor',
            'ticket_medio_min',
            'ticket_medio_max',
            'confidencialidade_ativa',
        ]


class PerfilEntidadeFomentoForm(forms.ModelForm):
    class Meta:
        model = PerfilEntidadeFomento
        fields = [
            'usuario',
            'nome_instituicao',
            'cnpj',
            'tipo_entidade',
            'site_institucional',
            'verificado_por_admin',
        ]
