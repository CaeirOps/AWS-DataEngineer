# Implementation Plan: AWS Data Engineer Workshop Platform

## Overview

Implementação de uma plataforma web local de workshop para a certificação DEA-C01, composta por: infraestrutura Docker Compose com dois containers (`workshop` em rede interna e `gateway` Squid com allowlist de saída), scripts de host em stdlib (`check_requirements.py` e `start.py`), servidor Flask executado por gunicorn com API REST, módulos Python de validação com boto3, frontend SPA em HTML/CSS/JS puro e estrutura de conteúdo para 10 labs com CloudFormation. Cada step `task` oferece as Trilhas Console e CLI (Requirement 11): metadados `paths`/`unavailable_paths`, conteúdo e dica por Trilha servidos pela API, preferência de Trilha persistida no `progress.json` e abas `Console | CLI` no frontend.

O plano está dividido em três partes: **Parte 1 (tasks 1 a 15)** constrói a plataforma completa e a valida com um lab de exemplo usado só em testes; **Parte 2 (tasks 16 a 25)** cria os 10 labs reais, um por vez, com aprovação do usuário antes (proposta) e depois (revisão) de cada lab; **Parte 3 (tasks 26 e 27)** verifica o catálogo completo.

## Tasks

## Parte 1: Plataforma

- [ ] 1. Configurar estrutura do projeto e infraestrutura Docker
  - [ ] 1.1 Criar Dockerfile, arquivos de dependências e arquivos de repositório
    - Criar `Dockerfile` com `python:3.11-slim`, `pip install` de `requirements.txt`, cópia de `app/` e `labs/`, `EXPOSE 5000`
    - Definir `HEALTHCHECK` via `python -c "import urllib.request..."` para `http://localhost:5000/health` (sem curl)
    - Definir `CMD` do gunicorn com `--workers 2 --bind 0.0.0.0:5000 app.server:app`
    - Criar `requirements.txt` com `flask`, `gunicorn`, `boto3` (versões fixadas)
    - Criar `requirements-dev.txt` com `pytest`, `hypothesis`
    - Criar/atualizar `.gitignore` com `progress/*` e a exceção `!progress/.gitkeep`; criar `progress/.gitkeep`
    - _Requirements: 1.1, 1.6, 1.7, 9.4_

  - [ ] 1.2 Criar docker-compose.yml
    - Não usar a chave `version`
    - Serviço `workshop`: `build: .`, sem `ports`, somente na rede `workshop-internal`, volumes `${HOME}/.aws:/root/.aws:ro` e `./progress:/app/progress`
    - Variáveis do `workshop`: `FLASK_ENV`, `AWS_PROFILE=${AWS_PROFILE:-default}`, `AWS_DEFAULT_REGION`, `HTTPS_PROXY` e `HTTP_PROXY` apontando para `http://gateway:3128`, `NO_PROXY=localhost,127.0.0.1,gateway`
    - `healthcheck` com `python -c urllib` e `restart: on-failure:3`
    - Serviço `gateway`: imagem `ubuntu/squid` com tag fixada (nunca `latest`), redes `workshop-internal` e `egress`, `depends_on` do `workshop` com `condition: service_healthy`, `restart: on-failure:3`
    - Publicar somente `127.0.0.1:${WORKSHOP_PORT:-5000}:8080` no `gateway`; montar `gateway/squid.conf` e `gateway/allowlist.txt` como `:ro`
    - Redes: `workshop-internal` com `internal: true` e `egress` com driver `bridge`
    - _Requirements: 1.5, 1.6, 1.9, 1.10, 1.12, 9.1, 9.3, 9.5_

  - [ ] 1.3 Criar configuração do Gateway (Squid)
    - Criar `gateway/squid.conf` com reverse proxy `http_port 8080 accel` encaminhando para `workshop:5000` via `cache_peer`
    - Configurar forward proxy em `http_port 3128` permitindo somente `CONNECT` na porta 443 para a ACL `allowed_domains` (arquivo `allowlist.txt`) a partir de `from_internal`, e `http_access deny all` ao final
    - Configurar `access_log` no formato `squid` (horário e destino, sem cabeçalhos de autenticação)
    - Criar `gateway/allowlist.txt` com `.amazonaws.com` e `.api.aws`
    - Conferir a ACL `from_internal` contra a sub-rede real atribuída a `workshop-internal` (`docker network inspect`) e ajustar o CIDR se necessário
    - Documentar no README que downloads do build (imagem base, `pip install`) ocorrem fora da restrição de runtime
    - _Requirements: 9.5, 9.6, 9.7_

  - [ ]* 1.4 Escrever teste de propriedade para a porta publicada
    - **Property 14: Porta publicada somente em loopback**
    - Gerar valores de `WORKSHOP_PORT` (inclusive ausente), renderizar o compose (`docker compose config` ou parse do YAML com substituição de variáveis) e verificar que existe exatamente uma porta publicada, no `gateway`, vinculada a `127.0.0.1`, e que `workshop` não publica portas
    - **Validates: Requirements 9.1, 1.9**

  - [ ]* 1.5 Escrever testes da Allowlist de saída
    - **Property 13: Saída restrita à Allowlist**
    - Teste de propriedade em função pura que espelha o `dstdomain` (`.amazonaws.com`, `.api.aws`), incluindo sufixos enganosos como `amazonaws.com.evil.example`
    - Teste de integração a partir do container `workshop`: poucos exemplos representativos, destino fora da allowlist falha e aparece no log do Gateway com destino e horário; domínio AWS na porta 443 é aceito via proxy
    - **Validates: Requirements 9.5, 9.6**

