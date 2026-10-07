from rest_framework import serializers

from .models import (
    PerfilEmpresaCliente,
    PerfilEntidadeFomento,
    PerfilInvestidor,
    PerfilStartup,
    Usuario,
)


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer do USUARIO. A senha nunca é lida de volta (write_only) e é
    sempre gravada via `set_password`, garantindo o hash Argon2id.
    """

    password = serializers.CharField(
        write_only=True, min_length=8, style={'input_type': 'password'}
    )

    class Meta:
        model = Usuario
        fields = [
            'id',
            'email',
            'password',
            'nome_civil',
            'telefone',
            'perfil_ativo',
            'termo_privacidade_aceito',
            'data_aceite_termos',
            'ativo',
            'criado_em',
            'atualizado_em',
        ]
        read_only_fields = ['id', 'data_aceite_termos', 'criado_em', 'atualizado_em']

    def create(self, validated_data):
        password = validated_data.pop('password')
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PerfilStartupSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilStartup
        fields = [
            'id',
            'usuario',
            'nome_startup',
            'cnpj',
            'website',
            'setor_mercado',
            'estagio_desenvolvimento',
            'pitch_resumido',
            'pontuacao_reputacao',
            'total_testes_concluidos',
            'criado_em',
        ]
        read_only_fields = ['id', 'criado_em']


class PerfilEmpresaClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilEmpresaCliente
        fields = [
            'id',
            'usuario',
            'razao_social',
            'nome_fantasia',
            'cnpj',
            'segmento_operacional',
            'porte_empresa',
            'endereco_cidade_uf',
            'criado_em',
        ]
        read_only_fields = ['id', 'criado_em']


class PerfilInvestidorSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilInvestidor
        fields = [
            'id',
            'usuario',
            'instituicao_origem',
            'cargo_funcao',
            'tipo_investidor',
            'teses_interesse',
            'ticket_medio_min',
            'ticket_medio_max',
            'confidencialidade_ativa',
            'criado_em',
        ]
        read_only_fields = ['id', 'criado_em']


class PerfilEntidadeFomentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilEntidadeFomento
        fields = [
            'id',
            'usuario',
            'nome_instituicao',
            'cnpj',
            'tipo_entidade',
            'site_institucional',
            'verificado_por_admin',
            'criado_em',
        ]
        read_only_fields = ['id', 'criado_em']
