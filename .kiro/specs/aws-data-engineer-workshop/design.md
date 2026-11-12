# Design Document

## Overview

A Plataforma de Workshop AWS Data Engineer é uma aplicação web local, distribuída via `git clone` e executada com Docker Compose. O backend é um servidor Flask (Python 3.11+) que serve conteúdo estático e expõe uma API REST para validação de steps, gerenciamento de progresso e operações CloudFormation. Toda a lógica de validação AWS é implementada em módulos Python com boto3, sem autenticação própria, sem banco de dados externo e sem telemetria.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Host do Usuário                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   Docker Container                          │  │
│  │                                                             │  │
│  │  ┌──────────────┐    ┌──────────────────────────────────┐  │  │
│  │  │ Flask Server │    │        Validation Modules        │  │  │
│  │  │  server.py   │───▶│  validators/lab01.py ... lab10.py│  │  │
│  │  └──────┬───────┘    └──────────────────────────────────┘  │  │
│  │         │                           │                        │  │
│  │  ┌──────▼───────┐                   │ boto3                  │  │
│  │  │ Static Files │          ┌────────▼────────┐              │  │
│  │  │  (HTML/CSS/  │          │   AWS Endpoints  │              │  │
│  │  │    JS)       │          │  (S3, Glue, etc.)│              │  │
│  │  └──────────────┘          └─────────────────┘              │  │
│  │                                                              │  │
│  │  Volumes:                                                    │  │
│  │  ├── ~/.aws (read-only) ──▶ /root/.aws                      │  │
│  │  └── ./progress/        ──▶ /app/progress/                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Browser ──▶ http://localhost:5000                                │
└─────────────────────────────────────────────────────────────────┘
```

A arquitetura é deliberadamente simples: single-container, sem orquestração de microserviços, sem banco de dados, sem autenticação. O estado é mantido em um único arquivo JSON no host.

## Components and Interfaces

### 1. check_requirements.py

Script de pré-validação executado pelo usuário antes de `docker compose up`. Roda no ambiente Python do host (não dentro do container).

**Responsabilidades:**
- Detectar Docker (`docker --version`) e validar versão >= 20
- Detectar AWS CLI (`aws --version`) e validar versão >= 2
- Detectar credenciais AWS válidas via `boto3.Session().get_credentials()`
- Verificar permissões mínimas AWS (IAM, S3, CloudFormation) via chamadas boto3 sem efeitos colaterais (dry-run ou describe)
- Exibir erros descritivos com passos de correção para cada pré-requisito ausente
- Retornar exit code 0 (sucesso) ou 1 (falha)

```python
# Estrutura de saída de erro
{
    "prerequisite": "Docker >= 20",
    "status": "missing",
    "found": "18.09.0",
    "fix": "Atualize o Docker: https://docs.docker.com/engine/install/"
}
```

### 2. Flask Server (app/server.py)

Servidor WSGI Flask que atua como API backend e servidor de arquivos estáticos.

**Configuração:**
- `host="127.0.0.1"` — somente localhost, nunca `0.0.0.0`
- `port=5000`
- `debug=False` em produção (controlado por variável de ambiente `FLASK_ENV`)
- CORS desabilitado (mesmo host)

**Rotas de API:**

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/` | Serve `static/index.html` (Dashboard) |
| `GET` | `/lab/<lab_id>` | Serve `static/index.html` (SPA, rota gerenciada pelo JS) |
| `GET` | `/api/progress` | Retorna `progress.json` completo |
| `PUT` | `/api/progress` | Atualiza `progress.json` com payload parcial |
| `POST` | `/api/validate/<lab_id>/<step_id>` | Executa validação do step |
| `POST` | `/api/deploy/<lab_id>` | Inicia deploy da stack CloudFormation |
| `POST` | `/api/teardown/<lab_id>` | Inicia exclusão da stack CloudFormation |
| `GET` | `/api/stack-status/<lab_id>` | Retorna status atual da stack |
| `GET` | `/api/labs` | Retorna catálogo de labs com metadados |
| `GET` | `/api/labs/<lab_id>` | Retorna metadados e steps de um lab |

**Rota de saúde:**
| `GET` | `/health` | Retorna `{"status": "ok"}` para healthcheck do Docker |

