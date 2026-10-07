# Ambiente e verificação

## Docker Compose (desenvolvimento)

Copie .env.example para .env. Gere DJANGO_SECRET_KEY com secrets.token_urlsafe(48) e POSTGRES_PASSWORD com um gerador criptográfico; preencha-os no arquivo local. Não use .env.example diretamente. Mantenha o frontend irmão em ../starup-frontend.

```bash
# /var/home/pedro/Projects/starup-backend
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web pytest
```

PWA em http://localhost:8000/. API /api/v1/, OpenAPI /api/v1/schema/ e documentação /api/v1/docs/ (autenticada). O admin só permite consultar identidade por superusuário e gerenciar categorias. Usuários do produto são criados pelo cadastro.

Compose não expõe PostgreSQL ou Redis no host. O web usa runserver porque este Compose é de desenvolvimento. Para produção, construa o estágio runtime do Dockerfile (`docker build --target runtime -t starup-backend .`), com Gunicorn como comando padrão; configure HTTPS, proxy confiável, assets estáticos, secrets, Redis protegido, backups e logging sem dados pessoais. Disponibilize o frontend em PWA_ROOT na implantação.

## Python local

Python >=3.12. Criar venv, instalar .[dev], fornecer as variáveis em .env.example via ambiente e disponibilizar PostgreSQL/Redis. Settings não carregam .env automaticamente. POSTGRES_HOST será localhost quando banco estiver local. PWA_ROOT pode apontar a qualquer checkout do frontend.

```bash
# /var/home/pedro/Projects/starup-backend
python -m venv .venv
.venv/bin/python -m pip install -c requirements.lock -e '.[dev]'
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
.venv/bin/python -m pytest
.venv/bin/ruff check config src/starup_backend/accounts src/starup_backend/common src/starup_backend/profiles src/starup_backend/demands src/starup_backend/solutions src/starup_backend/reviews src/starup_backend/feed src/starup_backend/privacy src/starup_backend/notifications tests
.venv/bin/python manage.py spectacular --file openapi.yaml --validate --fail-on-warn
```

Os testes usam PostgreSQL, cache em memória e transporte push simulado. Banco precisa permitir criação do banco de testes; use um usuário dedicado. Não apontar testes ao banco de produção. MD5 aparece apenas em test_settings para acelerar fixtures; runtime usa Argon2.

## Fluxo da API

GET auth/csrf retorna csrf_token e versão da política. POST auth/register aceita campos específicos de CLIENT, STARTUP ou INVESTOR e policy_version. Não inicia sessão. POST auth/login requer cookie CSRF e X-CSRFToken e devolve token CSRF rotacionado.

CLIENT cria demanda em POST demands. STARTUP cria proposta em POST solutions. CLIENT aceita em POST solutions/{id}/transition com status ACCEPTED. STARTUP envia IN_PROGRESS e DELIVERED, este com delivery. CLIENT confirma entrega em POST reviews com solution_id e rating inteiro. GET feed é público e omite propostas e entregas. GET me é privado.

Escritas rejeitam campos desconhecidos e campos controlados pelo servidor. Papel não pode ser alterado. IDs inválidos e recursos fora do escopo não revelam proprietários.

## Web Push

Gere um par VAPID com a ferramenta oficial py-vapid instalada; mantenha a chave privada fora do repositório. Preencha VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY e VAPID_SUBJECT (mailto: contato operacional). Habilite na PWA. O worker só mostra mensagem genérica.

```bash
# /var/home/pedro/Projects/starup-backend
docker compose exec web python manage.py send_pending_push
```

Agende este comando na infraestrutura quando houver deploy. Ele envia notificações reais somente quando executado com inscrições e configuração válidas.

## Documentação anterior

README original, ER SVG e modelagem de testes auditados são referências históricas. docs/architecture.md é a especificação do MVP atual e substitui a regra antiga de revelação do investidor. Esses documentos antigos serão harmonizados quando os módulos futuros entrarem no escopo.

## Mudança de nome para StarUP

O pacote Python e o comando de console agora são starup_backend e starup-backend. Imports históricos das migrações foram ajustados, mantendo app labels, dependências, operações e nomes de tabelas. A mudança de marca não exige migração de schema. Sessões emitidas com o caminho anterior do backend de autenticação exigem novo login.

Para instalações novas, POSTGRES_DB e POSTGRES_USER usam starup como padrão. Em instalações existentes, mantenha essas variáveis com os valores atuais: renomear a marca não renomeia banco, usuário ou volume PostgreSQL.

A PWA usa um novo shell versionado, remove caches da marca anterior quando a atualização é ativada e transfere a referência local da inscrição push. O id do manifesto, scope e start_url continuam na mesma origem. Os créditos de autoria originais em LICENSE foram preservados.

A renomeação foi verificada com os mesmos 151 testes de backend e 9 testes do service worker, incluindo limpeza de caches legados. Migrações, system check e OpenAPI passaram; makemigrations não detectou alterações de schema. O novo pacote editável e comando de console foram instalados e verificados. No navegador com cache da marca anterior, a atualização explícita passou a exibir StarUP no título e no cabeçalho.

## Validação realizada em 2026-10-07

- Backend: 151 testes passaram em Python 3.12.14, Django 5.2.18 e PostgreSQL 16.2 temporário, incluindo concorrência, migrações, permissões, projeções públicas e exclusão de conta. Cobertura de 96% nos novos apps; não representa cobertura integral do legado.
- PWA: 9 testes do service worker passaram. No navegador, foram verificados os campos mínimos do cadastro de investidor, a atualização explícita do worker e a abertura do shell e feed salvo com o servidor desligado.
- Django system check, detecção de migrações pendentes, validação OpenAPI sem avisos, Ruff, Black e verificação de sintaxe JavaScript passaram.
- Migrações foram executadas somente no banco temporário de verificação. Nenhum banco existente foi atualizado nesta validação.
- Docker/Compose estão configurados com PostgreSQL 17, mas não foram executados: a máquina não possui runtime de contêiner. Compatibilidade do ambiente completo deve ser verificada onde Docker estiver disponível.
- Transporte Web Push foi testado com simulações; nenhuma notificação real foi enviada e não foram criados segredos VAPID.
