import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower


class UsuarioManager(BaseUserManager):
    """Manager customizado: login por e-mail em vez de username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email).strip().lower()
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra_fields):
        if extra_fields.get("is_staff") or extra_fields.get("is_superuser"):
            raise ValueError("Use create_superuser for privileged accounts.")
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("perfil_ativo", Usuario.PerfilAtivo.ADMIN)
        extra_fields.setdefault("termo_privacidade_aceito", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa ter is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Identidade canônica de acesso ao sistema (USUARIO no ERD).

    A senha é gerenciada pelos métodos padrão do Django (set_password /
    check_password) usando Argon2id (ver PASSWORD_HASHERS em settings.py);
    o atributo continua se chamando `password` para manter compatibilidade
    com django.contrib.auth, mas a coluna física no banco é `senha_hash`,
    como especificado na modelagem de dados.
    """

    class PerfilAtivo(models.TextChoices):
        STARTUP = "STARTUP", "Startup"
        EMPRESA_CLIENTE = "EMPRESA_CLIENTE", "Empresa Cliente"
        INVESTIDOR = "INVESTIDOR", "Investidor"
        ENTIDADE_FOMENTO = "ENTIDADE_FOMENTO", "Entidade de Fomento"
        ADMIN = "ADMIN", "Administrador"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("e-mail", max_length=255, unique=True)
    password = models.CharField("senha (hash)", max_length=255, db_column="senha_hash")
    nome_civil = models.CharField("nome civil", max_length=150)
    telefone = models.CharField("telefone", max_length=30, blank=True, null=True)
    perfil_ativo = models.CharField(
        "perfil ativo", max_length=20, choices=PerfilAtivo.choices
    )
    termo_privacidade_aceito = models.BooleanField(
        "termo de privacidade aceito", default=False
    )
    data_aceite_termos = models.DateTimeField(
        "data de aceite dos termos", auto_now_add=True
    )
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    # Requerido pelo Django (não faz parte do ERD funcional).
    is_staff = models.BooleanField("acesso ao admin", default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome_civil", "perfil_ativo"]

    class Meta:
        db_table = "usuario"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_case_insensitive")
        ]
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"User({self.pk})"

    @property
    def is_active(self):
        return self.ativo

    @is_active.setter
    def is_active(self, value):
        self.ativo = value


class PerfilStartup(models.Model):
    """Dados específicos da empresa desenvolvedora de tecnologia."""

    class SetorMercado(models.TextChoices):
        LOGISTICA = "LOGISTICA", "Logística"
        FINANCAS = "FINANCAS", "Finanças"
        VAREJO = "VAREJO", "Varejo"
        SAUDE = "SAUDE", "Saúde"
        AGRO = "AGRO", "Agro"
        EDUCACAO = "EDUCACAO", "Educação"
        SERVICOS = "SERVICOS", "Serviços"
        OUTROS = "OUTROS", "Outros"

    class EstagioDesenvolvimento(models.TextChoices):
        PROTOTIPO = "PROTOTIPO", "Protótipo"
        MVP = "MVP", "MVP"
        TRACAO_INICIAL = "TRAÇÃO_INICIAL", "Tração Inicial"
        ESCALA = "ESCALA", "Escala"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="perfil_startup",
        db_column="usuario_id",
        verbose_name="usuário",
    )
    nome_startup = models.CharField("nome da startup", max_length=100)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True, blank=True, null=True)
    website = models.CharField("website", max_length=100, blank=True, null=True)
    setor_mercado = models.CharField(
        "setor de mercado", max_length=20, choices=SetorMercado.choices
    )
    estagio_desenvolvimento = models.CharField(
        "estágio de desenvolvimento",
        max_length=20,
        choices=EstagioDesenvolvimento.choices,
    )
    pitch_resumido = models.CharField("pitch resumido", max_length=300)
    pontuacao_reputacao = models.DecimalField(
        "pontuação de reputação", max_digits=4, decimal_places=2, default=0
    )
    total_testes_concluidos = models.PositiveIntegerField(
        "total de testes concluídos", default=0
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "perfil_startup"
        verbose_name = "Perfil de Startup"
        verbose_name_plural = "Perfis de Startup"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome_startup


class PerfilEmpresaCliente(models.Model):
    """Dados da PME que busca resolver gargalos operacionais testando soluções."""

    class SegmentoOperacional(models.TextChoices):
        OFICINA_MECANICA = "OFICINA_MECANICA", "Oficina Mecânica"
        MERCADO_VAREJO = "MERCADO_VAREJO", "Mercado / Varejo"
        DISTRIBUIDORA = "DISTRIBUIDORA", "Distribuidora"
        RESTAURANTE = "RESTAURANTE", "Restaurante"
        CLINICA = "CLINICA", "Clínica"
        LOGISTICA_LOCAL = "LOGISTICA_LOCAL", "Logística Local"
        OUTROS = "OUTROS", "Outros"

    class PorteEmpresa(models.TextChoices):
        MEI = "MEI", "MEI"
        ME = "ME", "Microempresa"
        EPP = "EPP", "Empresa de Pequeno Porte"
        MEDIO_PORTE = "MEDIO_PORTE", "Médio Porte"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="perfil_empresa_cliente",
        db_column="usuario_id",
        verbose_name="usuário",
    )
    razao_social = models.CharField("razão social", max_length=120)
    nome_fantasia = models.CharField("nome fantasia", max_length=100)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    segmento_operacional = models.CharField(
        "segmento operacional", max_length=20, choices=SegmentoOperacional.choices
    )
    porte_empresa = models.CharField(
        "porte da empresa", max_length=15, choices=PorteEmpresa.choices
    )
    endereco_cidade_uf = models.CharField("cidade / UF", max_length=255)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "perfil_empresa_cliente"
        verbose_name = "Perfil de Empresa Cliente"
        verbose_name_plural = "Perfis de Empresa Cliente"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome_fantasia