### 3. Módulos Validadores (app/validators/)

Cada lab possui um módulo Python dedicado (`lab01.py` ... `lab10.py`) que implementa a função `validate_step`.

**Contrato obrigatório:**

```python
from dataclasses import dataclass
from typing import Optional
import boto3

@dataclass
class ValidationResult:
    passed: bool
    message: str
    hint: Optional[str] = None

def validate_step(boto3_session: boto3.Session, context: dict) -> ValidationResult:
    """
    Valida o estado real dos recursos AWS para um step específico.
    
    Args:
        boto3_session: Sessão boto3 autenticada (criada a partir de ~/.aws)
        context: Dicionário com step_id, lab_id, attempt_count e parâmetros extras
    
    Returns:
        ValidationResult com passed, message e hint opcional
    
    Raises:
        Não deve lançar exceções; capturar e retornar ValidationResult(passed=False)
    """
```

**Exemplo de validador (lab01, step-01 — bucket S3 criado):**

```python
def validate_step(boto3_session: boto3.Session, context: dict) -> ValidationResult:
    step_id = context.get("step_id")
    
    if step_id == "step-01":
        return _validate_s3_bucket_created(boto3_session, context)
    
    return ValidationResult(passed=False, message=f"Step {step_id} nao reconhecido.")

def _validate_s3_bucket_created(session: boto3.Session, ctx: dict) -> ValidationResult:
    try:
        s3 = session.client("s3")
        expected_prefix = ctx.get("bucket_prefix", "workshop-datalake")
        
        response = s3.list_buckets()
        matching = [b for b in response["Buckets"] 
                    if b["Name"].startswith(expected_prefix)]
        
        if not matching:
            return ValidationResult(
                passed=False,
                message=f"Nenhum bucket com prefixo '{expected_prefix}' encontrado.",
                hint="Certifique-se de que o bucket foi criado na regiao correta."
            )
        
        return ValidationResult(
            passed=True,
            message=f"Bucket '{matching[0]['Name']}' encontrado com sucesso!"
        )
    
    except Exception as e:
        if "InvalidClientTokenId" in str(e) or "ExpiredToken" in str(e):
            return ValidationResult(
                passed=False,
                message="Credenciais AWS expiradas ou invalidas. Reconfigure ~/.aws."
            )
        return ValidationResult(passed=False, message=f"Erro ao validar: {str(e)}")
```

**Mapeamento step_id → função de validação por módulo:**

Cada `labXX.py` mantém um dicionário interno de dispatch:

```python
STEP_VALIDATORS = {
    "step-01": _validate_s3_bucket_created,
    "step-02": _validate_bucket_versioning,
    # ...
}

def validate_step(boto3_session, context):
    step_id = context.get("step_id")
    validator_fn = STEP_VALIDATORS.get(step_id)
    if not validator_fn:
        return ValidationResult(passed=False, message=f"Step {step_id} desconhecido.")
    return validator_fn(boto3_session, context)
```

### 4. Progress Store (progress/progress.json)

Arquivo JSON persistido em volume Docker local no host. Nunca entra no container como parte da imagem.

**Schema completo:**

```json
{
  "schema_version": "1.0",
  "last_updated": "2024-01-15T10:30:00Z",
  "labs": {
    "lab-01": {
      "status": "in_progress",
      "started_at": "2024-01-15T09:00:00Z",
      "completed_at": null,
      "steps": {
        "step-01": {
          "status": "passed",
          "attempts": 2,
          "last_attempt_at": "2024-01-15T09:15:00Z",
          "passed_at": "2024-01-15T09:15:00Z"
        },
        "step-02": {
          "status": "failed",
          "attempts": 1,
          "last_attempt_at": "2024-01-15T09:20:00Z",
          "passed_at": null
        },
        "step-03": {
          "status": "not_visited",
          "attempts": 0,
          "last_attempt_at": null,
          "passed_at": null
        }
      }
    }
  }
}
```

**Regras de transição de estado de step:**

```
not_visited → failed  (primeira tentativa falhou)
not_visited → passed  (primeira tentativa passou)
failed      → passed  (retry bem-sucedido)
passed      → passed  (retry após conclusão, sem regressão)
```

