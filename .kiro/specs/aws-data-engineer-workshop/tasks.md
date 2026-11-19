# Implementation Plan: AWS Data Engineer Workshop Platform

## Overview

Implementação de uma plataforma web local de workshop para a certificação DEA-C01, composta por: infraestrutura Docker Compose com dois containers (`workshop` em rede interna e `gateway` Squid com allowlist de saída), scripts de host em stdlib (`check_requirements.py` e `start.py`), servidor Flask executado por gunicorn com API REST, módulos Python de validação com boto3, frontend SPA em HTML/CSS/JS puro e estrutura de conteúdo para 19 módulos com teoria, prática e Verificação de conhecimento, mais um Simulado final. Cada step `task` oferece as Trilhas Console e CLI (Requirement 11): metadados `paths`/`unavailable_paths`, conteúdo e dica por Trilha servidos pela API, preferência de Trilha persistida no `progress.json` e abas `Console | CLI` no frontend.

O plano está dividido em três partes: **Parte 1 (tasks 1 a 15)** constrói a plataforma completa e a valida com um lab de exemplo usado só em testes; **Parte 1B (tasks 15J a 15Q)** prepara a plataforma para módulos (Matriz de cobertura, metadata, Destaques, imagens locais, quiz, prática opcional, Aviso de custo e Simulado) e publica a `v0.2.0`; **Parte 2 (tasks 16 a 34)** cria os 19 módulos reais, um por vez, com aprovação do mantenedor antes (proposta) e depois (revisão) de cada módulo; **Parte 3 (tasks 35 e 36)** valida o Simulado com as questões reais e verifica o catálogo completo. Entre a Parte 1 e a Parte 2 entram os ajustes 15A a 15H: retomada com steps não-task, campo `services`, verificação de ambiente, e as tasks de segurança (credenciais temporárias e sessão, proteção da API local, endurecimento do container, CI e governança, validação final e configuração do GitHub), seguindo o princípio "security first".

## Tasks

## Parte 1: Plataforma

- [x] 1. Configurar estrutura do projeto e infraestrutura Docker
  - [x] 1.1 Criar Dockerfile, arquivos de dependências e arquivos de repositório
    - Criar `Dockerfile` com `python:3.11-slim`, `pip install` de `requirements.txt`, cópia de `app/` e `labs/`, `EXPOSE 5000`
    - Definir `HEALTHCHECK` via `python -c "import urllib.request..."` para `http://localhost:5000/health` (sem curl)
    - Definir `CMD` do gunicorn com `--workers 2 --bind 0.0.0.0:5000 app.server:app`
    - Criar `requirements.txt` com `flask`, `gunicorn`, `boto3` (versões fixadas)
    - Criar `requirements-dev.txt` com `pytest`, `hypothesis`
    - Criar/atualizar `.gitignore` com `progress/*` e a exceção `!progress/.gitkeep`; criar `progress/.gitkeep`
    - _Requirements: 1.1, 1.6, 1.7, 9.4_

  - [x] 1.2 Criar docker-compose.yml
    - Não usar a chave `version`
    - Serviço `workshop`: `build: .`, sem `ports`, somente na rede `workshop-internal`, volumes `${HOME}/.aws:/root/.aws:ro` e `./progress:/app/progress`
    - Variáveis do `workshop`: `FLASK_ENV`, `AWS_PROFILE=${AWS_PROFILE:-default}`, `AWS_DEFAULT_REGION`, `HTTPS_PROXY` e `HTTP_PROXY` apontando para `http://gateway:3128`, `NO_PROXY=localhost,127.0.0.1,gateway`
    - `healthcheck` com `python -c urllib` e `restart: on-failure:3`
    - Serviço `gateway`: imagem `ubuntu/squid` com tag fixada (nunca `latest`), redes `workshop-internal` e `egress`, `depends_on` do `workshop` com `condition: service_healthy`, `restart: on-failure:3`
    - Publicar somente `127.0.0.1:${WORKSHOP_PORT:-5000}:8080` no `gateway`; montar `gateway/squid.conf` e `gateway/allowlist.txt` como `:ro`
    - Redes: `workshop-internal` com `internal: true` e `egress` com driver `bridge`
    - _Requirements: 1.5, 1.6, 1.9, 1.10, 1.12, 9.1, 9.3, 9.5_

  - [x] 1.3 Criar configuração do Gateway (Squid)
    - Criar `gateway/squid.conf` com reverse proxy `http_port 8080 accel` encaminhando para `workshop:5000` via `cache_peer`
    - Configurar forward proxy em `http_port 3128` permitindo somente `CONNECT` na porta 443 para a ACL `allowed_domains` (arquivo `allowlist.txt`) a partir de `from_internal`, e `http_access deny all` ao final
    - Configurar `access_log` no formato `squid` (horário e destino, sem cabeçalhos de autenticação)
    - Criar `gateway/allowlist.txt` com `.amazonaws.com` e `.api.aws`
    - Conferir a ACL `from_internal` contra a sub-rede real atribuída a `workshop-internal` (`docker network inspect`) e ajustar o CIDR se necessário
    - Documentar no README que downloads do build (imagem base, `pip install`) ocorrem fora da restrição de runtime
    - _Requirements: 9.5, 9.6, 9.7_

  - [x]* 1.4 Escrever teste de propriedade para a porta publicada
    - **Property 14: Porta publicada somente em loopback**
    - Gerar valores de `WORKSHOP_PORT` (inclusive ausente), renderizar o compose (`docker compose config` ou parse do YAML com substituição de variáveis) e verificar que existe exatamente uma porta publicada, no `gateway`, vinculada a `127.0.0.1`, e que `workshop` não publica portas
    - **Validates: Requirements 9.1, 1.9**

  - [x]* 1.5 Escrever testes da Allowlist de saída
    - **Property 13: Saída restrita à Allowlist**
    - Teste de propriedade em função pura que espelha o `dstdomain` (`.amazonaws.com`, `.api.aws`), incluindo sufixos enganosos como `amazonaws.com.evil.example`
    - Teste de integração a partir do container `workshop`: poucos exemplos representativos, destino fora da allowlist falha e aparece no log do Gateway com destino e horário; domínio AWS na porta 443 é aceito via proxy
    - **Validates: Requirements 9.5, 9.6**

- [x] 2. Implementar check_requirements.py
  - [x] 2.1 Implementar verificações de pré-requisitos
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

  - [x]* 2.2 Escrever testes de propriedade para check_requirements.py
    - **Property 1: Pré-requisito ausente sempre resulta em falha descritiva**
    - **Validates: Requirements 1.2, 1.3**

- [x] 3. Implementar start.py
  - [x] 3.1 Implementar inicialização, health polling e diagnóstico
    - Usar somente stdlib; ler `WORKSHOP_PORT` (padrão 5000) e `AWS_PROFILE` (padrão `default`)
    - Executar `docker compose up -d --build`
    - Implementar `wait_for_health` com polling de `http://127.0.0.1:${WORKSHOP_PORT}/health` a cada 2 s por até 60 s
    - No sucesso, imprimir a URL e abrir o browser com `webbrowser.open`
    - Implementar `build_diagnostics` com `docker compose ps`, `docker compose logs --tail 50 workshop gateway`, verificação de porta ocupada, causas comuns (AirPlay Receiver do macOS na porta 5000 com sugestão `WORKSHOP_PORT=5050`, memória do Docker Desktop, erro de import, credenciais ou profile ausente) e o comando `docker compose down`
    - No timeout, imprimir o diagnóstico, retornar exit code 1 e manter os containers (não executar `docker compose down`)
    - Tornar `opener`, `clock`, `sleep` e `run` injetáveis para testes sem Docker e sem esperar 60 s
    - _Requirements: 1.4, 1.8, 1.9, 1.11, 1.12_

  - [x]* 3.2 Escrever testes de propriedade para o diagnóstico de timeout
    - **Property 15: Timeout de health gera diagnóstico completo e falha**
    - Gerar saídas arbitrárias de `compose ps`/`logs` e estados de porta com mocks de `subprocess`, `urllib` e relógio; verificar exit code 1, conteúdo do diagnóstico e ausência de chamada a `docker compose down`
    - **Validates: Requirements 1.8**

- [x] 4. Implementar modelos de dados e hierarquia de exceções
  - [x] 4.1 Criar dataclasses e modelos Python
    - Implementar `ValidationResult` dataclass com campos `passed`, `message` e `hint`
    - Implementar `StepMetadata` (com `paths: Optional[list[str]]` e `unavailable_paths: Optional[dict[str, str]]`, usados somente em steps `task`) e `LabMetadata` dataclasses
    - Criar hierarquia de exceções `WorkshopError`, `CredentialsError`, `PermissionsError`, `LabNotFoundError`, `StackDeployError`
    - Criar `InvalidPathError` (`INVALID_PATH`, HTTP 400) para Trilha diferente de `console`/`cli` e `PathUnavailableError` (`PATH_UNAVAILABLE`, HTTP 409) para Trilha ausente de `paths`, com o motivo de `unavailable_paths` na mensagem
    - _Requirements: 4.1, 7.1, 11.1, 11.6_

  - [x]* 4.2 Escrever testes de propriedade para modelos de dados
    - **Property 9: Todos os steps de todos os labs têm campos obrigatórios**
    - **Validates: Requirements 4.1, 7.1**

- [x] 5. Implementar ProgressStore
  - [x] 5.1 Implementar leitura, escrita e transições de estado do progress.json
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

  - [x]* 5.2 Escrever testes de propriedade para ProgressStore
    - **Property 2: Cálculo de progresso reflete exatamente o estado dos steps**
    - **Validates: Requirements 2.2**

  - [x]* 5.3 Escrever testes de propriedade para get_resume_step
    - **Property 3: Step de retomada é sempre o primeiro step não concluído**
    - **Validates: Requirements 2.3, 2.4**

  - [x]* 5.4 Escrever testes de propriedade para serialização do progress.json
    - **Property 12: Serialização/deserialização de progress.json preserva dados**
    - **Validates: Requirements 2.5, 9.2**

  - [x]* 5.5 Escrever teste de concorrência entre processos para o ProgressStore
    - Executar atualizações simultâneas de steps distintos a partir de vários processos (`multiprocessing`) e verificar que nenhuma atualização é perdida e que o arquivo permanece JSON válido
    - _Requirements: 2.5, 9.2_

  - [x]* 5.6 Escrever teste de propriedade para a troca de Trilha
    - **Property 17: Troca de Trilha só altera a preferência**
    - Gerar progressos válidos e sequências não vazias de `console`/`cli`, aplicar `set_preferred_path` e verificar que `preferences.path` é a última Trilha escolhida e que `status`, `attempts`, `last_attempt_at` e `passed_at` de todos os steps permanecem idênticos
    - Incluir exemplos: arquivo sem `preferences` lido como `console`; valor inválido rejeitado com `InvalidPathError`
    - **Validates: Requirements 11.2, 11.3**

