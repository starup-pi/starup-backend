# Vitrine, publicação e perfis — validação em 2026-10-24

Implementação organizada em commits por funcionalidade na branch `feature/matchmaking`
e integrada localmente à `main` nos dois repositórios. Nenhum push ou publicação externa foi realizado.
A aplicação de testes continua disponível em http://localhost:8001/.

## Recursos

- Vitrine em feed central, com autor e perfil, data, status, descrição completa,
  imagens, tags clicáveis, filtros por tipo/tag, paginação e avaliações reais.
- Tutoriais e explicações do processo concentrados na visão geral.
- Página `#publicar-demanda` para criar/editar demandas abertas, escolher categoria
  e visibilidade, adicionar até 8 tags de 30 caracteres e até 4 imagens de 5 MB,
  pré-visualizar/remover imagens e preservar o rascunho na memória da aba.
- Perfis públicos de clientes e startups com histórico paginado, filtros por status,
  estatísticas e notas de entregas de 1 a 5. O histórico de startups contém trabalhos
  públicos em que foram selecionadas; propostas pendentes continuam privadas.
- Imagens verificadas e regravadas sem metadados, URLs protegidas pela visibilidade
  da demanda, limpeza transacional e exclusão dos arquivos ao excluir a conta.

## Banco e dependências

Aplicada a migração aditiva `demands.0003_demand_tags_images` ao PostgreSQL local de
verificação. Os dados anteriores foram preservados e o backup prévio está em
`/tmp/starup-review-postgres/before-feed-refinement.dump`.

Dependência Pillow incluída nos três arquivos de dependências/lock. Arquivos de
imagem ficam em `MEDIA_ROOT` (por padrão `media/`, ignorado pelo Git). O Compose
possui volume persistente `media_data`. Produção precisa instalar as dependências,
aplicar a migração e manter banco e mídia nos backups. Nenhum banco de produção
foi acessado ou atualizado; o stack Docker não foi executado nesta máquina.

O tratamento segue a documentação oficial de [uploads do Django](https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/)
e suas orientações sobre [conteúdo enviado pelo usuário](https://docs.djangoproject.com/en/5.2/topics/security/#user-uploaded-content).

## Verificação

- **255 testes de backend passaram** em Python 3.12.14, Django 5.2.18 e PostgreSQL 16.15.
- **30 testes de frontend passaram**, incluindo multipart, rascunhos, imagens,
  perfis, respostas atrasadas, matchmaking e cache offline.
- 9 testes de feed/schema repetidos após o ajuste final do tipo de imagem no OpenAPI.
- Ruff, Black (100 arquivos Python), sintaxe JavaScript, `git diff --check`,
  OpenAPI validado sem avisos, `check --deploy`, `migrate --check` e
  `makemigrations --check --dry-run` passaram.
- Navegador com API real e sessão/CSRF: login de cliente, página própria de
  publicação, imagem sintética com prévia, tags, publicação, exibição da imagem
  carregada, links de autores, perfil de cliente, filtro de concluídas, perfil de
  startup com avaliação e acesso com investidor em modo de leitura privada.
- Atualização explícita do shell antigo para **v10** verificada no endereço principal.
  Console da interface final sem erros/avisos.

A prévia temporária de QA na porta 8002 foi encerrada. Django na porta 8001,
PostgreSQL local e Redis permanecem ativos para os testes manuais do usuário.
As imagens e os perfis completos usam a rede; o feed salvo offline conserva seu
texto público, sem fazer cache de arquivos privados.