- [ ] 2. Implementar check_requirements.py
  - [ ] 2.1 Implementar verificações de pré-requisitos
    - Usar somente stdlib e `subprocess`, sem boto3 no host
    - Verificar Docker >= 20 com daemon ativo (`docker version --format '{{.Server.Version}}'`)
    - Verificar Docker Compose v2 (`docker compose version --short`)
    - Verificar AWS CLI >= 2 (`aws --version`)
    - Verificar credenciais com `aws sts get-caller-identity --profile $AWS_PROFILE` (padrão `default`)
    - Verificar porta `WORKSHOP_PORT` (padrão 5000) livre via `bind` em `127.0.0.1`
    - Não verificar permissões por lab
    - Executar todas as verificações, listar todas as falhas com pré-requisito, valor encontrado e passos de correção
    - Retornar exit code 0 (sucesso) ou 1 (falha)
    - _Requirements: 1.2, 1.3, 1.9, 1.12_

  - [ ]* 2.2 Escrever testes de propriedade para check_requirements.py
    - **Property 1: Pré-requisito ausente sempre resulta em falha descritiva**
    - **Validates: Requirements 1.2, 1.3**

- [ ] 3. Implementar start.py
  - [ ] 3.1 Implementar inicialização, health polling e diagnóstico
    - Usar somente stdlib; ler `WORKSHOP_PORT` (padrão 5000) e `AWS_PROFILE` (padrão `default`)
    - Executar `docker compose up -d --build`
    - Implementar `wait_for_health` com polling de `http://127.0.0.1:${WORKSHOP_PORT}/health` a cada 2 s por até 60 s
    - No sucesso, imprimir a URL e abrir o browser com `webbrowser.open`
    - Implementar `build_diagnostics` com `docker compose ps`, `docker compose logs --tail 50 workshop gateway`, verificação de porta ocupada, causas comuns (AirPlay Receiver do macOS na porta 5000 com sugestão `WORKSHOP_PORT=5050`, memória do Docker Desktop, erro de import, credenciais ou profile ausente) e o comando `docker compose down`
    - No timeout, imprimir o diagnóstico, retornar exit code 1 e manter os containers (não executar `docker compose down`)
    - Tornar `opener`, `clock`, `sleep` e `run` injetáveis para testes sem Docker e sem esperar 60 s
    - _Requirements: 1.4, 1.8, 1.9, 1.11, 1.12_

  - [ ]* 3.2 Escrever testes de propriedade para o diagnóstico de timeout
    - **Property 15: Timeout de health gera diagnóstico completo e falha**
    - Gerar saídas arbitrárias de `compose ps`/`logs` e estados de porta com mocks de `subprocess`, `urllib` e relógio; verificar exit code 1, conteúdo do diagnóstico e ausência de chamada a `docker compose down`
    - **Validates: Requirements 1.8**

- [ ] 4. Implementar modelos de dados e hierarquia de exceções
  - [ ] 4.1 Criar dataclasses e modelos Python
    - Implementar `ValidationResult` dataclass com campos `passed`, `message` e `hint`
    - Implementar `StepMetadata` (com `paths: Optional[list[str]]` e `unavailable_paths: Optional[dict[str, str]]`, usados somente em steps `task`) e `LabMetadata` dataclasses
    - Criar hierarquia de exceções `WorkshopError`, `CredentialsError`, `PermissionsError`, `LabNotFoundError`, `StackDeployError`
    - Criar `InvalidPathError` (`INVALID_PATH`, HTTP 400) para Trilha diferente de `console`/`cli` e `PathUnavailableError` (`PATH_UNAVAILABLE`, HTTP 409) para Trilha ausente de `paths`, com o motivo de `unavailable_paths` na mensagem
    - _Requirements: 4.1, 7.1, 11.1, 11.6_

  - [ ]* 4.2 Escrever testes de propriedade para modelos de dados
    - **Property 9: Todos os steps de todos os labs têm campos obrigatórios**
    - **Validates: Requirements 4.1, 7.1**

- [ ] 5. Implementar ProgressStore
  - [ ] 5.1 Implementar leitura, escrita e transições de estado do progress.json
    - Criar classe `ProgressStore` com `threading.Lock()` entre threads e lock de arquivo `fcntl.flock` entre processos, pois o gunicorn roda 2 workers
    - Gravar `progress.json` de forma atômica: arquivo temporário no mesmo diretório e `os.replace`, dentro da seção protegida por `flock` (ciclo ler-modificar-gravar completo)
    - Implementar `update_step` com transições de estado (`not_visited → failed/passed`, `failed → passed`)
    - Implementar `_compute_lab_status` com transições de lab (`not_started → in_progress → completed`)
    - Implementar `get_resume_step` retornando o primeiro step não-`passed`
    - Inicializar `progress.json` com `schema_version: "1.0"` e `preferences: {"path": "console"}` se não existir
    - Implementar `get_preferred_path` retornando `preferences.path`, ou `console` quando o arquivo não tiver `preferences` (compatibilidade com arquivos antigos)
    - Implementar `set_preferred_path` validando `console|cli` (senão `InvalidPathError`) e gravando somente `preferences.path` e `last_updated`, sem alterar `status`, `attempts`, `last_attempt_at` e `passed_at` dos steps
    - Fazer `PUT /api/progress` aceitar `{"preferences": {"path": "<trilha>"}}` por meio de `set_preferred_path` (a rota é ligada na tarefa 12.1)
    - _Requirements: 1.6, 2.2, 2.3, 2.4, 2.5, 9.2, 11.2, 11.3_

  - [ ]* 5.2 Escrever testes de propriedade para ProgressStore
    - **Property 2: Cálculo de progresso reflete exatamente o estado dos steps**
    - **Validates: Requirements 2.2**

  - [ ]* 5.3 Escrever testes de propriedade para get_resume_step
    - **Property 3: Step de retomada é sempre o primeiro step não concluído**
    - **Validates: Requirements 2.3, 2.4**

  - [ ]* 5.4 Escrever testes de propriedade para serialização do progress.json
    - **Property 12: Serialização/deserialização de progress.json preserva dados**
    - **Validates: Requirements 2.5, 9.2**

  - [ ]* 5.5 Escrever teste de concorrência entre processos para o ProgressStore
    - Executar atualizações simultâneas de steps distintos a partir de vários processos (`multiprocessing`) e verificar que nenhuma atualização é perdida e que o arquivo permanece JSON válido
    - _Requirements: 2.5, 9.2_

  - [ ]* 5.6 Escrever teste de propriedade para a troca de Trilha
    - **Property 17: Troca de Trilha só altera a preferência**
    - Gerar progressos válidos e sequências não vazias de `console`/`cli`, aplicar `set_preferred_path` e verificar que `preferences.path` é a última Trilha escolhida e que `status`, `attempts`, `last_attempt_at` e `passed_at` de todos os steps permanecem idênticos
    - Incluir exemplos: arquivo sem `preferences` lido como `console`; valor inválido rejeitado com `InvalidPathError`
    - **Validates: Requirements 11.2, 11.3**