**Regras de transição de estado de lab:**

```
not_started  → in_progress  (qualquer step visitado)
in_progress  → completed    (todos os steps com status=passed)
completed    → completed    (estado final, sem regressão)
```

### 5. Lab Content (labs/lab-XX/)

Cada lab é um diretório autocontido com:

```
labs/lab-01/
├── content.md              # Conteúdo completo do lab (Markdown)
├── metadata.json           # Metadados estruturados do lab
├── cloudformation/
│   └── stack.yaml          # Template CloudFormation do lab
└── assets/
    └── *.png               # Diagramas e imagens
```

**Schema de metadata.json:**

```json
{
  "lab_id": "lab-01",
  "title": "Fundamentos de S3 e Data Lake",
  "description": "Introdução ao Amazon S3 como base de um Data Lake na AWS.",
  "difficulty": "iniciante",
  "estimated_duration_minutes": 60,
  "estimated_cost_usd": 0.50,
  "cost_disclaimer": "Os recursos provisionados neste lab incorrem em custo...",
  "dea_domains": ["D2"],
  "dea_tasks": ["2.1", "2.2"],
  "prerequisites": {
    "hard": [],
    "recommended": []
  },
  "steps": [
    {
      "step_id": "step-01",
      "title": "Criar bucket S3 para o Data Lake",
      "type": "task",
      "hint_threshold": 3
    }
  ],
  "residual_resources": [
    "Bucket S3 criado manualmente (nao gerenciado pela stack)"
  ]
}
```

**Tipos de step:**

| Tipo | Descrição |
|------|-----------|
| `info` | Conteúdo informativo sem validação (cenário, pré-requisitos) |
| `deploy` | Instrução de deploy CloudFormation com botão de status |
| `task` | Tarefa com botão "Validar" que chama a API |
| `teardown` | Instrução de teardown CloudFormation com confirmação |
| `completion` | Tela de conclusão do lab |

### 6. Frontend SPA (app/static/)

Single-Page Application em HTML/CSS/JS puro (sem framework), servida pelo Flask.

**Estrutura de arquivos:**

```
app/static/
├── index.html              # Shell HTML da SPA
├── css/
│   ├── workshop.css        # Estilos base (paleta workshops.aws)
│   └── components.css      # Componentes reutilizáveis
└── js/
    ├── app.js              # Roteamento e inicialização
    ├── dashboard.js        # Lógica do Dashboard
    ├── lab.js              # Lógica de lab/step/wizard
    ├── validator.js        # Lógica de validação e feedback
    ├── progress.js         # Leitura/escrita de progresso via API
    └── cloudformation.js   # Polling de status de stack
```

**Roteamento client-side:**

```
/                    → Dashboard (todos os labs)
/lab/{lab_id}        → Lab (abre no step de retomada)
/lab/{lab_id}/{step} → Step específico (somente se visitado)
```

**Paleta de cores (workshops.aws):**

```css
:root {
  --aws-orange:     #FF9900;
  --aws-dark-blue:  #232F3E;
  --aws-light-blue: #1A73E8;
  --aws-success:    #2ECC71;
  --aws-error:      #E74C3C;
  --aws-warning:    #F39C12;
  --aws-bg:         #FAFAFA;
  --aws-text:       #16191F;
}
```

### 7. Docker Infrastructure

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY labs/ ./labs/

# Volumes externos (nao copiados na imagem)
# ~/.aws  → /root/.aws (somente-leitura)
# ./progress/ → /app/progress/

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -f http://localhost:5000/health || exit 1

CMD ["python", "-m", "flask", "--app", "app/server.py", "run", \
     "--host", "127.0.0.1", "--port", "5000"]
```

**docker-compose.yml:**

```yaml
version: "3.8"

services:
  workshop:
    build: .
    ports:
      - "127.0.0.1:5000:5000"   # somente localhost, nunca 0.0.0.0
    volumes:
      - "${HOME}/.aws:/root/.aws:ro"  # credenciais read-only
      - "./progress:/app/progress"    # progresso persistido
    environment:
      - FLASK_ENV=production
      - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
