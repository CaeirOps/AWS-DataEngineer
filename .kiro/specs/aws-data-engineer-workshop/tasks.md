# Implementation Plan: AWS Data Engineer Workshop Platform

## Overview

Implementação de uma plataforma web local de workshop para a certificação DEA-C01, composta por: script de pré-validação (`check_requirements.py`), servidor Flask com API REST, módulos Python de validação com boto3, frontend SPA em HTML/CSS/JS puro, estrutura de conteúdo para 10 labs com CloudFormation e infraestrutura Docker Compose.

## Tasks

- [ ] 1. Configurar estrutura do projeto e infraestrutura Docker
  - Criar `Dockerfile` com Python 3.11-slim, instalação de dependências e configuração de volumes
  - Criar `docker-compose.yml` com bind `127.0.0.1:5000:5000`, volume `~/.aws` read-only e volume `./progress`
  - Criar `requirements.txt` com Flask, boto3, botocore e hypothesis
  - Criar `.gitignore` incluindo `progress/progress.json`
  - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 9.1, 9.4_

- [ ] 2. Implementar check_requirements.py
  - [ ] 2.1 Implementar verificações de pré-requisitos (Docker, AWS CLI, credenciais, permissões)
    - Detectar Docker e validar versão >= 20 via subprocess
    - Detectar AWS CLI e validar versão >= 2 via subprocess
    - Verificar credenciais AWS via `boto3.Session().get_credentials()`
    - Verificar permissões mínimas IAM/S3/CloudFormation com chamadas describe sem efeitos colaterais
    - Exibir erros descritivos com passos de correção para cada pré-requisito ausente
    - Retornar exit code 0 (sucesso) ou 1 (falha)
    - _Requirements: 1.2, 1.3_

  - [ ]* 2.2 Escrever testes de propriedade para check_requirements.py
    - **Property 1: Pré-requisito ausente sempre resulta em falha descritiva**
    - **Validates: Requirements 1.2, 1.3**

- [ ] 3. Implementar modelos de dados e hierarquia de exceções
  - [ ] 3.1 Criar dataclasses e modelos Python
    - Implementar `ValidationResult` dataclass com campos `passed`, `message` e `hint`
    - Implementar `StepMetadata` e `LabMetadata` dataclasses
    - Criar hierarquia de exceções `WorkshopError`, `CredentialsError`, `PermissionsError`, `LabNotFoundError`, `StackDeployError`
    - _Requirements: 4.1, 7.1_

  - [ ]* 3.2 Escrever testes de propriedade para modelos de dados
    - **Property 9: Todos os steps de todos os labs têm campos obrigatórios**
    - **Validates: Requirements 4.1, 7.1**

- [ ] 4. Implementar ProgressStore
  - [ ] 4.1 Implementar leitura, escrita e transições de estado do progress.json
    - Criar classe `ProgressStore` com leitura/escrita thread-safe via `threading.Lock()`
    - Implementar `update_step` com transições de estado (`not_visited → failed/passed`, `failed → passed`)
    - Implementar `_compute_lab_status` com transições de lab (`not_started → in_progress → completed`)
    - Implementar `get_resume_step` retornando o primeiro step não-`passed`
    - Inicializar `progress.json` com `schema_version: "1.0"` se não existir
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 9.2_

  - [ ]* 4.2 Escrever testes de propriedade para ProgressStore
    - **Property 2: Cálculo de progresso reflete exatamente o estado dos steps**
    - **Validates: Requirements 2.2**

  - [ ]* 4.3 Escrever testes de propriedade para get_resume_step
    - **Property 3: Step de retomada é sempre o primeiro step não concluído**
    - **Validates: Requirements 2.3, 2.4**

  - [ ]* 4.4 Escrever testes de propriedade para serialização do progress.json
    - **Property 12: Serialização/deserialização de progress.json preserva dados**
    - **Validates: Requirements 2.5, 9.2**

- [ ] 5. Checkpoint — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [ ] 6. Implementar LabCatalog
  - [ ] 6.1 Implementar carregamento do catálogo de labs
    - Criar classe `LabCatalog` que carrega todos os `metadata.json` na inicialização
    - Implementar `get_lab` e `get_all_labs` ordenando por `lab_id`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 10.1_

  - [ ]* 6.2 Escrever smoke tests para o catálogo de labs
    - Verificar que exatamente 10 labs existem com os IDs esperados
    - Verificar que todos os `metadata.json` possuem campos obrigatórios
    - _Requirements: 7.1, 4.1_