- [ ] 6. Checkpoint — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [ ] 7. Implementar LabCatalog
  - [ ] 7.1 Implementar carregamento do catálogo de labs
    - Criar classe `LabCatalog` que carrega todos os `metadata.json` na inicialização
    - Implementar `get_lab` e `get_all_labs` ordenando por `lab_id`
    - Ler `paths` e `unavailable_paths` dos steps `task` e rejeitar `metadata.json` inválido na carga (`paths` vazio, Trilha ausente de `paths` sem motivo em `unavailable_paths`, Trilha simultaneamente em `paths` e `unavailable_paths`, `paths`/`unavailable_paths` em step que não é `task`)
    - Implementar `get_step_content(lab_id, step_id, path)` retornando `scenario.md`, um separador (`\n\n---\n\n`) e o arquivo da Trilha (`console.md` ou `cli.md`) de `labs/<lab_id>/steps/<step_id>/`
    - Implementar `get_step_hint(lab_id, step_id, path)` retornando `hint-console.md` ou `hint-cli.md`
    - Levantar `InvalidPathError` para `path` ausente ou diferente de `console`/`cli`, `PathUnavailableError` (com o motivo de `unavailable_paths`) para Trilha fora de `paths`, `LabNotFoundError` e `STEP_NOT_FOUND` para ids inválidos ou step que não é `task`
    - Fornecer para cada step o conteúdo único `content.md` nos steps de outros tipos (usado por `GET /api/labs/<lab_id>`)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 10.1, 11.1, 11.5, 11.6_

  - [ ]* 7.2 Escrever testes de unidade para conteúdo e dica por Trilha no LabCatalog
    - `get_step_content` retorna `scenario.md` seguido do arquivo da Trilha; `get_step_hint` retorna o `hint-<trilha>.md` correspondente
    - `path` inválido gera `InvalidPathError`; Trilha indisponível gera `PathUnavailableError` com o motivo
    - `metadata.json` inconsistente (casos listados em 7.1) é rejeitado na carga
    - _Requirements: 11.1, 11.5, 11.6_

- [ ] 8. Implementar contrato base dos validadores (app/validators/)
  - [ ] 8.1 Criar decorator `_safe_validate` e contrato base de validação
    - Implementar decorator que converte exceções boto3 em `ValidationResult(passed=False)`
    - Para `ClientError` com códigos de credencial, retornar o código e a mensagem originais do erro AWS seguidos de "Verifique as credenciais AWS do profile em uso."
    - Em um `except` separado, tratar `NoCredentialsError`, `UnauthorizedSSOTokenError` e `TokenRetrievalError` com o mesmo formato (código/mensagem originais do erro + "Verifique as credenciais AWS do profile em uso.")
    - Criar `__init__.py` do pacote `validators`
    - Os validadores de cada lab (`validators/labXX.py`) são criados nas tasks de cada lab (Parte 2), pois dependem dos steps definidos no lab
    - _Requirements: 5.3, 5.6_

  - [ ]* 8.2 Escrever testes de propriedade para tratamento de exceções AWS
    - **Property 8: Validador retorna ValidationResult para qualquer exceção AWS**
    - **Validates: Requirements 5.3, 5.6**