```

### API Response Schemas

**GET /api/labs**

```json
{
  "labs": [
    {
      "lab_id": "lab-01",
      "title": "Fundamentos de S3 e Data Lake",
      "difficulty": "iniciante",
      "dea_domains": ["D2"],
      "total_steps": 5,
      "completed_steps": 3,
      "status": "in_progress"
    }
  ]
}
```

**POST /api/validate/{lab_id}/{step_id}**

Request body:
```json
{
  "context": {
    "bucket_prefix": "workshop-datalake"
  }
}
```

Response (sucesso):
```json
{
  "passed": true,
  "message": "Bucket 'workshop-datalake-abc123' encontrado com sucesso!",
  "hint": null,
  "step_status": "passed",
  "show_hint_button": false,
  "attempt_count": 1
}
```

Response (falha):
```json
{
  "passed": false,
  "message": "Nenhum bucket com prefixo 'workshop-datalake' encontrado.",
  "hint": null,
  "step_status": "failed",
  "show_hint_button": false,
  "attempt_count": 2
}
```

Response (falha com dica disponível):
```json
{
  "passed": false,
  "message": "Nenhum bucket com prefixo 'workshop-datalake' encontrado.",
  "hint": "Certifique-se de que o bucket foi criado na regiao correta.",
  "step_status": "failed",
  "show_hint_button": true,
  "attempt_count": 3
}
```

**GET /api/stack-status/{lab_id}**

```json
{
  "stack_name": "workshop-lab-01",
  "status": "CREATE_IN_PROGRESS",
  "status_reason": null,
  "outputs": {},
  "last_updated": "2024-01-15T10:00:00Z"
}
```

**POST /api/deploy/{lab_id}**

```json
{
  "stack_name": "workshop-lab-01",
  "status": "CREATE_IN_PROGRESS",
  "message": "Stack iniciada. Aguarde o provisionamento."
}
```

**POST /api/teardown/{lab_id}**

```json
{
  "stack_name": "workshop-lab-01",
  "status": "DELETE_IN_PROGRESS",
  "residual_resources": [
    "Bucket S3 'workshop-datalake-abc123' (criado manualmente, verifique e exclua se necessario)"
  ],
  "message": "Exclusao da stack iniciada."
}
```

### Error Response Schema

Todos os erros da API seguem o formato:

```json
{
  "error": true,
  "code": "CREDENTIALS_EXPIRED",
  "message": "Credenciais AWS expiradas. Reconfigure ~/.aws e reinicie o container.",
  "http_status": 401
}
```

**Códigos de erro:**

| Código | HTTP | Descrição |
|--------|------|-----------|
| `CREDENTIALS_EXPIRED` | 401 | Token AWS expirado |
| `CREDENTIALS_MISSING` | 401 | Sem credenciais configuradas |
| `PERMISSIONS_DENIED` | 403 | Permissão AWS insuficiente |
| `LAB_NOT_FOUND` | 404 | lab_id inválido |
| `STEP_NOT_FOUND` | 404 | step_id inválido para o lab |
| `STACK_NOT_FOUND` | 404 | Stack CloudFormation não existe |
| `STACK_DEPLOY_FAILED` | 422 | Deploy CloudFormation falhou |
| `INTERNAL_ERROR` | 500 | Erro interno não classificado |

## Data Models

### LabCatalog

Carregado na inicialização do Flask a partir dos arquivos `metadata.json` de cada lab:

```python
@dataclass
class StepMetadata:
    step_id: str
    title: str
    type: str  # info | deploy | task | teardown | completion
    hint_threshold: int = 3

@dataclass
class LabMetadata:
    lab_id: str
    title: str
    description: str
    difficulty: str  # iniciante | intermediario | avancado
    estimated_duration_minutes: int
    estimated_cost_usd: float
    cost_disclaimer: str
    dea_domains: list[str]
    dea_tasks: list[str]
    prerequisites: dict
    steps: list[StepMetadata]
    residual_resources: list[str]

class LabCatalog:
    """Singleton carregado na inicialização do Flask."""
    
    def __init__(self, labs_dir: str):
        self._labs: dict[str, LabMetadata] = {}
        self._load_all(labs_dir)
    
    def get_lab(self, lab_id: str) -> Optional[LabMetadata]:
        return self._labs.get(lab_id)
    
    def get_all_labs(self) -> list[LabMetadata]:
        return sorted(self._labs.values(), key=lambda l: l.lab_id)