- [x] 6. Checkpoint — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 7. Implementar LabCatalog
  - [x] 7.1 Implementar carregamento do catálogo de labs
    - Criar classe `LabCatalog` que carrega todos os `metadata.json` na inicialização
    - Implementar `get_lab` e `get_all_labs` ordenando por `lab_id`
    - Ler `paths` e `unavailable_paths` dos steps `task` e rejeitar `metadata.json` inválido na carga (`paths` vazio, Trilha ausente de `paths` sem motivo em `unavailable_paths`, Trilha simultaneamente em `paths` e `unavailable_paths`, `paths`/`unavailable_paths` em step que não é `task`)
    - Implementar `get_step_content(lab_id, step_id, path)` retornando `scenario.md`, um separador (`\n\n---\n\n`) e o arquivo da Trilha (`console.md` ou `cli.md`) de `labs/<lab_id>/steps/<step_id>/`
    - Implementar `get_step_hint(lab_id, step_id, path)` retornando `hint-console.md` ou `hint-cli.md`
    - Levantar `InvalidPathError` para `path` ausente ou diferente de `console`/`cli`, `PathUnavailableError` (com o motivo de `unavailable_paths`) para Trilha fora de `paths`, `LabNotFoundError` e `STEP_NOT_FOUND` para ids inválidos ou step que não é `task`
    - Fornecer para cada step o conteúdo único `content.md` nos steps de outros tipos (usado por `GET /api/labs/<lab_id>`)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 10.1, 11.1, 11.5, 11.6_

  - [x]* 7.2 Escrever testes de unidade para conteúdo e dica por Trilha no LabCatalog
    - `get_step_content` retorna `scenario.md` seguido do arquivo da Trilha; `get_step_hint` retorna o `hint-<trilha>.md` correspondente
    - `path` inválido gera `InvalidPathError`; Trilha indisponível gera `PathUnavailableError` com o motivo
    - `metadata.json` inconsistente (casos listados em 7.1) é rejeitado na carga
    - _Requirements: 11.1, 11.5, 11.6_

- [x] 8. Implementar contrato base dos validadores (app/validators/)
  - [x] 8.1 Criar decorator `_safe_validate` e contrato base de validação
    - Implementar decorator que converte exceções boto3 em `ValidationResult(passed=False)`
    - Para `ClientError` com códigos de credencial, retornar o código e a mensagem originais do erro AWS seguidos de "Verifique as credenciais AWS do profile em uso."
    - Em um `except` separado, tratar `NoCredentialsError`, `UnauthorizedSSOTokenError` e `TokenRetrievalError` com o mesmo formato (código/mensagem originais do erro + "Verifique as credenciais AWS do profile em uso.")
    - Criar `__init__.py` do pacote `validators`
    - Os validadores de cada lab (`validators/labXX.py`) são criados nas tasks de cada lab (Parte 2), pois dependem dos steps definidos no lab
    - _Requirements: 5.3, 5.6_

  - [x]* 8.2 Escrever testes de propriedade para tratamento de exceções AWS
    - **Property 8: Validador retorna ValidationResult para qualquer exceção AWS**
    - **Validates: Requirements 5.3, 5.6**

- [x] 9. Implementar ValidationService
  - [x] 9.1 Criar ValidationService que orquestra validadores e ProgressStore
    - Implementar `validate(lab_id, step_id, context)` criando `boto3.Session()` com o profile de `AWS_PROFILE`, carregando validador dinamicamente, atualizando `ProgressStore`
    - Calcular `show_hint_button` comparando `attempt_count >= hint_threshold`
    - Remover a chave `path` de `context` antes de chamar `validate_step`, de modo que o validador e as mensagens de erro não dependam da Trilha
    - Formatar resposta completa da API (passed, message, hint, step_status, show_hint_button, attempt_count)
    - _Requirements: 1.12, 5.1, 5.2, 5.4, 5.5, 11.4_

  - [x]* 9.2 Escrever testes de propriedade para retry ilimitado
    - **Property 5: Retry ilimitado — tentativas não bloqueiam validação**
    - **Validates: Requirements 5.4**

  - [x]* 9.3 Escrever testes de propriedade para lógica de hint threshold
    - **Property 6: Exibição de dica segue o limiar configurado**
    - **Validates: Requirements 5.5**

  - [x]* 9.4 Escrever testes de propriedade para conclusão de lab
    - **Property 7: Lab marcado como concluído somente quando todos os steps passam**
    - **Validates: Requirements 5.7**

  - [x]* 9.5 Testar a renovação de credenciais SSO / `aws login` com `~/.aws` montado em `:ro`
    - Criar teste de integração em `tests/integration/` (executado somente quando uma variável de ambiente indicar um profile SSO ou `aws login` real) que sobe o `workshop` com `~/.aws:ro` e chama uma validação com sessão expirada e com sessão válida
    - Verificar se o botocore falha ao gravar o token renovado no cache com o volume somente-leitura
    - Registrar o resultado (profile testado, comportamento observado) em seção do README ou `docs/` sobre credenciais SSO
    - Só considerar o requisito 9.3 atendido para profiles SSO após este teste
    - _Requirements: 5.6, 9.3, 1.12_

  - [x]* 9.6 Escrever testes de unidade para a independência da Trilha na validação
    - Chamar `ValidationService.validate` com `context` contendo `path` (`console` e `cli`) e verificar que o validador mockado recebe `context` sem `path`
    - Verificar que o resultado e a mensagem de erro são idênticos para as duas Trilhas com a mesma sessão boto3 mockada
    - _Requirements: 11.4_


  - [x]* 9.7 Escrever testes de propriedade para atualização de progresso na validação
    - **Property 4: Validação bem-sucedida sempre atualiza o progresso**
    - Usar validador mockado (sem depender de lab real) e `ProgressStore` temporário
    - **Validates: Requirements 5.2**

- [x] 10. Implementar CloudFormationService
  - [x] 10.1 Criar CloudFormationService com deploy, teardown e status
    - Implementar `deploy` iniciando criação de stack a partir de `labs/{lab_id}/cloudformation/stack.yaml`
    - Implementar `teardown` iniciando exclusão e retornando `residual_resources` do `metadata.json`
    - Implementar `get_status` consultando `describe_stacks` e retornando status e outputs
    - Usar convenção de nomenclatura `workshop-{lab_id}`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x]* 10.2 Escrever testes de unidade para CloudFormationService
    - Testar cenários de sucesso e falha com mock boto3
    - Testar exibição de `residual_resources` no teardown
    - _Requirements: 6.4, 6.6_

- [x] 11. Checkpoint — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 12. Implementar servidor Flask (app/server.py)
  - [x] 12.1 Criar servidor Flask com todas as rotas da API
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

  - [x]* 12.2 Escrever smoke tests para o servidor Flask
    - Verificar que `GET /health` retorna `{"status": "ok"}`
    - Verificar que o `CMD` do Dockerfile usa gunicorn com `--bind 0.0.0.0:5000` e 2 workers
    - _Requirements: 1.4_

  - [x]* 12.3 Escrever testes de unidade para as rotas de Trilha
    - `GET /api/labs/<lab_id>` retorna `paths` e `unavailable_paths` por step `task`
    - `GET .../content?path=console|cli` e `GET .../hint?path=console|cli` retornam o conteúdo da Trilha; `path` ausente ou inválido retorna `INVALID_PATH` (400); Trilha indisponível retorna `PATH_UNAVAILABLE` (409) com o motivo
    - `PUT /api/progress` com `preferences.path` válido persiste e inválido retorna `INVALID_PATH`; `progress.json` sem `preferences` é lido como `console`
    - `POST /api/validate` com `path` no corpo: o validador recebe `context` sem `path` e o resultado é o mesmo para `console` e `cli`
    - _Requirements: 11.1, 11.3, 11.4, 11.5, 11.6_

- [x] 13. Criar lab de exemplo para testes da plataforma
  - [x] 13.1 Criar `tests/fixtures/labs/lab-example/` e permitir diretório de labs configurável
    - Criar `metadata.json` mínimo com um step de cada tipo (`info`, `task`, `deploy`, `teardown`, `completion`), `estimated_cost_usd` e `residual_resources`
    - Criar um step `task` com as duas Trilhas (`scenario.md`, `console.md`, `cli.md`, `hint-console.md`, `hint-cli.md`) e um segundo step `task` com `unavailable_paths` (motivo não vazio) para exercitar a aba desabilitada; `content.md` nos demais steps
    - Criar `cloudformation/stack.yaml` mínimo (recurso sem custo) e um validador de exemplo com `STEP_VALIDATORS` e `validate_step` usando `@_safe_validate`
    - Fazer `LabCatalog` aceitar o diretório de labs por parâmetro ou variável de ambiente (padrão `labs/`) e `ValidationService` aceitar um carregador de validadores injetável, para que os testes usem o fixture
    - O lab de exemplo não pode aparecer no catálogo real nem ser copiado para a imagem (`labs/` continua sendo o único diretório do catálogo)
    - _Requirements: 4.1, 7.1, 11.1, 11.5, 11.6_

  - [x]* 13.2 Escrever testes de integração da plataforma com o lab de exemplo
    - Subir o app Flask com o fixture e percorrer: listagem de labs, detalhes, conteúdo e dica por Trilha, validação (resultado, tentativas, dica), troca de Trilha, deploy/teardown com boto3 mockado e retomada de progresso
    - _Requirements: 2.2, 2.3, 5.1, 6.2, 11.1, 11.3, 11.5, 11.6_

- [x] 14. Implementar frontend SPA (app/static/)
  - [x] 14.1 Criar estrutura base HTML e CSS
    - Criar `app/static/index.html` como shell da SPA com todos os imports locais
    - Criar `app/static/css/workshop.css` com paleta `workshops.aws` (variáveis CSS)
    - Criar `app/static/css/components.css` com componentes reutilizáveis (cards, botões, wizard, badges)
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 14.2 Criar módulos JavaScript da SPA
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

  - [x]* 14.3 Escrever smoke tests para arquivos estáticos
    - **Property 11: Arquivos estáticos não referenciam URLs externas**
    - **Validates: Requirements 8.2**

  - [x]* 14.4 Escrever testes de DOM para o seletor de Trilha
    - Aba de Trilha indisponível fica desabilitada e exibe o motivo
    - Clicar em uma aba carrega o conteúdo via `fetch` sem recarregar a página, envia `PUT /api/progress` e mantém o resultado da última validação
    - A aba inicial segue `preferences.path`, com fallback para a outra Trilha sem alterar a preferência
    - A dica detalhada usa a Trilha ativa e é recarregada ao trocar de aba
    - _Requirements: 11.2, 11.3, 11.5, 11.6_

- [x] 15. Checkpoint da Parte 1 — Plataforma funcionando com o lab de exemplo
  - Garantir que todos os testes passam e que a plataforma funciona de ponta a ponta com o lab de exemplo
  - Perguntar ao usuário antes de começar os labs reais (Parte 2)

## Ajustes da Parte 1 antes dos labs reais

- [x] 15A. Retomada do lab com steps não-task
  - [x] 15A.1 Implementar `mark_visited`, a rota `visit` e `create_app(config)` no backend
    - Em `app/progress_store.py`, criar `ProgressStore.mark_visited(lab_id, step_id, lab_metadata)`: marca step não-`task` como `passed` com `passed_at`, sem incrementar `attempts`, de forma idempotente; step `task` levanta `StepRequiresValidationError`; `_compute_lab_status` continua usando só steps `task` para `completed`
    - Em `app/errors.py`, criar `StepRequiresValidationError` (`STEP_REQUIRES_VALIDATION`, HTTP 409)
    - Em `app/server.py`, criar a rota `POST /api/labs/<lab_id>/steps/<step_id>/visit` (resposta com `step_status`, `attempt_count`, `lab_status` e `resume_step`; 404 para ids inválidos) e converter a inicialização em `create_app(config)`, que aceita `validator_loader` e o repassa ao `ValidationService`; manter `app = create_app(config_padrao)` para o gunicorn
    - Ajustar os testes e fixtures existentes que dependiam de variável de ambiente ou patch para injetar o carregador de validadores
    - _Requirements: 2.4, 2.6, 3.2_

  - [x] 15A.2 Ajustar o frontend para registrar a visita e usar o status do servidor
    - Em `app/static/js/progress.js` e `app/static/js/lab.js`, chamar a rota `visit` ao avançar (ou ao "Finalizar Lab") a partir de step não-`task`, atualizar o estado com a resposta e só então navegar; em caso de erro, exibir a mensagem e permanecer no step
    - Remover o uso de `sessionStorage`; o indicador do wizard e a navegação direta usam o status de `GET /api/progress` (step navegável se o status não é `not_visited` ou se é o step de retomada)
    - _Requirements: 2.4, 2.6, 3.2, 3.5_

  - [x]* 15A.3 Escrever teste de propriedade para steps não-task visitados
    - **Property 19: Marcar steps não-task não altera os steps task e avança a retomada**
    - Gerar labs com tipos de step mistos e progressos válidos, aplicar `mark_visited` em subconjuntos de steps não-`task` e verificar os itens (a) a (c) da propriedade; incluir `mark_visited` em step `task` rejeitado sem alterar o progresso
    - **Validates: Requirements 2.4, 2.6, 3.2**

  - [x]* 15A.4 Escrever testes de unidade para a rota `visit`, `create_app` e o frontend
    - Rota `visit`: step não-`task` vira `passed` com `attempt_count` 0 e `resume_step` avança; chamada repetida não altera `passed_at`; step `task` retorna 409 `STEP_REQUIRES_VALIDATION`; ids inválidos retornam 404
    - `create_app` com `validator_loader` injetado usa o carregador sem variável de ambiente
    - DOM: avançar de step não-`task` chama a rota `visit`; navegação direta usa o status do servidor; nenhuma referência a `sessionStorage` em `app/static/js/`
    - _Requirements: 2.4, 2.6, 3.2_