class PerfilInvestidor(models.Model):
    """Preferências de investimento, com isolamento de visibilidade na vitrine."""

    class TipoInvestidor(models.TextChoices):
        ANJO = "ANJO", "Investidor Anjo"
        PRE_SEED = "PRE_SEED", "Pré-Seed"
        SEED = "SEED", "Seed"
        VENTURE_CAPITAL = "VENTURE_CAPITAL", "Venture Capital"
        CORPORATE_VC = "CORPORATE_VC", "Corporate VC"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="perfil_investidor",
        db_column="usuario_id",
        verbose_name="usuário",
    )
    instituicao_origem = models.CharField(
        "instituição de origem", max_length=120, blank=True, null=True
    )
    cargo_funcao = models.CharField(
        "cargo / função", max_length=80, blank=True, null=True
    )
    tipo_investidor = models.CharField(
        "tipo de investidor", max_length=20, choices=TipoInvestidor.choices
    )
    teses_interesse = models.JSONField("teses de interesse", default=list)
    ticket_medio_min = models.DecimalField(
        "ticket médio mínimo", max_digits=14, decimal_places=2, blank=True, null=True
    )
    ticket_medio_max = models.DecimalField(
        "ticket médio máximo", max_digits=14, decimal_places=2, blank=True, null=True
    )
    confidencialidade_ativa = models.BooleanField(
        "confidencialidade ativa", default=True
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "perfil_investidor"
        verbose_name = "Perfil de Investidor"
        verbose_name_plural = "Perfis de Investidor"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.instituicao_origem or f"Investidor {self.id}"


class PerfilEntidadeFomento(models.Model):
    """Entidades responsáveis por editais, premiações e eventos do ecossistema."""

    class TipoEntidade(models.TextChoices):
        GRANDE_EMPRESA = "GRANDE_EMPRESA", "Grande Empresa"
        HUB_INOVACAO = "HUB_INOVACAO", "Hub de Inovação"
        ACELERADORA = "ACELERADORA", "Aceleradora"
        ORGAO_GOVERNO = "ORGAO_GOVERNO", "Órgão de Governo"
        ASSOCIACAO_SETORIAL = "ASSOCIACAO_SETORIAL", "Associação Setorial"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="perfil_entidade_fomento",
        db_column="usuario_id",
        verbose_name="usuário",
    )
    nome_instituicao = models.CharField("nome da instituição", max_length=120)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    tipo_entidade = models.CharField(
        "tipo de entidade", max_length=20, choices=TipoEntidade.choices
    )
    site_institucional = models.CharField(
        "site institucional", max_length=100, blank=True, null=True
    )
    verificado_por_admin = models.BooleanField(
        "verificado por administrador", default=False
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "perfil_entidade_fomento"
        verbose_name = "Perfil de Entidade de Fomento"
        verbose_name_plural = "Perfis de Entidade de Fomento"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome_instituicao