- [ ] 7. Implementar módulos validadores (app/validators/)
  - [ ] 7.1 Criar decorator `_safe_validate` e contrato base de validação
    - Implementar decorator que converte `ClientError` e `NoCredentialsError` em `ValidationResult(passed=False)`
    - Criar `__init__.py` do pacote `validators`
    - _Requirements: 5.3, 5.6_

  - [ ] 7.2 Implementar validadores dos Labs 01 a 05
    - Criar `validators/lab01.py` com `STEP_VALIDATORS` dict e `validate_step` (S3, Data Lake)
    - Criar `validators/lab02.py` (Glue Catalog, descoberta de dados)
    - Criar `validators/lab03.py` (Glue ETL jobs)
    - Criar `validators/lab04.py` (Athena queries, resultados)
    - Criar `validators/lab05.py` (DataBrew, qualidade de dados)
    - Cada módulo usa `@_safe_validate` em todas as funções internas
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ] 7.3 Implementar validadores dos Labs 06 a 10
    - Criar `validators/lab06.py` (Kinesis streams)
    - Criar `validators/lab07.py` (Redshift cluster/serverless)
    - Criar `validators/lab08.py` (Step Functions, EventBridge)
    - Criar `validators/lab09.py` (IAM policies, Lake Formation, KMS)
    - Criar `validators/lab10.py` (pipeline end-to-end, dependências dos labs 01-09)
    - _Requirements: 5.1, 5.2, 7.1_

  - [ ]* 7.4 Escrever testes de propriedade para validadores
    - **Property 4: Validação bem-sucedida sempre atualiza o progresso**
    - **Validates: Requirements 5.2**

  - [ ]* 7.5 Escrever testes de propriedade para tratamento de exceções AWS
    - **Property 8: Validador retorna ValidationResult para qualquer exceção AWS**
    - **Validates: Requirements 5.3, 5.6**

- [ ] 8. Implementar ValidationService
  - [ ] 8.1 Criar ValidationService que orquestra validadores e ProgressStore
    - Implementar `validate(lab_id, step_id, context)` criando `boto3.Session()`, carregando validador dinamicamente, atualizando `ProgressStore`
    - Calcular `show_hint_button` comparando `attempt_count >= hint_threshold`
    - Formatar resposta completa da API (passed, message, hint, step_status, show_hint_button, attempt_count)
    - _Requirements: 5.1, 5.2, 5.4, 5.5_

  - [ ]* 8.2 Escrever testes de propriedade para lógica de hint threshold
    - **Property 5: Retry ilimitado — tentativas não bloqueiam validação**
    - **Validates: Requirements 5.4**

  - [ ]* 8.3 Escrever testes de propriedade adicionais para ValidationService
    - **Property 6: Exibição de dica segue o limiar configurado**
    - **Validates: Requirements 5.5**

  - [ ]* 8.4 Escrever testes de propriedade para conclusão de lab
    - **Property 7: Lab marcado como concluído somente quando todos os steps passam**
    - **Validates: Requirements 5.7**

- [ ] 9. Implementar CloudFormationService
  - [ ] 9.1 Criar CloudFormationService com deploy, teardown e status
    - Implementar `deploy` iniciando criação de stack a partir de `labs/{lab_id}/cloudformation/stack.yaml`
    - Implementar `teardown` iniciando exclusão e retornando `residual_resources` do `metadata.json`
    - Implementar `get_status` consultando `describe_stacks` e retornando status e outputs
    - Usar convenção de nomenclatura `workshop-{lab_id}`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 9.2 Escrever testes de unidade para CloudFormationService
    - Testar cenários de sucesso e falha com mock boto3
    - Testar exibição de `residual_resources` no teardown
    - _Requirements: 6.4, 6.6_

- [ ] 10. Checkpoint — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [ ] 11. Implementar servidor Flask (app/server.py)
  - [ ] 11.1 Criar servidor Flask com todas as rotas da API
    - Configurar Flask com `host="127.0.0.1"`, `port=5000`, `debug=False` em produção
    - Registrar `LabCatalog`, `ProgressStore`, `ValidationService`, `CloudFormationService` como singletons
    - Implementar rotas: `GET /`, `GET /lab/<lab_id>`, `GET /health`
    - Implementar rotas de API: `GET /api/labs`, `GET /api/labs/<lab_id>`, `GET/PUT /api/progress`
    - Implementar rotas de validação e CloudFormation: `POST /api/validate/<lab_id>/<step_id>`, `POST /api/deploy/<lab_id>`, `POST /api/teardown/<lab_id>`, `GET /api/stack-status/<lab_id>`
    - Registrar error handlers globais para `WorkshopError` e `Exception`
    - _Requirements: 1.4, 9.1, 5.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 11.2 Escrever smoke tests para o servidor Flask
    - Verificar que `GET /health` retorna `{"status": "ok"}`
    - Verificar que Flask está configurado para bind somente em `127.0.0.1`
    - _Requirements: 1.4, 9.1_