- [ ] 9. Implementar ValidationService
  - [ ] 9.1 Criar ValidationService que orquestra validadores e ProgressStore
    - Implementar `validate(lab_id, step_id, context)` criando `boto3.Session()` com o profile de `AWS_PROFILE`, carregando validador dinamicamente, atualizando `ProgressStore`
    - Calcular `show_hint_button` comparando `attempt_count >= hint_threshold`
    - Remover a chave `path` de `context` antes de chamar `validate_step`, de modo que o validador e as mensagens de erro não dependam da Trilha
    - Formatar resposta completa da API (passed, message, hint, step_status, show_hint_button, attempt_count)
    - _Requirements: 1.12, 5.1, 5.2, 5.4, 5.5, 11.4_

  - [ ]* 9.2 Escrever testes de propriedade para retry ilimitado
    - **Property 5: Retry ilimitado — tentativas não bloqueiam validação**
    - **Validates: Requirements 5.4**

  - [ ]* 9.3 Escrever testes de propriedade para lógica de hint threshold
    - **Property 6: Exibição de dica segue o limiar configurado**
    - **Validates: Requirements 5.5**

  - [ ]* 9.4 Escrever testes de propriedade para conclusão de lab
    - **Property 7: Lab marcado como concluído somente quando todos os steps passam**
    - **Validates: Requirements 5.7**

  - [ ]* 9.5 Testar a renovação de credenciais SSO / `aws login` com `~/.aws` montado em `:ro`
    - Criar teste de integração em `tests/integration/` (executado somente quando uma variável de ambiente indicar um profile SSO ou `aws login` real) que sobe o `workshop` com `~/.aws:ro` e chama uma validação com sessão expirada e com sessão válida
    - Verificar se o botocore falha ao gravar o token renovado no cache com o volume somente-leitura
    - Registrar o resultado (profile testado, comportamento observado) em seção do README ou `docs/` sobre credenciais SSO
    - Só considerar o requisito 9.3 atendido para profiles SSO após este teste
    - _Requirements: 5.6, 9.3, 1.12_

  - [ ]* 9.6 Escrever testes de unidade para a independência da Trilha na validação
    - Chamar `ValidationService.validate` com `context` contendo `path` (`console` e `cli`) e verificar que o validador mockado recebe `context` sem `path`
    - Verificar que o resultado e a mensagem de erro são idênticos para as duas Trilhas com a mesma sessão boto3 mockada
    - _Requirements: 11.4_


  - [ ]* 9.7 Escrever testes de propriedade para atualização de progresso na validação
    - **Property 4: Validação bem-sucedida sempre atualiza o progresso**
    - Usar validador mockado (sem depender de lab real) e `ProgressStore` temporário
    - **Validates: Requirements 5.2**

- [ ] 10. Implementar CloudFormationService
  - [ ] 10.1 Criar CloudFormationService com deploy, teardown e status
    - Implementar `deploy` iniciando criação de stack a partir de `labs/{lab_id}/cloudformation/stack.yaml`
    - Implementar `teardown` iniciando exclusão e retornando `residual_resources` do `metadata.json`
    - Implementar `get_status` consultando `describe_stacks` e retornando status e outputs
    - Usar convenção de nomenclatura `workshop-{lab_id}`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 10.2 Escrever testes de unidade para CloudFormationService
    - Testar cenários de sucesso e falha com mock boto3
    - Testar exibição de `residual_resources` no teardown
    - _Requirements: 6.4, 6.6_

- [ ] 11. Checkpoint — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [ ] 12. Implementar servidor Flask (app/server.py)
  - [ ] 12.1 Criar servidor Flask com todas as rotas da API
    - Expor o objeto `app` em `app/server.py`, executado pelo gunicorn (2 workers); `debug=False` controlado por `FLASK_ENV`; CORS desabilitado
    - Registrar `LabCatalog`, `ProgressStore`, `ValidationService`, `CloudFormationService` como singletons por processo
    - Implementar rotas: `GET /`, `GET /lab/<lab_id>`, `GET /health`
    - Implementar rotas de API: `GET /api/labs`, `GET /api/labs/<lab_id>` (com `paths` e `unavailable_paths` em cada step `task`), `GET/PUT /api/progress`
    - Fazer `PUT /api/progress` persistir a Trilha com `{"preferences": {"path": "console|cli"}}` via `ProgressStore.set_preferred_path`, retornando `INVALID_PATH` (400) para valor inválido; `GET /api/progress` inclui `preferences`
    - Implementar `GET /api/labs/<lab_id>/steps/<step_id>/content?path=console|cli` (cenário + Trilha) e `GET /api/labs/<lab_id>/steps/<step_id>/hint?path=console|cli`, retornando os JSONs do design (`lab_id`, `step_id`, `path`, `markdown` ou `hint`)
    - Mapear `INVALID_PATH` (400) e `PATH_UNAVAILABLE` (409) nas rotas de conteúdo e dica; estas rotas e a troca de Trilha não alteram o status nem as tentativas do step
    - Implementar rotas de validação e CloudFormation: `POST /api/validate/<lab_id>/<step_id>` (ignora `path` no corpo), `POST /api/deploy/<lab_id>`, `POST /api/teardown/<lab_id>`, `GET /api/stack-status/<lab_id>`
    - Registrar error handlers globais para `WorkshopError` e `Exception`
    - _Requirements: 1.4, 5.1, 6.2, 6.3, 6.4, 6.5, 6.6, 11.1, 11.3, 11.4, 11.5, 11.6_

  - [ ]* 12.2 Escrever smoke tests para o servidor Flask
    - Verificar que `GET /health` retorna `{"status": "ok"}`
    - Verificar que o `CMD` do Dockerfile usa gunicorn com `--bind 0.0.0.0:5000` e 2 workers
    - _Requirements: 1.4_

  - [ ]* 12.3 Escrever testes de unidade para as rotas de Trilha
    - `GET /api/labs/<lab_id>` retorna `paths` e `unavailable_paths` por step `task`
    - `GET .../content?path=console|cli` e `GET .../hint?path=console|cli` retornam o conteúdo da Trilha; `path` ausente ou inválido retorna `INVALID_PATH` (400); Trilha indisponível retorna `PATH_UNAVAILABLE` (409) com o motivo
    - `PUT /api/progress` com `preferences.path` válido persiste e inválido retorna `INVALID_PATH`; `progress.json` sem `preferences` é lido como `console`
    - `POST /api/validate` com `path` no corpo: o validador recebe `context` sem `path` e o resultado é o mesmo para `console` e `cli`
    - _Requirements: 11.1, 11.3, 11.4, 11.5, 11.6_