```

### ProgressStore

```python
class ProgressStore:
    """Thread-safe gerenciador do progress.json."""
    
    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = threading.Lock()
    
    def get_progress(self) -> dict:
        """Retorna o progresso completo."""
    
    def get_lab_progress(self, lab_id: str) -> dict:
        """Retorna o progresso de um lab específico."""
    
    def update_step(self, lab_id: str, step_id: str, 
                    status: str, increment_attempts: bool = True) -> None:
        """Atualiza status e tentativas de um step atomicamente."""
    
    def get_resume_step(self, lab_id: str, 
                        lab_metadata: LabMetadata) -> str:
        """Retorna o step_id de retomada (primeiro não concluído)."""
    
    def _compute_lab_status(self, lab_id: str, 
                             lab_metadata: LabMetadata) -> str:
        """Recalcula status do lab com base nos steps."""
        # not_started → in_progress → completed
```

### ValidationService

```python
class ValidationService:
    """Orquestra a execução de validadores e atualização de progresso."""
    
    def __init__(self, lab_catalog: LabCatalog, 
                 progress_store: ProgressStore):
        self._catalog = lab_catalog
        self._progress = progress_store
        self._validators = self._load_validators()
    
    def validate(self, lab_id: str, step_id: str, 
                 context: dict) -> dict:
        """
        Executa validação e retorna resposta completa da API.
        1. Cria boto3.Session() a partir de ~/.aws
        2. Carrega módulo validators/labXX.py
        3. Chama validate_step(session, context)
        4. Atualiza ProgressStore
        5. Calcula show_hint_button baseado em attempts e hint_threshold
        6. Retorna resposta formatada
        """
    
    def _create_boto3_session(self) -> boto3.Session:
        """Cria sessão boto3 lendo credenciais do volume ~/.aws."""
    
    def _load_validators(self) -> dict:
        """Importa dinamicamente validators/labXX.py para todos os labs."""
```

### CloudFormationService

```python
class CloudFormationService:
    """Gerencia operações de deploy e teardown de stacks CloudFormation."""
    
    def deploy(self, lab_id: str, 
               lab_metadata: LabMetadata) -> dict:
        """Inicia criação da stack CloudFormation do lab."""
    
    def teardown(self, lab_id: str) -> dict:
        """Inicia exclusão da stack e retorna lista de recursos residuais."""
    
    def get_status(self, lab_id: str) -> dict:
        """Consulta describe_stacks e retorna status e outputs."""
    
    def _get_stack_name(self, lab_id: str) -> str:
        return f"workshop-{lab_id}"
    
    def _get_template_path(self, lab_id: str) -> str:
        return f"labs/{lab_id}/cloudformation/stack.yaml"
```

## Error Handling

### Hierarquia de Exceções

```python
class WorkshopError(Exception):
    """Base para todos os erros da plataforma."""
    code: str
    http_status: int

class CredentialsError(WorkshopError):
    code = "CREDENTIALS_EXPIRED"
    http_status = 401

class PermissionsError(WorkshopError):
    code = "PERMISSIONS_DENIED"
    http_status = 403

class LabNotFoundError(WorkshopError):
    code = "LAB_NOT_FOUND"
    http_status = 404

class StackDeployError(WorkshopError):
    code = "STACK_DEPLOY_FAILED"
    http_status = 422
```

### Flask Error Handler Global

```python
@app.errorhandler(WorkshopError)
def handle_workshop_error(e: WorkshopError):
    return jsonify({
        "error": True,
        "code": e.code,
        "message": str(e),
        "http_status": e.http_status
    }), e.http_status

@app.errorhandler(Exception)
def handle_unexpected_error(e: Exception):
    app.logger.exception("Erro inesperado")
    return jsonify({
        "error": True,
        "code": "INTERNAL_ERROR",
        "message": "Erro interno do servidor.",
        "http_status": 500
    }), 500
```

### Tratamento de Erros AWS em Validadores

Todos os validadores DEVEM capturar `botocore.exceptions.ClientError` e tratar:

```python
from botocore.exceptions import ClientError, NoCredentialsError