- [x] 15B. Campo `services` no metadata dos labs
  - [x] 15B.1 Implementar o campo obrigatório `services` no backend e no fixture
    - Em `app/models.py`, adicionar `services: list[str]` a `LabMetadata`
    - Em `app/lab_catalog.py`, rejeitar na carga `metadata.json` sem `services`, com lista vazia ou com item que não seja string não vazia
    - Em `app/server.py`, incluir `services` em `GET /api/labs` e em `GET /api/labs/<lab_id>` (com `dea_domains` neste último)
    - Atualizar `tests/fixtures/labs/lab-example/metadata.json` com `services` (por exemplo `["Amazon S3"]`) e ajustar os testes que montam `metadata.json`
    - _Requirements: 5.7, 7.1_

  - [x] 15B.2 Exibir os serviços na tela de conclusão
    - Em `app/static/js/lab.js`, na tela do step `completion`, listar `services` e `dea_domains` do lab vindos de `GET /api/labs/<lab_id>`
    - _Requirements: 5.7, 10.1_

  - [x]* 15B.3 Escrever testes de unidade para `services`
    - Catálogo: `services` ausente, vazio ou com item inválido é rejeitado; fixture válido carrega
    - API: `GET /api/labs` e `GET /api/labs/<lab_id>` retornam `services`
    - DOM: a tela de conclusão exibe os serviços e os domínios
    - _Requirements: 5.7_

- [x] 15C. Verificação de ambiente com Docker e AWS real (somente leitura)
  - [x] 15C.1 Validar compose, build, Squid e sub-rede da rede interna
    - Executar `docker compose config` e `docker compose build`; executar `squid -k parse` com a imagem fixada do gateway sobre `gateway/squid.conf`
    - Conferir o CIDR de `from_internal` com `docker network inspect` da rede `workshop-internal` e ajustar `gateway/squid.conf` se necessário
    - Não criar recursos AWS nem fazer deploy de stacks
    - _Requirements: 9.1, 9.5, 1.5, 1.10_

  - [x] 15C.2 Validar `check_requirements.py`, `start.py` e o health pelo gateway
    - Executar `python check_requirements.py` com `AWS_PROFILE=Caeiro-Admin` e `WORKSHOP_PORT` livre
    - Executar `python start.py`, confirmar `http://127.0.0.1:${WORKSHOP_PORT}/health` respondendo pelo gateway e encerrar com `docker compose down`
    - _Requirements: 1.2, 1.4, 1.9, 1.11, 1.12_

  - [x] 15C.3 Executar os testes de integração de egress e SSO e registrar no README
    - Executar os testes de integração de egress (`WORKSHOP_EGRESS_TEST=1`, tarefa 1.5) e de SSO com `~/.aws:ro` (`WORKSHOP_SSO_TEST_PROFILE=Caeiro-Admin`, tarefa 9.5)
    - Registrar o resultado (profile testado, comportamento observado) na seção "Credenciais SSO" do README
    - _Requirements: 9.3, 9.5, 9.6, 1.12_

  - [x] 15C.4 Validar uma chamada AWS real somente leitura dentro do container
    - Executar dentro do container `workshop` uma chamada `sts:GetCallerIdentity` via boto3 com o profile em uso, passando pelo proxy do gateway; registrar o resultado sem expor credenciais
    - Proibido: criar qualquer recurso AWS ou fazer deploy de stacks
    - _Requirements: 5.1, 9.3, 9.5, 1.12_

## Ajustes de segurança antes dos labs reais

Princípio: "security first", seguindo as recomendações de segurança do GitHub e da AWS. As tasks 15D a 15H substituem o modelo de volume `~/.aws` por credenciais temporárias e adicionam sessão, proteção da API local, endurecimento do container, CI e governança. Tasks 1 a 15C permanecem como histórico concluído (9.5 e 15C.3 testaram o modelo antigo de `~/.aws:ro`).

- [x] 15D. Credenciais temporárias e cronômetro de sessão
  - [x] 15D.1 Criar `host_credentials.py` (stdlib) com a exportação de credenciais
    - Implementar `TempCredentials` (campos com `repr=False`), `export_credentials(profile, run)` com `aws configure export-credentials --profile <profile> --format process` (lista de argumentos, sem shell) e `to_environment(creds)`
    - Levantar `LongLivedCredentialsError` quando faltar `SessionToken` ou `Expiration` e `CredentialsExportError` quando o comando falhar ou a saída não for JSON válido; as mensagens pedem SSO ou `aws login` e nunca contêm valores de credenciais
    - Ler o `stdout` só em memória; filtrar o `stderr` antes de exibir
    - _Requirements: 1.5, 1.14, 9.3_

  - [x] 15D.2 Adaptar `check_requirements.py` ao modelo de credenciais temporárias
    - Na verificação de credenciais, manter `aws sts get-caller-identity --profile` e chamar `host_credentials.export_credentials`; falhar com a mensagem de SSO ou `aws login` quando as credenciais forem de longa duração
    - Não imprimir valores de credenciais
    - Atualizar os testes existentes de `check_requirements.py` e a Property 1 para incluir o caso de credencial de longa duração
    - _Requirements: 1.2, 1.3, 1.12, 1.14_

  - [x] 15D.3 Adaptar `start.py` para exportar credenciais e adicionar `--refresh`
    - Exportar as credenciais do `AWS_PROFILE` e passar `to_environment(creds)` somente no `env` do subprocesso `docker compose up -d --build`, sem arquivo `.env`, sem gravar em disco e sem imprimir credenciais; imprimir apenas o horário de expiração
    - Recusar credenciais de longa duração e erro de exportação com exit code 1, antes de qualquer `docker compose`
    - Implementar `python start.py --refresh`: exportar de novo e executar `docker compose up -d --force-recreate --no-deps workshop`, com o mesmo polling de `/health`; nenhum comando de login é executado
    - Atualizar o diagnóstico de timeout (sessão expirada ou variáveis ausentes, em vez de `~/.aws`) e os testes existentes de `start.py`
    - _Requirements: 1.4, 1.5, 1.8, 1.14, 1.15, 1.16_

  - [x] 15D.4 Remover o volume `~/.aws` do `docker-compose.yml` e passar as variáveis de credenciais
    - Remover `${HOME}/.aws:/root/.aws:ro` e `AWS_PROFILE` do `workshop`; manter somente o volume `./progress`
    - Declarar em pass-through `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` e `WORKSHOP_CREDENTIALS_EXPIRATION`; definir `AWS_SHARED_CREDENTIALS_FILE=/dev/null`, `AWS_CONFIG_FILE=/dev/null` e `AWS_EC2_METADATA_DISABLED=true`; manter `AWS_DEFAULT_REGION`
    - Ajustar os testes e smoke tests existentes que afirmam o volume `~/.aws` ou `AWS_PROFILE` no `workshop`
    - _Requirements: 1.5, 1.12, 9.3, 14.6_

  - [x] 15D.5 Criar `app/session.py`, a rota `GET /api/session` e a guarda `SESSION_EXPIRED`
    - Implementar `get_session_state(env, now)` e `require_active_session()` conforme o design (`expired` com variável ausente ou inválida; `expiring` de 1 a 600 s)
    - Criar `SessionExpiredError` (`SESSION_EXPIRED`, HTTP 401) em `app/errors.py` e chamar `require_active_session()` no início de `POST /api/validate/...`, `POST /api/deploy/...`, `POST /api/teardown/...` e `GET /api/stack-status/...`, antes de criar qualquer cliente boto3
    - Em `app/validators/base.py`, acrescentar à mensagem de erro de credenciais a orientação de renovar o login no host e executar `python start.py --refresh`, sem valores de credenciais
    - _Requirements: 5.6, 12.1, 12.2, 12.3, 12.6_

  - [x] 15D.6 Implementar o cronômetro de sessão no frontend
    - Criar `app/static/js/session.js` e o espaço no cabeçalho de `index.html`: consulta `GET /api/session` na carga e a cada 60 s, contagem local a cada segundo, aviso visível em `expiring`
    - Em `expired`, desabilitar Validar, Deploy e Teardown, explicar o motivo e exibir `python start.py --refresh` com botão de copiar; manter Markdown e navegação funcionando
    - Sem scripts nem estilos inline e sem URLs externas
    - _Requirements: 12.4, 12.5, 8.2_

  - [x]* 15D.7 Escrever testes de unidade de `host_credentials.py`, `check_requirements.py` e `start.py`
    - `export_credentials` com `run` injetado: JSON completo, sem `SessionToken`, sem `Expiration`, comando com falha e saída inválida; `repr` e mensagens sem valores de credenciais
    - `start.py`: o `env` do `docker compose up` contém as quatro variáveis, nenhum arquivo é criado, `--refresh` executa exatamente o comando previsto e preserva o `gateway`, credencial de longa duração interrompe antes de qualquer `docker compose`
    - _Requirements: 1.5, 1.14, 1.15_

  - [x]* 15D.8 Escrever teste de propriedade para a sessão expirada
    - **Property 21: Sessão expirada bloqueia as rotas que chamam a AWS**
    - Em `tests/security/test_session_guard.py`: gerar instantes de expiração e relógios, verificar a classificação de `status` e que as quatro rotas AWS retornam `SESSION_EXPIRED` sem criar cliente boto3 nem alterar o `progress.json`
    - **Validates: Requirements 12.2, 12.3, 12.6**

  - [x]* 15D.9 Escrever teste de propriedade para a não exposição de credenciais
    - **Property 20: Credenciais nunca aparecem em respostas nem em logs**
    - Em `tests/security/test_no_credential_leak.py`: injetar valores gerados no ambiente, exercitar todas as rotas e erros forçados e verificar respostas, cabeçalhos e logs capturados; no host, verificar `start.py`, `check_requirements.py` e `host_credentials.py` (saída, erro e `repr`)
    - **Validates: Requirements 1.5, 5.6, 9.3, 12.1**

  - [x]* 15D.10 Escrever testes de unidade da rota de sessão e testes de DOM do cronômetro
    - `GET /api/session` com relógio injetado nos limiares 601, 600, 1 e 0 s e com variável ausente ou inválida
    - DOM: aviso em `expiring`, bloqueio de Validar, Deploy e Teardown em `expired`, comando `python start.py --refresh` exibido, sincronização a cada 60 s
    - _Requirements: 12.1, 12.2, 12.4, 12.5_

  - [x] 15D.11 Remover o teste SSO com `~/.aws:ro` e atualizar a seção de credenciais do README
    - Remover `tests/integration/test_sso_readonly.py` e as variáveis `WORKSHOP_SSO_TEST_PROFILE` de qualquer documentação
    - Substituir a seção "Credenciais SSO" do README por "Credenciais temporárias": fluxo `start.py`, `--refresh`, renovação manual do login no host e o registro de que o container não acessa `portal.sso.*`
    - _Requirements: 1.5, 1.16, 9.3_

  - [x]* 15D.12 Escrever teste de integração: o container não tem `~/.aws` e só recebe as variáveis esperadas
    - Em `tests/security/test_container_env.py` (ignorado sem Docker): com credenciais fictícias, subir o `workshop`, verificar que `/root/.aws` e qualquer `.aws` não existem, que o ambiente contém exatamente as variáveis previstas (sem `AWS_PROFILE`) e que `AWS_SHARED_CREDENTIALS_FILE` e `AWS_CONFIG_FILE` apontam para `/dev/null`
    - _Requirements: 9.3, 14.6_