- [ ] 13. Criar lab de exemplo para testes da plataforma
  - [ ] 13.1 Criar `tests/fixtures/labs/lab-example/` e permitir diretório de labs configurável
    - Criar `metadata.json` mínimo com um step de cada tipo (`info`, `task`, `deploy`, `teardown`, `completion`), `estimated_cost_usd` e `residual_resources`
    - Criar um step `task` com as duas Trilhas (`scenario.md`, `console.md`, `cli.md`, `hint-console.md`, `hint-cli.md`) e um segundo step `task` com `unavailable_paths` (motivo não vazio) para exercitar a aba desabilitada; `content.md` nos demais steps
    - Criar `cloudformation/stack.yaml` mínimo (recurso sem custo) e um validador de exemplo com `STEP_VALIDATORS` e `validate_step` usando `@_safe_validate`
    - Fazer `LabCatalog` aceitar o diretório de labs por parâmetro ou variável de ambiente (padrão `labs/`) e `ValidationService` aceitar um carregador de validadores injetável, para que os testes usem o fixture
    - O lab de exemplo não pode aparecer no catálogo real nem ser copiado para a imagem (`labs/` continua sendo o único diretório do catálogo)
    - _Requirements: 4.1, 7.1, 11.1, 11.5, 11.6_

  - [ ]* 13.2 Escrever testes de integração da plataforma com o lab de exemplo
    - Subir o app Flask com o fixture e percorrer: listagem de labs, detalhes, conteúdo e dica por Trilha, validação (resultado, tentativas, dica), troca de Trilha, deploy/teardown com boto3 mockado e retomada de progresso
    - _Requirements: 2.2, 2.3, 5.1, 6.2, 11.1, 11.3, 11.5, 11.6_

- [ ] 14. Implementar frontend SPA (app/static/)
  - [ ] 14.1 Criar estrutura base HTML e CSS
    - Criar `app/static/index.html` como shell da SPA com todos os imports locais
    - Criar `app/static/css/workshop.css` com paleta `workshops.aws` (variáveis CSS)
    - Criar `app/static/css/components.css` com componentes reutilizáveis (cards, botões, wizard, badges)
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 14.2 Criar módulos JavaScript da SPA
    - Criar `app/static/js/app.js` com roteamento client-side (`/`, `/lab/{id}`, `/lab/{id}/{step}`)
    - Criar `app/static/js/progress.js` com funções de leitura/escrita via `GET/PUT /api/progress`
    - Criar `app/static/js/dashboard.js` com exibição dos 10 labs, contagem de steps e ponto de retomada
    - Criar `app/static/js/lab.js` com wizard de navegação, controles anterior/próximo e botão "Finalizar Lab"
    - Em `lab.js`, nos steps `task`, exibir abas `Console | CLI` acima das instruções; a aba inicial é `preferences.path` de `GET /api/progress`, e se o step não oferece essa Trilha, abrir a outra disponível sem alterar a preferência
    - Ao clicar em uma aba, carregar `GET /api/labs/<lab_id>/steps/<step_id>/content?path=<trilha>` via `fetch`, substituir o bloco de instruções sem recarregar a página e enviar `PUT /api/progress` com `{"preferences": {"path": "<trilha>"}}`; manter o resultado da última validação, o contador de tentativas e o botão "Validar"
    - Exibir Trilha presente em `unavailable_paths` como aba desabilitada (`aria-disabled="true"`) com o motivo visível no rótulo ou tooltip e na área de conteúdo
    - Converter o Markdown em HTML no cliente com renderizador local, sem CDN, e adicionar botão de copiar nos blocos de código da Trilha CLI
    - Criar `app/static/js/validator.js` com chamada `POST /api/validate` (sem enviar a Trilha), exibição de feedback sem reload e controle do botão "Ver Dica Detalhada", que busca `GET .../hint?path=<trilha ativa>` e recarrega a dica ao trocar de aba com a dica aberta
    - Criar `app/static/js/cloudformation.js` com polling a cada 5 segundos em `GET /api/stack-status` e exibição de status
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 5.5, 5.7, 6.3, 6.4, 6.5, 6.6, 6.7, 7.5, 8.2, 8.4, 11.2, 11.3, 11.5, 11.6, 11.8_

  - [ ]* 14.3 Escrever smoke tests para arquivos estáticos
    - **Property 11: Arquivos estáticos não referenciam URLs externas**
    - **Validates: Requirements 8.2**

  - [ ]* 14.4 Escrever testes de DOM para o seletor de Trilha
    - Aba de Trilha indisponível fica desabilitada e exibe o motivo
    - Clicar em uma aba carrega o conteúdo via `fetch` sem recarregar a página, envia `PUT /api/progress` e mantém o resultado da última validação
    - A aba inicial segue `preferences.path`, com fallback para a outra Trilha sem alterar a preferência
    - A dica detalhada usa a Trilha ativa e é recarregada ao trocar de aba
    - _Requirements: 11.2, 11.3, 11.5, 11.6_

- [ ] 15. Checkpoint da Parte 1 — Plataforma funcionando com o lab de exemplo
  - Garantir que todos os testes passam e que a plataforma funciona de ponta a ponta com o lab de exemplo
  - Perguntar ao usuário antes de começar os labs reais (Parte 2)

## Parte 2: Labs (um por task, com revisão do usuário entre eles)