def _safe_validate(fn):
    """Decorator que converte exceções AWS em ValidationResult."""
    def wrapper(session, context):
        try:
            return fn(session, context)
        except NoCredentialsError:
            return ValidationResult(
                passed=False,
                message="Credenciais AWS nao encontradas. Verifique ~/.aws."
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("ExpiredTokenException", "InvalidClientTokenId"):
                return ValidationResult(
                    passed=False,
                    message="Credenciais AWS expiradas. Reconfigure ~/.aws."
                )
            return ValidationResult(
                passed=False,
                message=f"Erro AWS ({code}): {e.response['Error']['Message']}"
            )
    return wrapper
```

### Estratégia de Polling de Stack CloudFormation

O frontend chama `GET /api/stack-status/{lab_id}` a cada 5 segundos enquanto o status for `*_IN_PROGRESS`. O backend não mantém estado de polling — cada chamada executa `describe_stacks` diretamente.

**Estados terminais (polling para):**
- `CREATE_COMPLETE` → sucesso
- `UPDATE_COMPLETE` → sucesso
- `DELETE_COMPLETE` → sucesso
- `CREATE_FAILED`, `ROLLBACK_COMPLETE`, `DELETE_FAILED` → falha com exibição do erro

## Testing Strategy

### Abordagem Dual: Testes de Propriedade + Testes de Exemplo

A estratégia de testes combina **property-based tests** (para validar invariantes universais com inputs gerados) e **testes de exemplo** (para cenários específicos e pontos de integração).

**Framework recomendado:** `pytest` + `hypothesis` (property-based testing em Python)

### Testes de Propriedade (Property-Based Tests)

Usados para validar comportamentos que devem valer para qualquer combinação válida de inputs. Cada teste de propriedade referencia explicitamente a propriedade correspondente neste documento (via tag `@settings` e docstring).

Exemplos de propriedades a serem testadas com geração aleatória de inputs:
- Cálculo de progresso (Property 2): gerar estados arbitrários de `progress.json` e verificar que o cálculo de steps concluídos é consistente
- Step de retomada (Property 3): gerar sequências de steps com statuses mistos e verificar que o primeiro não-concluído é retornado
- Limiar de dica (Property 6): gerar contagens de tentativas e limiares e verificar a lógica de exibição de dica
- Serialização de progresso (Property 12): gerar estados de progresso, serializar e desserializar, verificar round-trip sem perda

### Testes de Exemplo (Unit/Integration Tests)

Usados para cenários específicos, pontos de integração e edge cases:
- Dashboard exibe exatamente 10 labs com metadados corretos
- Disclaimer de custos aparece antes do primeiro step de tarefa
- Confirmação de teardown é exigida antes de deletar a stack
- Resposta de validação é JSON sem recarregar página

### Testes de Smoke

Verificações estáticas de configuração executadas uma vez:
- `docker-compose.yml` monta `~/.aws` como read-only
- `progress.json` está no `.gitignore`
- 10 arquivos `cloudformation/stack.yaml` existem com sintaxe YAML válida
- Flask está configurado para bind somente em `127.0.0.1`

### Estratégia de Mock para Testes de Validadores

Todos os testes de validadores usam `unittest.mock.patch` para substituir chamadas boto3, permitindo testar a lógica de validação sem chamadas reais à AWS:

```python
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st

@given(bucket_name=st.text(min_size=3, max_size=63))
def test_validate_step_handles_any_bucket_name(bucket_name):
    """Property 4, 8: validate_step retorna ValidationResult para qualquer input."""
    mock_session = MagicMock()
    mock_session.client.return_value.list_buckets.return_value = {
        "Buckets": [{"Name": bucket_name}]
    }
    result = validate_step(mock_session, {"step_id": "step-01", 
                                           "bucket_prefix": bucket_name[:3]})
    assert isinstance(result, ValidationResult)
    assert isinstance(result.passed, bool)
    assert len(result.message) > 0
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Pré-requisito ausente sempre resulta em falha descritiva

*Para qualquer* combinação de pré-requisitos ausentes ou inválidos (Docker abaixo da versão mínima, AWS CLI ausente, credenciais inválidas, permissões insuficientes), o `check_requirements.py` deve retornar exit code não-zero e exibir uma mensagem identificando especificamente qual pré-requisito está faltante.

**Validates: Requirements 1.2, 1.3**

---

### Property 2: Cálculo de progresso reflete exatamente o estado dos steps

*Para qualquer* estado válido de `progress.json`, o número de steps concluídos exibido para um lab deve ser igual ao count de steps com `status == "passed"` naquele lab, e o total deve ser igual ao número de steps definidos em `metadata.json` para aquele lab.

**Validates: Requirements 2.2**

---

### Property 3: Step de retomada é sempre o primeiro step não concluído

*Para qualquer* lab com progresso parcial (mistura de steps `passed` e não-`passed`), o step de retomada retornado por `get_resume_step` deve ser o primeiro step (pela ordem definida em `metadata.json`) cujo status não é `"passed"`.

**Validates: Requirements 2.3, 2.4**

---

### Property 4: Validação bem-sucedida sempre atualiza o progresso

*Para qualquer* step em qualquer lab, quando `validate_step` retorna `ValidationResult(passed=True)`, o `ProgressStore` deve atualizar o status daquele step para `"passed"` com `passed_at` preenchido e incrementar `attempts` em 1.

**Validates: Requirements 5.2**

---

### Property 5: Retry ilimitado — tentativas não bloqueiam validação

*Para qualquer* step com qualquer número de tentativas anteriores (incluindo números arbitrariamente grandes), a chamada à API `POST /api/validate/{lab_id}/{step_id}` deve executar o validador e retornar um resultado, sem retornar erro 429 ou similar baseado em contagem de tentativas.

**Validates: Requirements 5.4**

---

### Property 6: Exibição de dica segue o limiar configurado

*Para qualquer* step com `hint_threshold` configurado em `metadata.json`, o campo `show_hint_button` na resposta da API de validação deve ser `true` se e somente se `attempt_count >= hint_threshold` após a tentativa atual.

**Validates: Requirements 5.5**

---

### Property 7: Lab marcado como concluído somente quando todos os steps passam

*Para qualquer* lab, `_compute_lab_status` deve retornar `"completed"` se e somente se todos os steps daquele lab (do tipo `"task"`) possuem `status == "passed"` no `ProgressStore`.

**Validates: Requirements 5.7**

---

### Property 8: Validador retorna ValidationResult para qualquer exceção AWS

*Para qualquer* validador de qualquer lab, quando `validate_step` é chamado com uma sessão boto3 que lança `ClientError` ou `NoCredentialsError`, a função deve retornar `ValidationResult(passed=False)` com mensagem não-vazia, sem propagar a exceção.

**Validates: Requirements 5.3, 5.6**

---

### Property 9: Todos os steps de todos os labs têm campos obrigatórios

*Para qualquer* lab no catálogo e qualquer step daquele lab, o `metadata.json` deve conter `step_id`, `title`, `type` e `hint_threshold` não-nulos.

**Validates: Requirements 4.1, 7.1**

---

### Property 10: Cobertura de domínios DEA-C01 é completa

*Para qualquer* task dos domínios DEA-C01 (1.1-1.4, 2.1-2.4, 3.1-3.4, 4.1-4.5), deve existir ao menos um lab no catálogo cujo campo `dea_tasks` contenha aquela task.

**Validates: Requirements 10.2, 10.3, 10.4, 10.5**

---

### Property 11: Arquivos estáticos não referenciam URLs externas

*Para qualquer* arquivo HTML servido pelo Flask, todos os atributos `src`, `href` e `url()` em CSS que referenciam recursos (scripts, estilos, fontes, imagens) devem ser caminhos relativos ou absolutos dentro do servidor local, nunca URLs de CDN externo.

**Validates: Requirements 8.2**

---

### Property 12: Serialização/deserialização de progress.json preserva dados

*Para qualquer* estado válido de progresso (qualquer combinação de labs e steps com status válidos), ler `progress.json`, modificar um step e escrever de volta deve resultar em um arquivo que, quando relido, contém exatamente o estado modificado sem perda de dados de outros labs ou steps.

**Validates: Requirements 2.5, 9.2**