- [x] 15E. Proteção da API local (CSRF e DNS rebinding)
  - [x] 15E.1 Criar `app/http_security.py` com as validações de `Host`, `Origin`, `Content-Type` e cabeçalho próprio
    - Registrar `before_request` em `create_app`: `Host` contra `127.0.0.1:<porta>` e `localhost:<porta>` com `WORKSHOP_PORT` (exceto `GET /health`); em `POST`, `PUT` e `DELETE`, `Origin` presente e igual, `Content-Type: application/json` e `X-Workshop-Request: 1`
    - Criar os erros `HostNotAllowedError` (421), `OriginNotAllowedError` (403), `UnsupportedMediaTypeError` (415) e `MissingWorkshopHeaderError` (403) em `app/errors.py`
    - Ajustar os clientes de teste e fixtures existentes (`base_url`, `Origin` e cabeçalhos padrão) para as requisições válidas
    - _Requirements: 13.1, 13.2, 13.5_

  - [x] 15E.2 Adicionar os cabeçalhos de segurança a todas as respostas
    - `after_request` com CSP `default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` e `Cross-Origin-Resource-Policy: same-origin`, inclusive em respostas de erro
    - Garantir que o frontend não usa script nem estilo inline, para que a CSP não o quebre
    - _Requirements: 13.4, 8.2_

  - [x] 15E.3 Centralizar o `fetch` do frontend em `app/static/js/api.js`
    - Enviar `Content-Type: application/json` e `X-Workshop-Request: 1` em `POST`, `PUT` e `DELETE`; migrar `progress.js`, `validator.js`, `lab.js`, `cloudformation.js` e `session.js` para o helper
    - _Requirements: 13.3_

  - [x] 15E.4 Ajustar o Gateway e o compose para que o `Host` do browser e a porta cheguem ao Flask
    - Em `gateway/squid.conf`, usar `http_port 8080 accel vhost defaultsite=workshop`, trocar a ACL `reverse_site` por `reverse_listener` (`localport 8080`), manter `http_access deny all` ao final
    - Em `docker-compose.yml`, passar `WORKSHOP_PORT=${WORKSHOP_PORT:-5000}` ao `workshop`
    - Validar a sintaxe com `squid -k parse` usando a imagem fixada
    - _Requirements: 13.1, 13.5, 9.5_

  - [x]* 15E.5 Escrever teste de propriedade para a recusa de requisições inválidas
    - **Property 22: Requisições sem Host, Origin, Content-Type ou cabeçalho próprio válidos são recusadas**
    - Em `tests/security/test_http_protection.py`: gerar combinações de `Host`, `Origin`, `Content-Type` e cabeçalho próprio e verificar que só a combinação válida é aceita, que as recusadas não alteram o `progress.json` e que os cinco cabeçalhos de segurança estão presentes
    - **Validates: Requirements 13.1, 13.2, 13.4**

  - [x]* 15E.6 Escrever testes de unidade e de DOM da proteção da API
    - `GET /health` responde com qualquer `Host`; `GET` com `Host` fora da allowlist retorna 421; `POST` sem `Origin`, com `Origin` de outro domínio, com `Content-Type` diferente de JSON ou sem `X-Workshop-Request` é recusado; cabeçalhos presentes em respostas 200, 4xx e 5xx
    - DOM: `api.js` envia os dois cabeçalhos em `POST` e `PUT`, e nenhum módulo chama `fetch` diretamente para rotas que alteram estado
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [x] 15F. Endurecimento do container e da cadeia de suprimentos
  - [x] 15F.1 Endurecer o Dockerfile
    - Fixar `python:3.11-slim` por `@sha256:` (obter o digest com `docker buildx imagetools inspect`), criar o usuário `workshop` (uid 10001) e `USER 10001:10001`, `/app/progress` pertencente a ele, `PYTHONDONTWRITEBYTECODE=1`, `pip install --require-hashes` e `--worker-tmp-dir /tmp` no gunicorn
    - Manter o `HEALTHCHECK` sem curl e o `EXPOSE 5000`
    - _Requirements: 14.1, 14.2, 14.4, 14.5_

  - [x] 15F.2 Gerar `requirements.txt` com hashes de forma reproduzível
    - Criar `requirements.in` com `flask`, `gunicorn` e `boto3`; criar `scripts/compile-requirements.sh`, que executa `pip-compile --generate-hashes` dentro da imagem `python:3.11-slim` fixada por digest; gerar `requirements.txt` com hashes de todas as dependências, inclusive transitivas
    - Documentar a regeneração no `CONTRIBUTING.md` (tarefa 15G.5)
    - _Requirements: 14.5_

  - [x] 15F.3 Endurecer o `docker-compose.yml`
    - Em `workshop`: `user` (`${WORKSHOP_UID:-10001}:${WORKSHOP_GID:-10001}`), `read_only: true`, `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `mem_limit` e `pids_limit`
    - Em `gateway`: imagem `ubuntu/squid` fixada por tag e `@sha256:`, `read_only: true` com `tmpfs` para `/tmp`, `/var/run`, `/var/log/squid` e `/var/spool/squid`, `cap_drop: [ALL]` com `cap_add` somente do mínimo que o Squid exigir (`CHOWN`, `SETUID`, `SETGID`), `no-new-privileges:true`, `mem_limit` e `pids_limit`
    - Confirmar com `docker compose up` que o Squid inicia com a menor lista de capabilities possível e registrar a lista final em comentário no compose
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

  - [x] 15F.4 Fazer o `start.py` preparar o volume de progresso para o usuário do container
    - Criar `progress/` se não existir; em Linux, exportar `WORKSHOP_UID` e `WORKSHOP_GID` do usuário atual no `env` do `docker compose`, para que o volume seja gravável; nos demais sistemas manter 10001
    - Atualizar os testes de `start.py`
    - _Requirements: 14.2_

  - [x] 15F.5 Mover os testes de segurança existentes para `tests/security/`
    - Mover `tests/unit/test_compose_ports.py` (Property 14), `tests/unit/test_allowlist.py` e `tests/unit/allowlist_matcher.py` (Property 13) e `tests/integration/test_egress.py` para `tests/security/`, atualizando os imports
    - _Requirements: 15.8, 9.1, 9.5, 9.6_

  - [x]* 15F.6 Escrever testes de smoke de segurança do Dockerfile, do compose e das dependências
    - Em `tests/security/`: o compose não monta `~/.aws`, `~/.ssh`, `~/.config`, `~/.docker` nem o socket do Docker; `workshop` não publica portas e só recebe as variáveis esperadas, sem `AWS_PROFILE`; `USER` não root; `read_only`, `cap_drop: [ALL]` e `no-new-privileges` nos dois serviços (com `cap_add` do gateway restrito ao mínimo); `mem_limit` e `pids_limit`; imagens fixadas por `@sha256:`; `requirements.txt` com `--hash=sha256:` em todas as entradas e `--require-hashes` no Dockerfile
    - _Requirements: 9.3, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [x] 15G. CI, cadeia de suprimentos e documentação pública
  - [x] 15G.1 Criar `scripts/check_dco.py` (stdlib)
    - Verificar que todos os commits de um intervalo (`base..head`) contêm `Signed-off-by:` com nome e e-mail; sair com código 1 e listar os commits sem assinatura; sem dependência de app de terceiros
    - _Requirements: 1.13, 15.3_

  - [x] 15G.2 Criar `.github/workflows/ci.yml`
    - Gatilhos `pull_request` e `push` em `main`, nunca `pull_request_target`; `permissions: contents: read` no topo; sem secrets; todas as actions de terceiros fixadas por SHA completo, com o nome e a versão em comentário
    - Jobs: testes Python e JS (`pytest` e a suíte de `tests/js`), DCO (`scripts/check_dco.py`), varredura de segredos, `pip-audit`, `hadolint` no `Dockerfile`, `cfn-lint` e `cfn-guard` nos templates de `labs/` e do fixture (regras versionadas em `.github/cfn-guard/`); `actions/checkout` com `persist-credentials: false`
    - _Requirements: 15.1, 15.2, 15.3, 1.13_

  - [x] 15G.3 Criar `.github/workflows/codeql.yml` e `.github/dependabot.yml`
    - CodeQL para `python` e `javascript` com `permissions` mínimas no topo e `security-events: write` somente no job, actions fixadas por SHA
    - Dependabot semanal para `pip`, `docker` e `github-actions`
    - _Requirements: 15.2, 15.4, 15.5_

  - [x] 15G.4 Criar `.github/CODEOWNERS` e `.github/pull_request_template.md`
    - `@CaeirOps` em `docker-compose.yml`, `Dockerfile`, `start.py`, `check_requirements.py`, `host_credentials.py`, `gateway/`, `app/server.py`, `app/session.py`, `app/http_security.py`, `requirements*.txt`, `.github/`, `tests/security/`, `LICENSE*` e `NOTICE`
    - Template de PR com checklist de segurança: sem credenciais nem dados reais, DCO, testes passando, mudanças em arquivos sensíveis descritas
    - _Requirements: 15.6, 15.7_

  - [x] 15G.5 Criar `SECURITY.md` e `CONTRIBUTING.md`
    - `SECURITY.md`: versões suportadas, reporte privado via GitHub Private Vulnerability Reporting, prazo de resposta indicativo e o que está fora de escopo
    - `CONTRIBUTING.md`: DCO com `git commit -s`, como rodar os testes (Python e JS), CI obrigatório, revisão do mantenedor para arquivos sensíveis, diretrizes (dados fictícios, sem credenciais, termos técnicos em inglês) e como regenerar `requirements.txt`
    - _Requirements: 16.1, 16.2, 14.5_

  - [x] 15G.6 Atualizar o README com as recomendações de segurança para quem usa o workshop
    - Conta AWS dedicada (sandbox) separada de contas com dados reais, alerta no AWS Budgets, permission set com o mínimo necessário em vez de `AdministratorAccess`, sessão curta e renovação manual (`python start.py --refresh`)
    - Explicar o risco residual de que a Allowlist por domínio não impede o envio de dados a um bucket S3 de terceiros e que a mitigação é conta isolada e privilégio mínimo; documentar que as variáveis de ambiente do container ficam visíveis a quem acessa o Docker do usuário
    - Não incluir instruções de configuração administrativa do repositório no GitHub
    - _Requirements: 9.7, 9.8, 9.9, 16.3_

  - [x]* 15G.7 Escrever testes de segurança dos workflows, do CODEOWNERS e da documentação
    - Em `tests/security/test_workflows.py`: sem `pull_request_target`, `permissions` mínimas no topo, `security-events: write` somente no job do CodeQL, toda `uses:` de terceiros com SHA de 40 caracteres, nenhuma referência a `secrets.`; `CODEOWNERS` cobre os caminhos sensíveis; `dependabot.yml` cobre os três ecossistemas; `SECURITY.md`, `CONTRIBUTING.md` e o template de PR existem; o README não contém instruções administrativas do GitHub
    - _Requirements: 15.1, 15.2, 15.4, 15.5, 15.6, 15.7, 16.1, 16.2, 16.3_

  - [x]* 15G.8 Escrever testes de unidade de `scripts/check_dco.py`
    - Repositório git temporário: commits assinados passam; commit sem `Signed-off-by` falha e é listado
    - _Requirements: 1.13, 15.3_

- [x] 15H. Validação final com Docker e configuração do GitHub
  - [x] 15H.1 Executar a suíte completa e validar compose, build e Squid
    - Executar `pytest` (incluindo `tests/security/`) e a suíte JS; executar `docker compose config`, `docker compose build`, `squid -k parse` na imagem fixada e `hadolint` no `Dockerfile` quando disponível
    - Corrigir qualquer falha antes de seguir
    - _Requirements: 14.1, 14.3, 14.4, 14.5, 15.3_

  - [x] 15H.2 Executar `check_requirements.py` e `start.py` reais com o profile `Caeiro-Admin`
    - Com `AWS_PROFILE=Caeiro-Admin`: `python check_requirements.py`, `python start.py` (health pelo gateway, `GET /api/session` com `status` e sem credenciais, `Host: 127.0.0.1:<porta>` aceito e `Host: evil.example` recusado com 421, `POST` sem `Origin` recusado, container não root, `read_only`, sem `~/.aws` e com as variáveis esperadas), `python start.py --refresh` (volume de progresso e `gateway` preservados) e `docker compose down` ao final
    - Executar os testes de integração com Docker de `tests/security/` (egress e ambiente do container) e uma chamada `sts:GetCallerIdentity` dentro do container, sem criar recursos AWS e sem imprimir credenciais
    - _Requirements: 1.2, 1.4, 1.5, 1.14, 1.15, 9.3, 12.1, 13.1, 13.2, 14.1, 14.6_

  - [x] 15H.3 Fazer commit e push das mudanças
    - Adicionar os arquivos por nome (nunca `git add -A`), conferir com `git status` e `git diff --cached` que não há credenciais, `progress/*` nem `.env`, criar os commits com `git commit -s` (`Signed-off-by`) e fazer push em `main`
    - _Requirements: 1.13, 15.1_

  - [x] 15H.4 Confirmar a execução do CI em `main` e obter os nomes dos status checks
    - Com `gh run list` e `gh run watch`, aguardar `ci.yml` e `codeql.yml` terminarem com sucesso em `main` e registrar os nomes exatos dos checks (`gh api repos/{owner}/{repo}/commits/<sha>/check-runs`) para uso no ruleset
    - Se algum job falhar, corrigir e repetir a partir da 15H.3
    - _Requirements: 15.3, 15.9_

  - [x] 15H.5 Configurar o repositório no GitHub com o `gh` CLI (autenticado como administrador)
    - Depende da 15I.7 (branch `release/v0.1.0` já enviada) e roda antes do PR da release, para que o próprio PR seja validado pelos rulesets
    - Ruleset em `main`: pull request obrigatório (aprovação 0 e revisão de code owners obrigatória), resolução de conversas, os 8 status checks `tests`, `dco`, `secrets`, `dependencies`, `dockerfile`, `cloudformation`, `analyze (python)` e `analyze (javascript)` com política estrita, bloqueio de exclusão e de force push, histórico linear; bypass somente do papel admin e somente no modo `pull_request`
    - Segundo ruleset para `release/**` e `hotfix/**`: pull request obrigatório e os mesmos 8 status checks, sem regra de non-fast-forward (para permitir atualizar por rebase) e sem regra de exclusão (para apagar a branch após o merge)
    - Repositório: `allow_rebase_merge: true`, `allow_squash_merge: false`, `allow_merge_commit: false`, `delete_branch_on_merge: true`, wiki e projects desligados
    - Habilitar secret scanning e push protection, Dependabot alerts e security updates, e Private Vulnerability Reporting
    - Actions: `allowed_actions: selected` somente com ações do GitHub, `sha_pinning_required: true`, `default_workflow_permissions` igual a `read`, sem permissão de aprovar PR pelo Actions e aprovação obrigatória para workflows de fork de todos os colaboradores externos
    - Conferir cada configuração relendo-a pela API; registrar o resultado somente no relatório da execução, sem criar arquivo no repositório
    - _Requirements: 15.9, 15.17, 15.18_

- [x] 15I. Correção do DCO com Dependabot, alinhamento ao Python 3.15 e gitflow (release v0.1.0)
  - [x] 15I.1 Criar a branch `release/v0.1.0` a partir de `origin/main`
    - `git fetch origin` e `git switch -c release/v0.1.0 origin/main`; todos os commits desta task usam `git commit -s` e Conventional Commits
    - _Requirements: 15.15, 15.19_

  - [x] 15I.2 Corrigir `scripts/check_dco.py` para commits do Dependabot
    - Adicionar uma allowlist explícita e mínima no próprio script com um único par: autor `dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>` e trailer `Signed-off-by: dependabot[bot] <support@github.com>`, ambos exatamente iguais; qualquer variação continua sujeita à regra de e-mail do sign-off igual ao do autor
    - _Requirements: 15.3, 15.13, 15.14_

  - [x]* 15I.3 Escrever testes de unidade do DCO com bots
    - Em `tests/unit/` (ao lado dos testes existentes de `check_dco.py`), com repositório git temporário: o par do Dependabot é aceito; e-mail do sign-off diferente, sign-off de outra identidade e nome `dependabot[bot]` com e-mail diferente falham e são listados
    - _Requirements: 15.13, 15.14_

  - [x] 15I.4 Alinhar o repositório ao Python 3.15
    - Validar em container real: `docker build` com `python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928`, instalação das dependências com `--require-hashes` e suíte de testes dentro da imagem 3.15; se algo falhar, reverter o `FROM` para 3.11 e registrar o motivo no relatório da execução
    - Se passar: atualizar `python-version` nos 3 jobs de `.github/workflows/ci.yml`, a imagem de `scripts/compile-requirements.sh` (fixada por digest), o cabeçalho e o conteúdo de `requirements.txt` (recompilar com o script na imagem 3.15) e rodar `pip-audit`; atualizar os comentários do Dockerfile e do compose e o `CONTRIBUTING.md`
    - Em `.github/dependabot.yml`, no ecossistema `docker`, ignorar `version-update:semver-major` e `version-update:semver-minor` da dependência `python`, mantendo patch e digest
    - _Requirements: 14.4, 14.5, 15.10, 15.11, 15.12_

  - [x] 15I.5 Documentar o gitflow
    - No README, criar a seção "Fluxo de trabalho (gitflow)" para contribuidores: `main`, `release/vX.Y.Z`, branches de trabalho e `hotfix/vX.Y.Z`, branch base de cada uma, rebase and merge como único método (com o motivo: squash cria commit com o e-mail padrão do GitHub e pode quebrar o DCO; merge commit quebra o histórico linear), Conventional Commits e `git commit -s`; sem instruções administrativas do GitHub
    - Referenciar a seção no `CONTRIBUTING.md` e no `.github/pull_request_template.md` (com a indicação da branch base correta); estender `tests/security/test_workflows.py` para verificar a seção do README, as referências e a ausência de instruções administrativas, e que o `dependabot.yml` contém as regras de `ignore` do Python
    - _Requirements: 15.15, 15.16, 15.17, 15.19, 16.3, 16.4, 15.12_

  - [x] 15I.6 Rodar a suíte completa localmente e no container 3.15
    - `pytest` (incluindo `tests/security/`), suíte JS, `docker compose config` e `docker compose build`; repetir a suíte Python dentro da imagem 3.15
    - _Requirements: 14.4, 14.5, 15.3, 15.10_

  - [x] 15I.7 Fazer push da branch `release/v0.1.0`
    - Adicionar os arquivos por nome, conferir `git status` e `git diff --cached` sem credenciais, `progress/*` nem `.env`, e `git push -u origin release/v0.1.0`
    - _Requirements: 15.15_

  - [x] 15I.8 Abrir o PR da release, integrar, criar a tag e o GitHub Release
    - Depende da 15H.5 concluída. Abrir o PR de `release/v0.1.0` para `main`, aguardar os 8 checks, e fazer o merge por rebase and merge somente com autorização do mantenedor (o mantenedor aprova)
    - Criar a tag anotada `v0.1.0` em `main`, publicar o GitHub Release com notas e confirmar que a branch da release foi apagada
    - _Requirements: 15.16, 15.17_

## Parte 1B: Plataforma para módulos com teoria e prática (release v0.2.0)

- [x] 15J. Abrir a release v0.2.0 e atualizar o spec
  - [x] 15J.1 Criar a branch `release/v0.2.0`
    - Criar a branch no GitHub apontando para o commit atual de `origin/main`, que já tem os 8 checks aprovados, porque o ruleset de `release/**` recusa push de commits sem checks
    - Levar o `tasks.md` com o status pós `v0.1.0` por PR de uma branch de trabalho (`chore/...`) para `release/v0.2.0`
    - _Requirements: 15.15, 15.20_
  - [x] 15J.2 Atualizar o spec para a estrutura em módulos
    - Reescrever os requisitos 4, 7 e 10, ajustar 2, 5 e 6 e criar os requisitos 17 a 20; atualizar o design (seção 5a e Properties 23 a 28) e substituir as tasks 16 a 27 não iniciadas pela estrutura em módulos
    - Apresentar o resumo ao mantenedor e abrir o PR `docs/spec-modulos` para `release/v0.2.0` só depois da aprovação
    - _Requirements: 4.6, 7.1, 10.2, 17.1, 18.1, 19.1, 20.1_

- [x] 15K. Matriz de cobertura do exame
  - [x] 15K.1 Criar `docs/exam-coverage.json`
    - Listar todas as skills do guia oficial (1.1.1 a 4.5.7) com domínio, task e texto conferido nas páginas oficiais de cada domínio, e ligar cada skill aos módulos planejados (`lab-00` a `lab-18`)
    - Registrar `source` e `retrieved_at`
    - _Requirements: 10.2, 10.3, 20.1_
  - [x] 15K.2 Escrever os testes da Matriz de cobertura
    - **Property 26: Toda skill do guia oficial está coberta**
    - Falhar se alguma skill ficar sem módulo, se um módulo citado não existir em `modules`, se houver id duplicado ou fora do formato `N.N.N`, ou se o `skills` de um metadata existente divergir da Matriz
    - Gerar um relatório de skills por módulo e por domínio (por exemplo `python scripts/coverage_report.py`)
    - **Validates: Requirements 10.2, 10.3, 10.4, 20.2**

- [x] 15L. Metadata e catálogo de módulos
  - [x] 15L.1 Escrever primeiro os testes das novas regras do catálogo
    - `skills` válidos e existentes na Matriz, `has_infrastructure` coerente com `stack.yaml` e com steps `deploy`/`teardown`, `cost_notice` obrigatório com infraestrutura e `pricing_url` `https://aws.amazon.com/`, `optional` só em `task` e com `cost_note`, `quiz` com `quiz.json` e `pass_score` válidos
    - _Requirements: 6.8, 19.3, 20.3_
  - [x] 15L.2 Implementar as regras no `LabCatalog`, no modelo de dados e na API
    - Expor `skills`, `cost_notice`, `has_infrastructure`, `optional` e `cost_note` em `GET /api/labs` e `GET /api/labs/<lab_id>`, mantendo os nomes `lab_id` e `/api/labs`
    - `CloudFormationService` e rotas de deploy, teardown e stack-status respondem `NO_INFRASTRUCTURE` (409) sem cliente boto3 em módulo sem infraestrutura
    - `_compute_lab_status` passa a considerar obrigatórios só os steps `task` não opcionais e os steps `quiz`
    - _Requirements: 4.4, 5.8, 6.8, 19.2_
  - [x] 15L.3 Atualizar o fixture `lab-example` e criar o fixture `lab-theory`
    - `lab-example` ganha `skills`, `cost_notice`, um step opcional e um step `quiz`; `lab-theory` só tem steps `info`, `quiz` e `completion`, sem infraestrutura
    - _Requirements: 4.6, 6.8_
  - [x]* 15L.4 Escrever teste de propriedade da conclusão com prática opcional
    - **Property 28: Prática opcional não bloqueia a conclusão**
    - **Validates: Requirements 5.8, 19.2**

- [x] 15M. Destaques e imagens locais no conteúdo
  - [x] 15M.1 Implementar os Destaques no `markdown.js`
    - `> [!EXAM]`, `> [!COST]`, `> [!TIP]` e `> [!WARNING]` viram `aside.callout` com os títulos "Na prova", "Custo", "Boas práticas" e "Atenção"; texto sempre escapado; estilos em `components.css`
    - _Requirements: 4.7_
  - [x] 15M.2 Implementar imagens locais e a rota de assets
    - Renderizar `<img>` só para `assets/<nome>.svg|png` com texto alternativo não vazio; rota `GET /api/labs/<lab_id>/assets/<nome>` com validação do nome, proteção contra path traversal, `nosniff` e CSP `sandbox` para SVG
    - _Requirements: 4.8, 8.2_
  - [x]* 15M.3 Escrever testes do renderizador e da rota de assets
    - **Property 27: Imagens do conteúdo são sempre locais**
    - JS: escape de HTML, cada Destaque, imagem local aceita, imagem externa, `data:`, `..` e alternativo vazio recusados. Python: nomes inválidos, path traversal, tipos e cabeçalhos
    - **Validates: Requirements 4.7, 4.8, 8.2**

- [x] 15N. Verificação de conhecimento (step `quiz`)
  - [x] 15N.1 Implementar o carregamento e a validação do `quiz.json`
    - Escolha única com 4 alternativas e 1 correta; múltipla com 5 ou mais alternativas e 2 ou mais corretas; ids únicos; `domain` e `skills` válidos
    - _Requirements: 17.1_
  - [x] 15N.2 Implementar as rotas e o Progress Store do quiz
    - `GET .../quiz` sem gabarito e sem explicações; `POST .../quiz` corrige no servidor, retorna nota, resultado por questão e explicações, registra `attempts`, `last_score`, `best_score` e `passed_at`; `INVALID_ANSWER` (400) para alternativa inexistente
    - _Requirements: 17.2, 17.3, 17.4, 17.5, 17.6_
  - [x] 15N.3 Implementar a interface do quiz
    - Questões com rádio ou caixas de seleção conforme o tipo, aviso de quantas marcar, envio via `api.js`, resultado com explicações por alternativa, nova tentativa
    - _Requirements: 17.1, 17.3_
  - [x]* 15N.4 Escrever testes de propriedade e de unidade do quiz
    - **Property 23: O gabarito nunca chega ao browser antes da resposta**
    - **Property 24: A nota é calculada corretamente para escolha única e múltipla**
    - Mais testes das rotas e de DOM da interface
    - **Validates: Requirements 17.2, 17.3, 17.4, 17.5**

- [ ] 15O. Prática opcional e Aviso de custo na interface
  - [ ] 15O.1 Exibir o selo "Opcional" e o aviso de custo do step
    - _Requirements: 19.1_
  - [ ] 15O.2 Exibir o Aviso de custo antes do `deploy`
    - Serviços cobrados com os links das páginas oficiais de preços, sem valores em USD; módulo sem infraestrutura não mostra disclaimer nem controles de stack
    - _Requirements: 4.2, 4.3, 6.8_
  - [ ]* 15O.3 Escrever testes de DOM do selo, do Aviso de custo e da conclusão sem prática opcional
    - _Requirements: 4.3, 19.1, 19.2_

- [ ] 15P. Simulado final
  - [ ] 15P.1 Implementar o sorteio, as rotas e o Progress Store do Simulado
    - `POST /api/mock-exam` sorteia sem repetição com a cota por domínio e a regra de arredondamento do design; `POST /api/mock-exam/<attempt_id>/submit` corrige e retorna nota geral e por domínio; últimas 20 tentativas no Progress Store
    - _Requirements: 18.1, 18.2, 18.3, 18.5_
  - [ ] 15P.2 Implementar a interface do Simulado
    - Rota `/mock-exam`, cronômetro opcional de 130 minutos, navegação entre questões, resultado por domínio e histórico de tentativas
    - _Requirements: 18.3, 18.4_
  - [ ]* 15P.3 Escrever testes de propriedade e de unidade do Simulado
    - **Property 25: O Simulado respeita os pesos dos domínios e não repete questões**
    - **Validates: Requirements 7.4, 18.2**

- [ ] 15Q. Integração, documentação e release v0.2.0
  - [ ] 15Q.1 Executar a suíte completa, os testes com Docker e o `start.py` real
    - `env -u WORKSHOP_PORT .venv/bin/python -m pytest tests -q -rs`, `node --test "tests/js/*.test.mjs"`, testes com Docker separados por arquivo e `start.py` com `AWS_PROFILE=Caeiro-Admin WORKSHOP_PORT=5050`; conferir no browser os fixtures de ponta a ponta
    - _Requirements: 1.4, 17.1, 18.1_
  - [ ] 15Q.2 Atualizar README e `CONTRIBUTING.md`
    - README: lista dos 19 módulos, Verificação de conhecimento, Simulado, prática opcional, Aviso de custo, criação de release a partir do commit da `main` no gitflow e seção "Melhorias futuras" com a estimativa de custo em USD. `CONTRIBUTING.md`: como escrever um módulo (estrutura, Destaques, imagens, quiz, Aviso de custo, cenário AnyCompany, Matriz de cobertura)
    - _Requirements: 16.2, 19.4_
  - [ ] 15Q.3 Publicar a release v0.2.0
    - PR de `release/v0.2.0` para `main` com os 8 checks verdes, merge por rebase com `--admin`, tag anotada `v0.2.0` e GitHub Release
    - _Requirements: 15.16_

## Parte 2: Módulos (um por task, com proposta e revisão do mantenedor)

- [ ] 16. Módulo 00 - Fundamentos de engenharia de dados (D1, D2)
  - [ ] 16.1 Checkpoint de proposta do Módulo 00
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende da task 15Q (release v0.2.0 publicada)
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 16.2 Criar `labs/lab-00/metadata.json`
    - Módulo sem infraestrutura: `has_infrastructure: false`, sem `stack.yaml`, sem steps `deploy`/`teardown`; listar os pré-requisitos do workshop em `prerequisites`
    - _Requirements: 4.4, 6.8, 7.5, 20.2_
  - [ ] 16.3 Escrever o conteúdo teórico em `labs/lab-00/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 16.5 Escrever a Verificação de conhecimento do Módulo 00
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 16.8 Checkpoint de revisão do Módulo 00
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 17. Módulo 01 - S3 e data lake (D2, D1)
  - [ ] 17.1 Checkpoint de proposta do Módulo 01
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 00
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 17.2 Criar `labs/lab-01/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 17.3 Escrever o conteúdo teórico em `labs/lab-01/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 17.4 Escrever as práticas (steps `task`) do Módulo 01
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 17.5 Escrever a Verificação de conhecimento do Módulo 01
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 17.6 Criar `app/validators/lab01.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 17.7 Escrever testes de unidade do validador do Módulo 01
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 17.8 Checkpoint de revisão do Módulo 01
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 18. Módulo 02 - Catálogo de dados (D2)
  - [ ] 18.1 Checkpoint de proposta do Módulo 02
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 01
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 18.2 Criar `labs/lab-02/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 18.3 Escrever o conteúdo teórico em `labs/lab-02/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 18.4 Escrever as práticas (steps `task`) do Módulo 02
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 18.5 Escrever a Verificação de conhecimento do Módulo 02
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 18.6 Criar `app/validators/lab02.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 18.7 Escrever testes de unidade do validador do Módulo 02
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 18.8 Checkpoint de revisão do Módulo 02
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 19. Módulo 03 - Athena e SQL analítico (D3)
  - [ ] 19.1 Checkpoint de proposta do Módulo 03
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 02
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 19.2 Criar `labs/lab-03/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 19.3 Escrever o conteúdo teórico em `labs/lab-03/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 19.4 Escrever as práticas (steps `task`) do Módulo 03
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 19.5 Escrever a Verificação de conhecimento do Módulo 03
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 19.6 Criar `app/validators/lab03.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 19.7 Escrever testes de unidade do validador do Módulo 03
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 19.8 Checkpoint de revisão do Módulo 03
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 20. Módulo 04 - ETL com Glue e PySpark (D1, D3)
  - [ ] 20.1 Checkpoint de proposta do Módulo 04
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 03
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 20.2 Criar `labs/lab-04/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 20.3 Escrever o conteúdo teórico em `labs/lab-04/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 20.4 Escrever as práticas (steps `task`) do Módulo 04
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 20.5 Escrever a Verificação de conhecimento do Módulo 04
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 20.6 Criar `app/validators/lab04.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 20.7 Escrever testes de unidade do validador do Módulo 04
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 20.8 Checkpoint de revisão do Módulo 04
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 21. Módulo 05 - EMR Serverless e escolha do motor de processamento (D1, D3)
  - [ ] 21.1 Checkpoint de proposta do Módulo 05
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 04
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 21.2 Criar `labs/lab-05/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 21.3 Escrever o conteúdo teórico em `labs/lab-05/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 21.4 Escrever as práticas (steps `task`) do Módulo 05
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 21.5 Escrever a Verificação de conhecimento do Módulo 05
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 21.6 Criar `app/validators/lab05.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 21.7 Escrever testes de unidade do validador do Módulo 05
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 21.8 Checkpoint de revisão do Módulo 05
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 22. Módulo 06 - Qualidade de dados (D3)
  - [ ] 22.1 Checkpoint de proposta do Módulo 06
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 05
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 22.2 Criar `labs/lab-06/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 22.3 Escrever o conteúdo teórico em `labs/lab-06/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 22.4 Escrever as práticas (steps `task`) do Módulo 06
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 22.5 Escrever a Verificação de conhecimento do Módulo 06
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 22.6 Criar `app/validators/lab06.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 22.7 Escrever testes de unidade do validador do Módulo 06
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 22.8 Checkpoint de revisão do Módulo 06
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 23. Módulo 07 - Streaming (D1)
  - [ ] 23.1 Checkpoint de proposta do Módulo 07
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 06
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 23.2 Criar `labs/lab-07/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 23.3 Escrever o conteúdo teórico em `labs/lab-07/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 23.4 Escrever as práticas (steps `task`) do Módulo 07
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 23.5 Escrever a Verificação de conhecimento do Módulo 07
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 23.6 Criar `app/validators/lab07.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 23.7 Escrever testes de unidade do validador do Módulo 07
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 23.8 Checkpoint de revisão do Módulo 07
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 24. Módulo 08 - DynamoDB e bancos operacionais (D2, D1)
  - [ ] 24.1 Checkpoint de proposta do Módulo 08
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 07
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 24.2 Criar `labs/lab-08/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 24.3 Escrever o conteúdo teórico em `labs/lab-08/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 24.4 Escrever as práticas (steps `task`) do Módulo 08
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 24.5 Escrever a Verificação de conhecimento do Módulo 08
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 24.6 Criar `app/validators/lab08.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 24.7 Escrever testes de unidade do validador do Módulo 08
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 24.8 Checkpoint de revisão do Módulo 08
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 25. Módulo 09 - Migração e CDC (D1, D2, D4)
  - [ ] 25.1 Checkpoint de proposta do Módulo 09
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 08
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 25.2 Criar `labs/lab-09/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 25.3 Escrever o conteúdo teórico em `labs/lab-09/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 25.4 Escrever as práticas (steps `task`) do Módulo 09
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 25.5 Escrever a Verificação de conhecimento do Módulo 09
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 25.6 Criar `app/validators/lab09.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 25.7 Escrever testes de unidade do validador do Módulo 09
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 25.8 Checkpoint de revisão do Módulo 09
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 26. Módulo 10 - Redshift (D2, D3, D4)
  - [ ] 26.1 Checkpoint de proposta do Módulo 10
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 09
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 26.2 Criar `labs/lab-10/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 26.3 Escrever o conteúdo teórico em `labs/lab-10/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 26.4 Escrever as práticas (steps `task`) do Módulo 10
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 26.5 Escrever a Verificação de conhecimento do Módulo 10
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 26.6 Criar `app/validators/lab10.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 26.7 Escrever testes de unidade do validador do Módulo 10
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 26.8 Checkpoint de revisão do Módulo 10
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 27. Módulo 11 - Open table formats (D2)
  - [ ] 27.1 Checkpoint de proposta do Módulo 11
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 10
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 27.2 Criar `labs/lab-11/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 27.3 Escrever o conteúdo teórico em `labs/lab-11/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 27.4 Escrever as práticas (steps `task`) do Módulo 11
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 27.5 Escrever a Verificação de conhecimento do Módulo 11
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 27.6 Criar `app/validators/lab11.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 27.7 Escrever testes de unidade do validador do Módulo 11
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 27.8 Checkpoint de revisão do Módulo 11
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 28. Módulo 12 - Orquestração (D1, D3)
  - [ ] 28.1 Checkpoint de proposta do Módulo 12
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 11
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 28.2 Criar `labs/lab-12/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 28.3 Escrever o conteúdo teórico em `labs/lab-12/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 28.4 Escrever as práticas (steps `task`) do Módulo 12
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 28.5 Escrever a Verificação de conhecimento do Módulo 12
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 28.6 Criar `app/validators/lab12.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 28.7 Escrever testes de unidade do validador do Módulo 12
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 28.8 Checkpoint de revisão do Módulo 12
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 29. Módulo 13 - Observabilidade e operação (D3, D4)
  - [ ] 29.1 Checkpoint de proposta do Módulo 13
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 12
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 29.2 Criar `labs/lab-13/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 29.3 Escrever o conteúdo teórico em `labs/lab-13/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 29.4 Escrever as práticas (steps `task`) do Módulo 13
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 29.5 Escrever a Verificação de conhecimento do Módulo 13
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 29.6 Criar `app/validators/lab13.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 29.7 Escrever testes de unidade do validador do Módulo 13
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 29.8 Checkpoint de revisão do Módulo 13
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 30. Módulo 14 - Segurança (D4)
  - [ ] 30.1 Checkpoint de proposta do Módulo 14
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 13
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 30.2 Criar `labs/lab-14/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 30.3 Escrever o conteúdo teórico em `labs/lab-14/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 30.4 Escrever as práticas (steps `task`) do Módulo 14
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 30.5 Escrever a Verificação de conhecimento do Módulo 14
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 30.6 Criar `app/validators/lab14.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 30.7 Escrever testes de unidade do validador do Módulo 14
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 30.8 Checkpoint de revisão do Módulo 14
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 31. Módulo 15 - Governança (D4)
  - [ ] 31.1 Checkpoint de proposta do Módulo 15
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 14
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 31.2 Criar `labs/lab-15/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 31.3 Escrever o conteúdo teórico em `labs/lab-15/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 31.4 Escrever as práticas (steps `task`) do Módulo 15
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 31.5 Escrever a Verificação de conhecimento do Módulo 15
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 31.6 Criar `app/validators/lab15.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 31.7 Escrever testes de unidade do validador do Módulo 15
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 31.8 Checkpoint de revisão do Módulo 15
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 32. Módulo 16 - Dados para IA (D1, D2)
  - [ ] 32.1 Checkpoint de proposta do Módulo 16
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 15
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 32.2 Criar `labs/lab-16/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 32.3 Escrever o conteúdo teórico em `labs/lab-16/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 32.4 Escrever as práticas (steps `task`) do Módulo 16
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 32.5 Escrever a Verificação de conhecimento do Módulo 16
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 32.6 Criar `app/validators/lab16.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 32.7 Escrever testes de unidade do validador do Módulo 16
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 32.8 Checkpoint de revisão do Módulo 16
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 33. Módulo 17 - Data APIs, IaC e CI/CD (D1, D3)
  - [ ] 33.1 Checkpoint de proposta do Módulo 17
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 16
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 33.2 Criar `labs/lab-17/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 33.3 Escrever o conteúdo teórico em `labs/lab-17/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 33.4 Escrever as práticas (steps `task`) do Módulo 17
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 33.5 Escrever a Verificação de conhecimento do Módulo 17
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 33.6 Criar `app/validators/lab17.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 33.7 Escrever testes de unidade do validador do Módulo 17
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 33.8 Checkpoint de revisão do Módulo 17
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - _Requirements: 7.1, 7.3, 19.4_

- [ ] 34. Módulo 18 - Projeto final (D1, D2, D3, D4)
  - [ ] 34.1 Checkpoint de proposta do Módulo 18
    - Apresentar ao mantenedor: cenário da AnyCompany, roteiro de teoria e práticas, skills cobertas (conforme a Matriz de cobertura), serviços AWS, práticas opcionais e custo previsto
    - Aguardar a aprovação antes de escrever qualquer conteúdo
    - Depende do checkpoint de revisão do Módulo 17
    - _Requirements: 7.1, 7.6, 10.1, 10.3_
  - [ ] 34.2 Criar `labs/lab-18/metadata.json` e `cloudformation/stack.yaml`
    - Preencher `skills`, `services`, `dea_domains`, `dea_tasks`, `steps` (com `skills` por step e `optional`/`cost_note` nas práticas opcionais), `residual_resources` e `cost_notice` com os serviços cobrados e as páginas oficiais de preços
    - _Requirements: 4.3, 4.4, 6.1, 19.3, 20.2_
  - [ ] 34.3 Escrever o conteúdo teórico em `labs/lab-18/steps/`
    - Objetivos com as skills do exame, seções de conceito com exemplos e comparações, Destaques "Na prova", "Custo", "Boas práticas" e "Atenção", diagramas em `assets/` e resumo com links para a documentação oficial
    - _Requirements: 4.5, 4.6, 4.7, 4.8_
  - [ ] 34.4 Escrever as práticas (steps `task`) do Módulo 18
    - `scenario.md`, `console.md`, `cli.md`, `hint-console.md` e `hint-cli.md` seguindo 11.7 e 11.8; práticas de serviço caro como `optional: true` com aviso de custo reforçado
    - _Requirements: 4.1, 11.1, 11.7, 11.8, 19.1, 19.5_
  - [ ] 34.5 Escrever a Verificação de conhecimento do Módulo 18
    - `quiz.json` com questões de escolha única e múltipla no estilo do exame, explicação por alternativa, `domain` e `skills` por questão
    - _Requirements: 17.1, 18.2_
  - [ ] 34.6 Criar `app/validators/lab18.py`
    - `STEP_VALIDATORS` e `validate_step` para os steps `task`, com `@_safe_validate`
    - _Requirements: 5.1, 5.2, 5.3, 5.6_
  - [ ]* 34.7 Escrever testes de unidade do validador do Módulo 18
    - Sucesso e falha de cada step com boto3 mockado, incluindo exceções AWS
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 34.8 Checkpoint de revisão do Módulo 18
    - Apresentar o módulo pronto ao mantenedor e aguardar a aprovação antes do próximo módulo
    - Documentar no módulo a recomendação de concluir os Módulos 00 a 17 antes
    - _Requirements: 7.1, 7.3, 19.4_

## Parte 3: Simulado com questões reais e verificação final

- [ ] 35. Verificação final do catálogo
  - [ ] 35.1 Validar o Simulado com as questões reais dos 19 módulos
    - Conferir que o banco de questões permite a distribuição D1 34%, D2 26%, D3 22% e D4 18% com 65 questões e registrar os ajustes, se houver
    - _Requirements: 7.4, 18.2_
  - [ ]* 35.2 Escrever smoke tests do catálogo de módulos
    - Os 19 módulos (`lab-00` a `lab-18`) e o `mock-exam` existem; todos os `metadata.json` têm os campos obrigatórios; todo módulo com infraestrutura tem `stack.yaml` válido; parametrizado por módulo
    - _Requirements: 6.1, 7.1_
  - [ ]* 35.3 Executar a verificação final da Matriz de cobertura com os módulos reais
    - **Property 26: Toda skill do guia oficial está coberta**
    - **Validates: Requirements 10.2, 10.3, 10.4, 20.2**
  - [ ]* 35.4 Escrever teste de propriedade para o conteúdo completo por Trilha
    - **Property 16: Conteúdo completo por Trilha em todo step task**
    - **Validates: Requirements 11.1, 11.5, 11.6**
  - [ ]* 35.5 Escrever teste de propriedade para ausência de credenciais na Trilha CLI
    - **Property 18: Trilha CLI não contém credenciais**
    - **Validates: Requirements 11.7, 9.3**

- [ ] 36. Checkpoint final: garantir que todos os testes passam
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
- A task 15A (retomada com steps não-task, Property 19), a 15B (campo obrigatório `services` no `metadata.json`) e a 15C (verificação de ambiente com Docker e AWS real) entram entre a Parte 1 e a Parte 2. Os ids 15A, 15B e 15C evitam renumerar as tasks 16 a 27. A task 16.1 depende de 15A, 15B e 15C
- A task 15C é somente leitura: não cria recursos AWS nem faz deploy de stacks. Ela executa `docker`, `check_requirements.py`, `start.py` e uma chamada `sts:GetCallerIdentity`, com `AWS_PROFILE=Caeiro-Admin`; as tasks 15C.3 e 15C.4 exigem Docker e um token SSO válido
- Toda `metadata.json` de lab real declara `services` (lista não vazia); a tela de conclusão o exibe (5.7)
- As tasks 15D a 15H aplicam o princípio "security first" (recomendações de segurança do GitHub e da AWS). Os ids 15D a 15H evitam renumerar as tasks 16 a 27, e a task 16.1 depende de 15D a 15H
- 15D substitui o modelo de volume `~/.aws` por credenciais temporárias (Properties 20 e 21); as tasks 9.5 e 15C.3 ficam como histórico concluído, e o teste `test_sso_readonly.py` é removido na 15D.11 e substituído por `tests/security/test_container_env.py` (15D.12)
- 15E adiciona a proteção da API local (Property 22); o Gateway passa a repassar o `Host` do browser (`vhost`) e a porta chega ao Flask por `WORKSHOP_PORT`, a ser confirmada em ambiente real na 15H.2
- Os testes de segurança ficam em `tests/security/` (CODEOWNERS); a 15F.5 move para lá os testes existentes das Properties 13 e 14 e de egress
- A 15F.3 ajusta `cap_add` do gateway ao mínimo que o Squid exigir; a lista final é confirmada com `docker compose up`
- A 15H.3 e a 15H.5 alteram o estado remoto (push em `main` e configurações do GitHub). A 15H.5 só roda depois de a 15H.4 confirmar que o CI executou em `main`, e o resultado vai somente para o relatório da execução, não para o repositório
- A task 15I (depois da 15H, antes da 16) corrige o DCO para commits do Dependabot, alinha o repositório ao Python 3.15 (com reversão para 3.11 se a imagem, a instalação com `--require-hashes` ou a suíte falharem em 3.15) e adota o gitflow simplificado com a release `v0.1.0`. A 15H.5 passa a depender da 15I.7 (a branch precisa existir antes dos rulesets, para o PR ser validado), a 15I.8 depende da 15H.5 e a 16.1 depende da 15I.8. A 15I.8 só faz o merge com autorização do mantenedor
- O DCO é uma declaração de origem, não um controle de autenticidade; a proteção real é a revisão do code owner e os checks obrigatórios. A allowlist de bots da 15I.2 aceita um único par exato de autor e trailer
- As tasks 15D.12 e 15H exigem Docker e, a 15H.2, um token SSO válido para o profile `Caeiro-Admin`; a task 15H.2 não cria recursos AWS

- Reestruturação em módulos (Requirements 4, 7, 10 e 17 a 20): as antigas tasks 16 a 27 (10 labs) não iniciadas foram substituídas pela Parte 1B (15J a 15Q), pela Parte 2 (tasks 16 a 34, Módulos 00 a 18) e pela Parte 3 (tasks 35 e 36). Os nomes técnicos `lab_id`, `labs/` e `/api/labs` foram mantidos por compatibilidade
- Cada grupo de módulos sai como uma release `release/vX.Y.Z`, seguindo o gitflow. A divisão exata é decidida pelo mantenedor conforme os módulos ficam prontos
- A release é criada apontando para o commit atual de `main` (que já tem os checks aprovados) e as mudanças entram por PR de branches de trabalho, porque o ruleset de `release/**` recusa push de commits sem checks
- Sem estimativa de custo em USD nesta versão: a AWS Pricing Calculator pública não tem API, e calcular a partir do AWS Price List API dependeria de premissas de uso. Os módulos exibem o Aviso de custo com links das páginas oficiais de preços, e a estimativa em USD fica em "Melhorias futuras"
- O Módulo 00 não tem infraestrutura nem validador AWS; o Simulado (`mock-exam`) não tem infraestrutura nem `quiz.json` próprio
- As tasks de módulo `.4`, `.6` e `.7` não existem no Módulo 00
## Task Dependency Graph
```json
{
  "waves": [
    {"id": 0, "tasks": ["1.1", "1.2", "1.3", "2.1", "3.1", "4.1"]},
    {"id": 1, "tasks": ["1.4", "2.2", "3.2", "4.2", "5.1"]},
    {"id": 2, "tasks": ["5.2", "5.3", "5.4", "5.5", "5.6", "7.1"]},
    {"id": 3, "tasks": ["7.2", "8.1"]},
    {"id": 4, "tasks": ["8.2", "9.1"]},
    {"id": 5, "tasks": ["9.2", "9.3", "9.4", "9.6", "9.7", "10.1"]},
    {"id": 6, "tasks": ["10.2", "12.1"]},
    {"id": 7, "tasks": ["1.5", "9.5", "12.2", "12.3", "13.1", "14.1"]},
    {"id": 8, "tasks": ["13.2", "14.2"]},
    {"id": 9, "tasks": ["14.3", "14.4"]},
    {"id": 10, "tasks": ["15A.1"]},
    {"id": 11, "tasks": ["15A.3", "15B.1"]},
    {"id": 12, "tasks": ["15A.2"]},
    {"id": 13, "tasks": ["15A.4", "15B.2"]},
    {"id": 14, "tasks": ["15B.3"]},
    {"id": 15, "tasks": ["15C.1"]},
    {"id": 16, "tasks": ["15C.2"]},
    {"id": 17, "tasks": ["15C.3"]},
    {"id": 18, "tasks": ["15C.4"]},
    {"id": 19, "tasks": ["15D.1", "15D.5", "15F.2", "15G.1", "15G.4", "15G.5"]},
    {"id": 20, "tasks": ["15D.2", "15D.3", "15D.4", "15D.6", "15E.1", "15F.1", "15G.2"]},
    {"id": 21, "tasks": ["15D.7", "15D.8", "15D.9", "15D.10", "15D.11", "15D.12", "15E.2", "15E.3", "15E.4", "15F.5", "15G.3"]},
    {"id": 22, "tasks": ["15E.5", "15E.6", "15F.3", "15F.4", "15G.6", "15G.7", "15G.8"]},
    {"id": 23, "tasks": ["15F.6"]},
    {"id": 24, "tasks": ["15H.1"]},
    {"id": 25, "tasks": ["15H.2"]},
    {"id": 26, "tasks": ["15H.3"]},
    {"id": 27, "tasks": ["15H.4"]},
    {"id": 28, "tasks": ["15I.1"]},
    {"id": 29, "tasks": ["15I.2", "15I.4"]},
    {"id": 30, "tasks": ["15I.3", "15I.5"]},
    {"id": 31, "tasks": ["15I.6"]},
    {"id": 32, "tasks": ["15I.7"]},
    {"id": 33, "tasks": ["15H.5"]},
    {"id": 34, "tasks": ["15I.8"]},
    {"id": 35, "tasks": ["15J.1"]},
    {"id": 36, "tasks": ["15J.2"]},
    {"id": 37, "tasks": ["15K.1"]},
    {"id": 38, "tasks": ["15K.2", "15L.1"]},
    {"id": 39, "tasks": ["15L.2"]},
    {"id": 40, "tasks": ["15L.3", "15L.4", "15M.1", "15N.1"]},
    {"id": 41, "tasks": ["15M.2", "15N.2", "15O.1", "15O.2"]},
    {"id": 42, "tasks": ["15M.3", "15N.3", "15O.3", "15P.1"]},
    {"id": 43, "tasks": ["15N.4", "15P.2"]},
    {"id": 44, "tasks": ["15P.3"]},
    {"id": 45, "tasks": ["15Q.1"]},
    {"id": 46, "tasks": ["15Q.2"]},
    {"id": 47, "tasks": ["15Q.3"]},
    {"id": 48, "tasks": ["16.1"]},
    {"id": 49, "tasks": ["16.2"]},
    {"id": 50, "tasks": ["16.3", "16.5"]},
    {"id": 51, "tasks": ["16.8"]},
    {"id": 52, "tasks": ["17.1"]},
    {"id": 53, "tasks": ["17.2"]},
    {"id": 54, "tasks": ["17.3", "17.4", "17.5", "17.6"]},
    {"id": 55, "tasks": ["17.7"]},
    {"id": 56, "tasks": ["17.8"]},
    {"id": 57, "tasks": ["18.1"]},
    {"id": 58, "tasks": ["18.2"]},
    {"id": 59, "tasks": ["18.3", "18.4", "18.5", "18.6"]},
    {"id": 60, "tasks": ["18.7"]},
    {"id": 61, "tasks": ["18.8"]},
    {"id": 62, "tasks": ["19.1"]},
    {"id": 63, "tasks": ["19.2"]},
    {"id": 64, "tasks": ["19.3", "19.4", "19.5", "19.6"]},
    {"id": 65, "tasks": ["19.7"]},
    {"id": 66, "tasks": ["19.8"]},
    {"id": 67, "tasks": ["20.1"]},
    {"id": 68, "tasks": ["20.2"]},
    {"id": 69, "tasks": ["20.3", "20.4", "20.5", "20.6"]},
    {"id": 70, "tasks": ["20.7"]},
    {"id": 71, "tasks": ["20.8"]},
    {"id": 72, "tasks": ["21.1"]},
    {"id": 73, "tasks": ["21.2"]},
    {"id": 74, "tasks": ["21.3", "21.4", "21.5", "21.6"]},
    {"id": 75, "tasks": ["21.7"]},
    {"id": 76, "tasks": ["21.8"]},
    {"id": 77, "tasks": ["22.1"]},
    {"id": 78, "tasks": ["22.2"]},
    {"id": 79, "tasks": ["22.3", "22.4", "22.5", "22.6"]},
    {"id": 80, "tasks": ["22.7"]},
    {"id": 81, "tasks": ["22.8"]},
    {"id": 82, "tasks": ["23.1"]},
    {"id": 83, "tasks": ["23.2"]},
    {"id": 84, "tasks": ["23.3", "23.4", "23.5", "23.6"]},
    {"id": 85, "tasks": ["23.7"]},
    {"id": 86, "tasks": ["23.8"]},
    {"id": 87, "tasks": ["24.1"]},
    {"id": 88, "tasks": ["24.2"]},
    {"id": 89, "tasks": ["24.3", "24.4", "24.5", "24.6"]},
    {"id": 90, "tasks": ["24.7"]},
    {"id": 91, "tasks": ["24.8"]},
    {"id": 92, "tasks": ["25.1"]},
    {"id": 93, "tasks": ["25.2"]},
    {"id": 94, "tasks": ["25.3", "25.4", "25.5", "25.6"]},
    {"id": 95, "tasks": ["25.7"]},
    {"id": 96, "tasks": ["25.8"]},
    {"id": 97, "tasks": ["26.1"]},
    {"id": 98, "tasks": ["26.2"]},
    {"id": 99, "tasks": ["26.3", "26.4", "26.5", "26.6"]},
    {"id": 100, "tasks": ["26.7"]},
    {"id": 101, "tasks": ["26.8"]},
    {"id": 102, "tasks": ["27.1"]},
    {"id": 103, "tasks": ["27.2"]},
    {"id": 104, "tasks": ["27.3", "27.4", "27.5", "27.6"]},
    {"id": 105, "tasks": ["27.7"]},
    {"id": 106, "tasks": ["27.8"]},
    {"id": 107, "tasks": ["28.1"]},
    {"id": 108, "tasks": ["28.2"]},
    {"id": 109, "tasks": ["28.3", "28.4", "28.5", "28.6"]},
    {"id": 110, "tasks": ["28.7"]},
    {"id": 111, "tasks": ["28.8"]},
    {"id": 112, "tasks": ["29.1"]},
    {"id": 113, "tasks": ["29.2"]},
    {"id": 114, "tasks": ["29.3", "29.4", "29.5", "29.6"]},
    {"id": 115, "tasks": ["29.7"]},
    {"id": 116, "tasks": ["29.8"]},
    {"id": 117, "tasks": ["30.1"]},
    {"id": 118, "tasks": ["30.2"]},
    {"id": 119, "tasks": ["30.3", "30.4", "30.5", "30.6"]},
    {"id": 120, "tasks": ["30.7"]},
    {"id": 121, "tasks": ["30.8"]},
    {"id": 122, "tasks": ["31.1"]},
    {"id": 123, "tasks": ["31.2"]},
    {"id": 124, "tasks": ["31.3", "31.4", "31.5", "31.6"]},
    {"id": 125, "tasks": ["31.7"]},
    {"id": 126, "tasks": ["31.8"]},
    {"id": 127, "tasks": ["32.1"]},
    {"id": 128, "tasks": ["32.2"]},
    {"id": 129, "tasks": ["32.3", "32.4", "32.5", "32.6"]},
    {"id": 130, "tasks": ["32.7"]},
    {"id": 131, "tasks": ["32.8"]},
    {"id": 132, "tasks": ["33.1"]},
    {"id": 133, "tasks": ["33.2"]},
    {"id": 134, "tasks": ["33.3", "33.4", "33.5", "33.6"]},
    {"id": 135, "tasks": ["33.7"]},
    {"id": 136, "tasks": ["33.8"]},
    {"id": 137, "tasks": ["34.1"]},
    {"id": 138, "tasks": ["34.2"]},
    {"id": 139, "tasks": ["34.3", "34.4", "34.5", "34.6"]},
    {"id": 140, "tasks": ["34.7"]},
    {"id": 141, "tasks": ["34.8"]},
    {"id": 142, "tasks": ["35.1", "35.2", "35.3", "35.4", "35.5"]}
  ]
}
```