- [ ] 16. Lab 01 - Fundamentos de S3 e Data Lake (D2, iniciante)
  - [ ] 16.1 Checkpoint de proposta do Lab 01
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (S3) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 16.2 Criar `labs/lab-01/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - Listar em `prerequisites` os cinco pré-requisitos do requisito 7.5 (conta AWS ativa com acesso administrativo, conhecimento básico de SQL, familiaridade com linha de comando, Docker instalado e Git básico)
    - _Requirements: 4.1, 6.1, 7.1, 7.5, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 16.3 Criar o conteúdo dos steps em `labs/lab-01/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 16.4 Criar `app/validators/lab01.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 01 (S3), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ]* 16.5 Escrever testes de unidade do validador do Lab 01
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 16.6 Checkpoint de revisão do Lab 01
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 02
    - _Requirements: 7.1_

- [ ] 17. Lab 02 - Catalogação e descoberta de dados (D2)
  - [ ] 17.1 Checkpoint de proposta do Lab 02
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (Glue Data Catalog e crawlers) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 17.2 Criar `labs/lab-02/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 17.3 Criar o conteúdo dos steps em `labs/lab-02/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 17.4 Criar `app/validators/lab02.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 02 (Glue Data Catalog e crawlers), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ]* 17.5 Escrever testes de unidade do validador do Lab 02
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 17.6 Checkpoint de revisão do Lab 02
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 03
    - _Requirements: 7.1_

- [ ] 18. Lab 03 - Transformação ETL com AWS Glue (D1)
  - [ ] 18.1 Checkpoint de proposta do Lab 03
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (Glue ETL jobs) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 18.2 Criar `labs/lab-03/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 18.3 Criar o conteúdo dos steps em `labs/lab-03/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 18.4 Criar `app/validators/lab03.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 03 (Glue ETL jobs), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ]* 18.5 Escrever testes de unidade do validador do Lab 03
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 18.6 Checkpoint de revisão do Lab 03
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 04
    - _Requirements: 7.1_

- [ ] 19. Lab 04 - Consultas analíticas com Athena (D3)
  - [ ] 19.1 Checkpoint de proposta do Lab 04
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (Athena) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 19.2 Criar `labs/lab-04/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 19.3 Criar o conteúdo dos steps em `labs/lab-04/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 19.4 Criar `app/validators/lab04.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 04 (Athena), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ]* 19.5 Escrever testes de unidade do validador do Lab 04
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 19.6 Checkpoint de revisão do Lab 04
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 05
    - _Requirements: 7.1_

- [ ] 20. Lab 05 - Qualidade de dados com DataBrew (D3)
  - [ ] 20.1 Checkpoint de proposta do Lab 05
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (Glue DataBrew) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 20.2 Criar `labs/lab-05/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 20.3 Criar o conteúdo dos steps em `labs/lab-05/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 20.4 Criar `app/validators/lab05.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 05 (Glue DataBrew), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ]* 20.5 Escrever testes de unidade do validador do Lab 05
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 20.6 Checkpoint de revisão do Lab 05
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 06
    - _Requirements: 7.1_

- [ ] 21. Lab 06 - Ingestão de streaming com Kinesis (D1)
  - [ ] 21.1 Checkpoint de proposta do Lab 06
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (Kinesis Data Streams) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 21.2 Criar `labs/lab-06/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 21.3 Criar o conteúdo dos steps em `labs/lab-06/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 21.4 Criar `app/validators/lab06.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 06 (Kinesis Data Streams), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 7.1_

  - [ ]* 21.5 Escrever testes de unidade do validador do Lab 06
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 21.6 Checkpoint de revisão do Lab 06
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 07
    - _Requirements: 7.1_

- [ ] 22. Lab 07 - Data Warehouse com Redshift (D2)
  - [ ] 22.1 Checkpoint de proposta do Lab 07
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (Redshift) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 22.2 Criar `labs/lab-07/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 22.3 Criar o conteúdo dos steps em `labs/lab-07/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 22.4 Criar `app/validators/lab07.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 07 (Redshift), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 7.1_

  - [ ]* 22.5 Escrever testes de unidade do validador do Lab 07
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 22.6 Checkpoint de revisão do Lab 07
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 08
    - _Requirements: 7.1_

- [ ] 23. Lab 08 - Orquestração de pipelines (D3)
  - [ ] 23.1 Checkpoint de proposta do Lab 08
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (Step Functions e EventBridge) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 23.2 Criar `labs/lab-08/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 23.3 Criar o conteúdo dos steps em `labs/lab-08/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 23.4 Criar `app/validators/lab08.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 08 (Step Functions e EventBridge), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 7.1_

  - [ ]* 23.5 Escrever testes de unidade do validador do Lab 08
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 23.6 Checkpoint de revisão do Lab 08
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 09
    - _Requirements: 7.1_