- [ ] 12. Criar estrutura de conteúdo dos 10 labs
  - [ ] 12.1 Criar estrutura de diretórios e metadata.json para Labs 01 a 05
    - Criar `labs/lab-01/` com `metadata.json`, `content.md`, `cloudformation/stack.yaml`
    - Criar `labs/lab-02/` a `labs/lab-05/` com mesma estrutura
    - Cada `metadata.json` deve conter `lab_id`, `title`, `description`, `difficulty`, `estimated_duration_minutes`, `estimated_cost_usd`, `dea_domains`, `dea_tasks`, `steps`, `residual_resources`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 7.1, 10.1, 10.2, 10.3_

  - [ ] 12.2 Criar estrutura de diretórios e metadata.json para Labs 06 a 10
    - Criar `labs/lab-06/` a `labs/lab-10/` com `metadata.json`, `content.md`, `cloudformation/stack.yaml`
    - `lab-10/metadata.json` deve documentar dependência explícita dos labs 01-09
    - _Requirements: 7.1, 7.3, 10.1, 10.4, 10.5_

  - [ ]* 12.3 Escrever smoke tests para cobertura de domínios DEA-C01
    - **Property 10: Cobertura de domínios DEA-C01 é completa**
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5**

  - [ ]* 12.4 Escrever smoke tests para templates CloudFormation
    - Verificar que 10 arquivos `cloudformation/stack.yaml` existem com sintaxe YAML válida
    - _Requirements: 6.1_

- [ ] 13. Implementar frontend SPA (app/static/)
  - [ ] 13.1 Criar estrutura base HTML e CSS
    - Criar `app/static/index.html` como shell da SPA com todos os imports locais
    - Criar `app/static/css/workshop.css` com paleta `workshops.aws` (variáveis CSS)
    - Criar `app/static/css/components.css` com componentes reutilizáveis (cards, botões, wizard, badges)
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 13.2 Criar módulos JavaScript da SPA
    - Criar `app/static/js/app.js` com roteamento client-side (`/`, `/lab/{id}`, `/lab/{id}/{step}`)
    - Criar `app/static/js/progress.js` com funções de leitura/escrita via `GET/PUT /api/progress`
    - Criar `app/static/js/dashboard.js` com exibição dos 10 labs, contagem de steps e ponto de retomada
    - Criar `app/static/js/lab.js` com wizard de navegação, controles anterior/próximo e botão "Finalizar Lab"
    - Criar `app/static/js/validator.js` com chamada `POST /api/validate`, exibição de feedback sem reload e controle do botão "Ver Dica Detalhada"
    - Criar `app/static/js/cloudformation.js` com polling a cada 5 segundos em `GET /api/stack-status` e exibição de status
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.5, 5.7, 6.3, 6.4, 6.5, 6.6, 8.4_

  - [ ]* 13.3 Escrever smoke tests para arquivos estáticos
    - **Property 11: Arquivos estáticos não referenciam URLs externas**
    - **Validates: Requirements 8.2**

- [ ] 14. Checkpoint final — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada task referencia requisitos específicos para rastreabilidade
- Os checkpoints garantem validação incremental ao longo da implementação
- Testes de propriedade (hypothesis) validam invariantes universais; testes de unidade validam exemplos e edge cases específicos
- Todos os validadores de lab devem usar o decorator `@_safe_validate` para tratamento seguro de exceções boto3
- O frontend não usa frameworks — apenas HTML/CSS/JS puro servido pelo Flask
- A plataforma nunca expõe portas além de `127.0.0.1:5000`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "3.1"] },
    { "id": 1, "tasks": ["2.2", "3.2", "4.1"] },
    { "id": 2, "tasks": ["4.2", "4.3", "4.4", "6.1"] },
    { "id": 3, "tasks": ["6.2", "7.1"] },
    { "id": 4, "tasks": ["7.2", "7.3"] },
    { "id": 5, "tasks": ["7.4", "7.5", "8.1"] },
    { "id": 6, "tasks": ["8.2", "8.3", "8.4", "9.1"] },
    { "id": 7, "tasks": ["9.2", "11.1"] },
    { "id": 8, "tasks": ["11.2", "12.1"] },
    { "id": 9, "tasks": ["12.2"] },
    { "id": 10, "tasks": ["12.3", "12.4", "13.1"] },
    { "id": 11, "tasks": ["13.2"] },
    { "id": 12, "tasks": ["13.3"] }
  ]
}
```