- [ ] 24. Lab 09 - Segurança e Governança (D4)
  - [ ] 24.1 Checkpoint de proposta do Lab 09
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (IAM, Lake Formation e KMS) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 24.2 Criar `labs/lab-09/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - _Requirements: 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 24.3 Criar o conteúdo dos steps em `labs/lab-09/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 24.4 Criar `app/validators/lab09.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 09 (IAM, Lake Formation e KMS), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 7.1_

  - [ ]* 24.5 Escrever testes de unidade do validador do Lab 09
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 24.6 Checkpoint de revisão do Lab 09
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para o Lab 10
    - _Requirements: 7.1_

- [ ] 25. Lab 10 - Pipeline end-to-end (D1)
  - [ ] 25.1 Checkpoint de proposta do Lab 10
    - Apresentar ao usuário: cenário, lista de steps, tasks DEA-C01 cobertas, serviços AWS (pipeline integrando os Labs 01 a 09) e estimativa de custo
    - Aguardar a aprovação do usuário antes de escrever qualquer conteúdo
    - _Requirements: 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 25.2 Criar `labs/lab-10/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `cost_disclaimer`, `dea_domains`, `dea_tasks`, `prerequisites`, `steps`, `residual_resources`
    - Em cada step `task`, declarar `paths` e, para toda Trilha ausente, `unavailable_paths` com motivo não vazio
    - Documentar em `metadata.json` (`prerequisites`) a dependência explícita dos Labs 01 a 09 como pré-requisito recomendado (7.3)
    - _Requirements: 4.1, 6.1, 7.1, 7.3, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 25.3 Criar o conteúdo dos steps em `labs/lab-10/steps/<step_id>/`
    - Nos steps `task`, criar `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` (omitindo os arquivos de Trilhas declaradas em `unavailable_paths`); nos demais tipos, criar somente `content.md`
    - Seguir 11.7 em `cli.md` e `hint-cli.md`: comandos AWS CLI v2 com `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` ou placeholders `<...>`, sem credenciais, cada comando precedido por uma linha explicando o que faz
    - Seguir 11.8 em `console.md` e `hint-console.md`: caminho `Serviço > Menu > Botão`, configurações relevantes da tela e por que importam para o DEA-C01, com o mínimo para concluir a tarefa primeiro e as explorações em seção separada
    - Manter termos técnicos em inglês no conteúdo em português
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 11.1, 11.5, 11.6, 11.7, 11.8_

  - [ ] 25.4 Criar `app/validators/lab10.py`
    - Implementar `STEP_VALIDATORS` e `validate_step` para os steps do Lab 10 (pipeline integrando os Labs 01 a 09), usando `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 7.1_

  - [ ]* 25.5 Escrever testes de unidade do validador do Lab 10
    - Testar sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 25.6 Checkpoint de revisão do Lab 10
    - Apresentar o lab pronto ao usuário e aguardar a revisão e a aprovação antes de seguir para a Parte 3
    - _Requirements: 7.1_

## Parte 3: Verificação final do catálogo

- [ ] 26. Verificação final do catálogo
  - [ ]* 26.1 Escrever smoke tests para o catálogo de labs
    - Verificar que exatamente 10 labs existem com os IDs esperados
    - Verificar que todos os `metadata.json` possuem campos obrigatórios
    - _Requirements: 7.1, 4.1_

  - [ ]* 26.2 Escrever smoke tests para cobertura de domínios DEA-C01
    - **Property 10: Cobertura de domínios DEA-C01 é completa**
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5**

  - [ ]* 26.3 Escrever smoke tests para templates CloudFormation
    - Verificar que 10 arquivos `cloudformation/stack.yaml` existem com sintaxe YAML válida
    - Parametrizar por lab, de modo que a falha aponte o lab com problema
    - _Requirements: 6.1_

  - [ ]* 26.4 Escrever teste de propriedade para o conteúdo completo por Trilha
    - **Property 16: Conteúdo completo por Trilha em todo step task**
    - Percorrer o catálogo real (parametrizado por lab, para a falha apontar o lab) e `metadata.json` gerados com `hypothesis` (combinações de `paths` e `unavailable_paths`), verificando `scenario.md`, arquivos de instruções e dica não vazios por Trilha em `paths`, motivo não vazio por Trilha ausente e `paths` nunca vazio
    - Verificar por presença que todo `cli.md` usa `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` (ou placeholders `<...>`) e todo `console.md` contém um caminho `Serviço > Menu > Botão` (11.7, 11.8; o conteúdo editorial é revisado manualmente)
    - **Validates: Requirements 11.1, 11.5, 11.6**

  - [ ]* 26.5 Escrever teste de propriedade para ausência de credenciais na Trilha CLI
    - **Property 18: Trilha CLI não contém credenciais**
    - Varrer todos os `cli.md` e `hint-cli.md` (parametrizado por lab) com o detector (regex `AKIA`/`ASIA` + 16 caracteres alfanuméricos maiúsculos, `aws_secret_access_key`, `aws_session_token`, sem diferenciar maiúsculas de minúsculas)
    - Testar o detector com textos gerados que contêm ou não os padrões
    - **Validates: Requirements 11.7, 9.3**

- [ ] 27. Checkpoint final — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Ordem de construção: primeiro a plataforma (Parte 1), depois os labs um de cada vez (Parte 2), por fim a verificação do catálogo (Parte 3). O conteúdo dos labs é a parte mais importante e o usuário participa de cada um
- Cada lab exige aprovação do usuário antes (checkpoint de proposta: cenário, steps, tasks DEA-C01, serviços AWS e custo) e depois (checkpoint de revisão do lab pronto). O Lab N+1 só começa após o checkpoint de revisão do Lab N
- Os checkpoints de proposta e de revisão dos labs aparecem como sub-tasks no Task Dependency Graph para registrar a sequência; eles exigem resposta do usuário e não são executados automaticamente
- Os validadores de cada lab (`validators/labXX.py`) ficam na task do próprio lab porque dependem dos steps definidos nele; a Parte 1 só cria o contrato base (`_safe_validate`, task 8.1)
- O lab de exemplo `tests/fixtures/labs/lab-example/` (task 13) existe só para testes; ele não aparece no catálogo real
- Os testes que dependem dos 10 labs prontos (exatamente 10 labs, Property 10, templates CloudFormation, Properties 16 e 18) estão na Parte 3 e são parametrizados por lab
- A subtask 9.5 é opcional e apenas registra se a renovação de credenciais SSO / `aws login` funciona com `~/.aws:ro`; a mensagem de erro de credenciais não depende desse resultado
- Cada task referencia requisitos específicos para rastreabilidade
- Os checkpoints garantem validação incremental ao longo da implementação
- Testes de propriedade (hypothesis) validam invariantes universais; testes de unidade validam exemplos e edge cases específicos
- Os testes de integração 1.5 e 9.5 exigem Docker e, no caso do 9.5, um profile SSO real; devem ser ignorados quando o ambiente não estiver disponível
- Todos os validadores de lab devem usar o decorator `@_safe_validate` para tratamento seguro de exceções boto3
- O frontend não usa frameworks, apenas HTML/CSS/JS puro servido pelo Flask
- A única porta publicada é `127.0.0.1:${WORKSHOP_PORT:-5000}` no serviço `gateway`; o `workshop` não publica portas
- Trilhas Console e CLI (Requirement 11): as subtasks opcionais de Trilha são 5.6 (Property 17), 7.2, 9.6, 12.3, 14.4 e, na Parte 3, 26.4 (Property 16) e 26.5 (Property 18)
- A Property 4 (antes 8.4) foi para 9.7, junto do `ValidationService`, e roda com validador mockado; a Property 8 é a 8.2
- O validador não recebe a Trilha: o `ValidationService` remove `path` de `context` e o resultado é o mesmo para Console e CLI (11.4)
- O conteúdo editorial de `console.md` e `cli.md` (11.7, 11.8) é verificado automaticamente apenas por presença de padrões e deve ser revisado manualmente pelo usuário em cada checkpoint de revisão

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "2.1", "3.1", "4.1"] },
    { "id": 1, "tasks": ["1.4", "2.2", "3.2", "4.2", "5.1"] },
    { "id": 2, "tasks": ["5.2", "5.3", "5.4", "5.5", "5.6", "7.1"] },
    { "id": 3, "tasks": ["7.2", "8.1"] },
    { "id": 4, "tasks": ["8.2", "9.1"] },
    { "id": 5, "tasks": ["9.2", "9.3", "9.4", "9.6", "9.7", "10.1"] },
    { "id": 6, "tasks": ["10.2", "12.1"] },
    { "id": 7, "tasks": ["1.5", "9.5", "12.2", "12.3", "13.1", "14.1"] },
    { "id": 8, "tasks": ["13.2", "14.2"] },
    { "id": 9, "tasks": ["14.3", "14.4"] },
    { "id": 10, "tasks": ["16.1"] },
    { "id": 11, "tasks": ["16.2"] },
    { "id": 12, "tasks": ["16.3", "16.4"] },
    { "id": 13, "tasks": ["16.5"] },
    { "id": 14, "tasks": ["16.6"] },
    { "id": 15, "tasks": ["17.1"] },
    { "id": 16, "tasks": ["17.2"] },
    { "id": 17, "tasks": ["17.3", "17.4"] },
    { "id": 18, "tasks": ["17.5"] },
    { "id": 19, "tasks": ["17.6"] },
    { "id": 20, "tasks": ["18.1"] },
    { "id": 21, "tasks": ["18.2"] },
    { "id": 22, "tasks": ["18.3", "18.4"] },
    { "id": 23, "tasks": ["18.5"] },
    { "id": 24, "tasks": ["18.6"] },
    { "id": 25, "tasks": ["19.1"] },
    { "id": 26, "tasks": ["19.2"] },
    { "id": 27, "tasks": ["19.3", "19.4"] },
    { "id": 28, "tasks": ["19.5"] },
    { "id": 29, "tasks": ["19.6"] },
    { "id": 30, "tasks": ["20.1"] },
    { "id": 31, "tasks": ["20.2"] },
    { "id": 32, "tasks": ["20.3", "20.4"] },
    { "id": 33, "tasks": ["20.5"] },
    { "id": 34, "tasks": ["20.6"] },
    { "id": 35, "tasks": ["21.1"] },
    { "id": 36, "tasks": ["21.2"] },
    { "id": 37, "tasks": ["21.3", "21.4"] },
    { "id": 38, "tasks": ["21.5"] },
    { "id": 39, "tasks": ["21.6"] },
    { "id": 40, "tasks": ["22.1"] },
    { "id": 41, "tasks": ["22.2"] },
    { "id": 42, "tasks": ["22.3", "22.4"] },
    { "id": 43, "tasks": ["22.5"] },
    { "id": 44, "tasks": ["22.6"] },
    { "id": 45, "tasks": ["23.1"] },
    { "id": 46, "tasks": ["23.2"] },
    { "id": 47, "tasks": ["23.3", "23.4"] },
    { "id": 48, "tasks": ["23.5"] },
    { "id": 49, "tasks": ["23.6"] },
    { "id": 50, "tasks": ["24.1"] },
    { "id": 51, "tasks": ["24.2"] },
    { "id": 52, "tasks": ["24.3", "24.4"] },
    { "id": 53, "tasks": ["24.5"] },
    { "id": 54, "tasks": ["24.6"] },
    { "id": 55, "tasks": ["25.1"] },
    { "id": 56, "tasks": ["25.2"] },
    { "id": 57, "tasks": ["25.3", "25.4"] },
    { "id": 58, "tasks": ["25.5"] },
    { "id": 59, "tasks": ["25.6"] },
    { "id": 60, "tasks": ["26.1", "26.2", "26.3", "26.4", "26.5"] }
  ]
}
```
