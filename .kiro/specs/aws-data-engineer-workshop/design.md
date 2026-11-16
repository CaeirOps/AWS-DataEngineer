# Design Document

## Overview

A Plataforma de Workshop AWS Data Engineer é uma aplicação web local, distribuída via `git clone` e executada com Docker Compose. O backend é um servidor Flask (Python 3.11+) que serve conteúdo estático e expõe uma API REST para validação de steps, gerenciamento de progresso e operações CloudFormation. Toda a lógica de validação AWS é implementada em módulos Python com boto3, sem autenticação própria, sem banco de dados externo e sem telemetria.

A stack é composta por dois containers: `workshop` (Flask + gunicorn, em rede Docker `internal`, sem acesso direto à internet) e `gateway` (Squid, único com porta publicada em `127.0.0.1` e único com saída para a internet, filtrada por Allowlist). Dois scripts no host, `check_requirements.py` e `start.py`, usam somente a biblioteca padrão do Python.

O princípio de segurança adotado é "security first", seguindo as recomendações de segurança do GitHub e da AWS. Na prática: o container `workshop` recebe somente credenciais temporárias por variáveis de ambiente e nunca monta `~/.aws`; a API local valida `Host`, `Origin` e um cabeçalho próprio; os containers rodam sem privilégios; as imagens e dependências são fixadas por digest e por hash; e o repositório tem CI, CodeQL, Dependabot e CODEOWNERS.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                               Host do Usuário                             │
│                                                                           │
│  start.py / check_requirements.py (stdlib, rodam no host)                 │
│                                                                           │
│  Browser ──▶ http://127.0.0.1:${WORKSHOP_PORT:-5000}                      │
│                      │                                                    │
│  ┌───────────────────▼──────────────────────────────────────────────────┐ │
│  │  rede "egress" (bridge comum, com saída para a internet)             │ │
│  │                                                                      │ │
│  │   ┌────────────────────────────────────────────┐                    │ │
│  │   │ gateway (Squid, ubuntu/squid:<tag fixa>)    │──▶ AWS endpoints   │ │
│  │   │  :8080 reverse proxy (accel) ─┐             │   (*.amazonaws.com,│ │
│  │   │  :3128 forward proxy (CONNECT │ 443,        │    *.api.aws)      │ │
│  │   │         somente allowlist)    │             │   somente 443      │ │
│  │   └───────────────▲───────────────┼─────────────┘                    │ │
│  └───────────────────┼───────────────┼──────────────────────────────────┘ │
│  ┌───────────────────┼───────────────┼──────────────────────────────────┐ │
│  │  rede "workshop-internal" (internal: true, sem rota para a internet) │ │
│  │                   │               ▼                                  │ │
│  │   ┌───────────────┴───────────────────────────┐                      │ │
│  │   │ workshop (gunicorn + Flask, 0.0.0.0:5000)  │                      │ │
│  │   │  HTTPS_PROXY=http://gateway:3128           │                      │ │
│  │   │  Validation Modules (boto3)                │                      │ │
│  │   │  Env: AWS_* temporárias (sem ~/.aws)       │                      │ │
│  │   │  Volume: ./progress:/app/progress          │                      │ │
│  │   └────────────────────────────────────────────┘                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘

Entrada: Browser -> 127.0.0.1:PORT -> gateway:8080 -> workshop:5000
Saída:   workshop -> gateway:3128 (CONNECT :443, allowlist) -> AWS endpoints
```

O Docker não publica portas de containers conectados apenas a uma rede `internal: true`. Por isso o `workshop` não tem `ports:` e a entrada do browser passa pelo `gateway`, que está nas duas redes. O mesmo container é o único ponto de saída para a internet, o que permite aplicar a Allowlist (requisitos 9.5 e 9.6).

A arquitetura continua sem banco de dados e sem autenticação. O estado do usuário fica em um único arquivo JSON no host.

### Decisões de rede

| Decisão | Motivo |
|---------|--------|
| `workshop` somente em `workshop-internal` (`internal: true`) | Sem rota direta para a internet; qualquer saída precisa passar pelo proxy (9.5) |
| `gateway` em `workshop-internal` e `egress` | Único elo entre a rede interna, o host e a internet |
| Porta publicada só no `gateway` como `127.0.0.1:${WORKSHOP_PORT:-5000}:8080` | Loopback do host apenas (9.1, 1.9) |
| Flask escuta em `0.0.0.0:5000` dentro do container | O tráfego encaminhado pelo Docker chega pela interface de rede do container, não pelo loopback. A restrição a localhost é feita na publicação da porta |
| Squid com `http_access deny all` por padrão | Tudo que não for explicitamente permitido é recusado (9.5, 9.6) |
| Downloads de build (imagem base, `pip install`) ocorrem no `docker compose build` | Fora da restrição de runtime; documentado no README (9.7) |
| O container `workshop` não acessa `portal.sso.*` nem endpoints de login | Ele só usa credenciais temporárias já exportadas no host; a renovação do login é manual no host (1.16). A Allowlist continua limitada a `.amazonaws.com` e `.api.aws` |
| O Squid repassa ao Flask o `Host` enviado pelo browser (`http_port 8080 accel vhost`) | O Flask valida `Host` contra `127.0.0.1:<porta>` e `localhost:<porta>`; a porta chega ao container pela variável `WORKSHOP_PORT` (13.1, 13.5) |

## Components and Interfaces

### 1. check_requirements.py

Script de pré-validação executado no host antes de `python start.py`. Usa somente a biblioteca padrão do Python e `subprocess` para chamar `docker` e `aws`. Não usa boto3 no host (1.2).

**Verificações:**

| Pré-requisito | Comando | Critério |
|---------------|---------|----------|
| Docker >= 20 com daemon ativo | `docker version --format '{{.Server.Version}}'` | Versão >= 20 e comando retorna 0 (daemon respondendo) |
| Docker Compose v2 | `docker compose version --short` | Versão major >= 2 |
| AWS CLI >= 2 | `aws --version` | Versão major >= 2 |
| Credenciais temporárias válidas | `aws sts get-caller-identity --profile $AWS_PROFILE` e `aws configure export-credentials --profile $AWS_PROFILE --format process` | Ambos retornam 0 e o JSON exportado contém `SessionToken` e `Expiration` (1.2, 1.14). `AWS_PROFILE` padrão: `default` (1.12) |
| Porta livre | tentativa de `bind` via `socket` em `127.0.0.1:$WORKSHOP_PORT` | Bind bem-sucedido. `WORKSHOP_PORT` padrão: 5000 |

A verificação de permissões por lab não faz parte do escopo (removida dos requisitos).

A verificação de credenciais reutiliza `host_credentials.py` (seção 1a). Credenciais sem `SessionToken` ou `Expiration` falham com mensagem pedindo AWS IAM Identity Center (SSO) ou `aws login` (1.14). Nenhum valor de credencial é impresso.

**Responsabilidades:**
- Executar todas as verificações e listar todas as falhas, não só a primeira
- Exibir, para cada falha, o pré-requisito, o valor encontrado e os passos para corrigir
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

### 1a. host_credentials.py (módulo de host, somente stdlib)

Módulo compartilhado por `start.py` e `check_requirements.py` que obtém e valida as credenciais temporárias do profile. Fica na raiz do repositório e é coberto pelo CODEOWNERS.

```python
@dataclass(frozen=True)
class TempCredentials:
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    session_token: str = field(repr=False)
    expiration: datetime          # timezone-aware, UTC

class LongLivedCredentialsError(Exception): ...
class CredentialsExportError(Exception): ...

def export_credentials(profile: str, run=subprocess.run) -> TempCredentials:
    """Executa `aws configure export-credentials --profile <profile> --format process`
    (lista de argumentos, sem shell), lê o JSON de stdout e valida.
    Levanta LongLivedCredentialsError se faltar SessionToken ou Expiration,
    e CredentialsExportError se o comando falhar ou a saída não for JSON válido.
    As mensagens de erro nunca contêm valores de credenciais."""

def to_environment(creds: TempCredentials) -> dict[str, str]:
    """Retorna AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN e
    WORKSHOP_CREDENTIALS_EXPIRATION (ISO 8601 UTC)."""
```

- O `stdout` do AWS CLI é lido em memória e nunca gravado em disco nem repassado ao terminal. O `stderr` do CLI só é exibido depois de filtrado, sem linhas que contenham os valores lidos.
- O formato `process` devolve `Version`, `AccessKeyId`, `SecretAccessKey`, `SessionToken` e `Expiration`. Ausência de `SessionToken` ou de `Expiration` indica credencial de longa duração (access key de usuário IAM) e é recusada (1.14).
- `repr=False` nos campos evita que um traceback ou log exiba valores.

### 1b. start.py

Script de inicialização executado no host. Usa somente a biblioteca padrão (`subprocess`, `urllib.request`, `socket`, `webbrowser`, `time`, `os`).

**Fluxo:**
1. Lê `WORKSHOP_PORT` (padrão 5000) e `AWS_PROFILE` (padrão `default`).
2. Chama `host_credentials.export_credentials(AWS_PROFILE)`. Se falhar ou se as credenciais forem de longa duração, imprime mensagem pedindo SSO ou `aws login` e sai com código 1, sem subir containers (1.14).
3. Executa `docker compose up -d --build` com `env={**os.environ, **to_environment(creds)}`. O Compose declara essas variáveis em modo pass-through (sem valor no arquivo) e as entrega ao `workshop`. Nada é gravado em disco (nem `.env` temporário) e nada é impresso (1.5).
4. Faz polling em `http://127.0.0.1:${WORKSHOP_PORT}/health` a cada 2 s, por até 60 s (1.4).
5. Sucesso: imprime a URL, o horário de expiração da sessão (sem valores de credenciais) e abre o browser com `webbrowser.open` (1.11).
6. Timeout: imprime o diagnóstico abaixo, sai com código 1 e não derruba os containers (1.8).

**Modo `--refresh` (1.15):**
1. Exporta novamente as credenciais do profile e valida como no fluxo normal.
2. Executa `docker compose up -d --force-recreate --no-deps workshop`, que recria somente o serviço `workshop` com as novas variáveis. O volume `./progress` e o `gateway` são preservados.
3. Faz o polling de `/health` como no fluxo normal.
4. A renovação do login (`aws sso login` ou `aws login`) é sempre manual no host. O `start.py --refresh` não executa nenhum comando de login (1.16).

**Diagnóstico em caso de timeout:**
- `docker compose ps` (estado e health de cada serviço)
- `docker compose logs --tail 50 workshop gateway`
- Verificação de porta ocupada por outro processo (tentativa de `bind` via `socket`)
- Causas comuns:
  - AirPlay Receiver do macOS ocupa a porta 5000. Sugerir `WORKSHOP_PORT=5050`.
  - Docker Desktop sem memória suficiente.
  - Erro de import na aplicação (ver logs do `workshop`).
  - Sessão expirada ou variáveis de credenciais ausentes no container (renovar o login no host e executar `python start.py --refresh`).
- Comando para encerrar: `docker compose down`

```python
POLL_INTERVAL_S = 2
TIMEOUT_S = 60

def wait_for_health(port: int, timeout_s: int = TIMEOUT_S,
                    interval_s: int = POLL_INTERVAL_S,
                    opener=urllib.request.urlopen,
                    clock=time.monotonic, sleep=time.sleep) -> bool:
    """Retorna True se /health responder 200 antes do timeout."""

def build_diagnostics(port: int, run=subprocess.run) -> str:
    """Monta texto com compose ps, logs --tail 50, checagem de porta e causas comuns."""

def main() -> int:
    """0 em sucesso; 1 em timeout (containers mantidos)."""
```

Os parâmetros `opener`, `clock`, `sleep` e `run` são injetáveis para permitir testes sem Docker e sem esperar 60 s reais.

### 2. Flask Server (app/server.py)

Aplicação WSGI Flask que atua como API backend e servidor de arquivos estáticos. Executada por `gunicorn` (2 workers), não pelo servidor de desenvolvimento do Flask. O objeto `app` é exposto em `app/server.py`.

**Configuração:**
- Dentro do container: `gunicorn --bind 0.0.0.0:5000 --workers 2 app.server:app`. O bind em `127.0.0.1` dentro do container tornaria o serviço inacessível, porque o tráfego encaminhado pelo Docker chega pela interface de rede do container.
- A restrição a localhost é feita na publicação de porta do `gateway` (`127.0.0.1:${WORKSHOP_PORT:-5000}:8080`). O `workshop` não publica portas.
- `debug=False` em produção (controlado por variável de ambiente `FLASK_ENV`)
- `WORKSHOP_PORT` é passada ao container pelo Compose e usada por `app/http_security.py` para montar a allowlist de `Host` e `Origin` (13.5)
- CORS desabilitado (mesma origem: o browser acessa pelo `gateway`)
- `create_app(config)` constrói a aplicação Flask e aceita em `config` o diretório de labs, o caminho do `progress.json` e `validator_loader` (função que carrega os módulos validadores). O `ValidationService` recebe esse `validator_loader` diretamente, sem depender de variável de ambiente ou de patch de módulo; quando ausente, usa o carregador padrão de `app/validators/`. O objeto `app` exposto ao gunicorn é `create_app(config_padrao)`.
- Com 2 workers, o `ProgressStore` não pode depender apenas de `threading.Lock` em memória. A escrita de `progress.json` deve ser atômica (arquivo temporário + `os.replace`) e protegida por lock de arquivo (`fcntl.flock`) para evitar perda de atualização entre processos.

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
| `GET` | `/api/labs/<lab_id>` | Retorna metadados e steps de um lab, com as Trilhas disponíveis e indisponíveis de cada step `task` (11.1, 11.6) |
| `GET` | `/api/labs/<lab_id>/steps/<step_id>/content?path=console\|cli` | Retorna o Markdown do cenário (`scenario.md`) concatenado ao da Trilha escolhida (11.1, 11.8, 11.7) |
| `GET` | `/api/labs/<lab_id>/steps/<step_id>/hint?path=console\|cli` | Retorna a Dica Detalhada da Trilha escolhida (11.5) |
| `POST` | `/api/labs/<lab_id>/steps/<step_id>/visit` | Marca como concluído um step que não é `task`, quando o usuário avança além dele (2.6) |
| `GET` | `/api/session` | Retorna `expires_at`, `seconds_remaining` e `status` da sessão, sem valores de credenciais (12.1) |

`POST .../visit` só vale para steps `info`, `deploy`, `teardown` e `completion`. Para step `task`, retorna `STEP_REQUIRES_VALIDATION` (409), porque esses steps só passam por validação. A rota chama `ProgressStore.mark_visited`, é idempotente (repetir a chamada não altera `passed_at` nem `attempts`) e não aceita corpo. Lab ou step inexistente retorna `LAB_NOT_FOUND`/`STEP_NOT_FOUND` (404).

`path` aceita somente `console` ou `cli`. Valor ausente ou inválido resulta em `INVALID_PATH` (400). Trilha válida mas ausente de `paths` do step resulta em `PATH_UNAVAILABLE` (409), com o motivo de `unavailable_paths` na mensagem. Rotas de conteúdo e dica só existem para steps do tipo `task`; para outros tipos, o conteúdo é único e vem de `GET /api/labs/<lab_id>`. A troca de Trilha é persistida por `PUT /api/progress` com `{"preferences": {"path": "cli"}}` (11.3). Nenhuma dessas rotas altera o status do step (11.2).

**Proteção da API local (Requirement 13):** o módulo `app/http_security.py` registra `before_request` e `after_request` em `create_app`.

| Verificação | Regra | Resposta em caso de falha |
|-------------|-------|---------------------------|
| `Host` (toda requisição, exceto `GET /health`) | Igual a `127.0.0.1:<porta>` ou `localhost:<porta>`, com `<porta>` de `WORKSHOP_PORT` | 421 `HOST_NOT_ALLOWED` |
| `Origin` (`POST`, `PUT`, `DELETE`) | Presente e igual a `http://127.0.0.1:<porta>` ou `http://localhost:<porta>` | 403 `ORIGIN_NOT_ALLOWED` |
| `Content-Type` (`POST`, `PUT`, `DELETE`) | `application/json` (parâmetro `charset` aceito) | 415 `UNSUPPORTED_MEDIA_TYPE` |
| `X-Workshop-Request` (`POST`, `PUT`, `DELETE`) | Igual a `1` | 403 `MISSING_WORKSHOP_HEADER` |

`GET /health` fica fora da checagem de `Host` porque o healthcheck do container chama `localhost:5000` e a rota só retorna `{"status": "ok"}`. A ordem é: `Host`, `Origin`, `Content-Type`, cabeçalho próprio. Uma requisição recusada não chega à rota e não altera estado. O browser não consegue forjar `Origin` nem o cabeçalho próprio em requisição cross-origin sem preflight, e o servidor não responde a `OPTIONS` com CORS, então o preflight falha.

Cabeçalhos de segurança em todas as respostas, inclusive as de erro: `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` e `Cross-Origin-Resource-Policy: same-origin` (13.4). A CSP `default-src 'self'` exige que o frontend não use scripts nem estilos inline; isso já vale para o frontend atual, sem CDN (8.2).

**Como a porta chega ao Flask:** o browser acessa `127.0.0.1:<porta>` e envia `Host: 127.0.0.1:<porta>`. O Squid recebe em `:8080` (porta interna) e, com `http_port 8080 accel vhost`, repassa ao Flask o `Host` original do browser. O `docker-compose.yml` passa `WORKSHOP_PORT=${WORKSHOP_PORT:-5000}` ao `workshop`, e `app/http_security.py` monta a allowlist com esse valor. O `squid.conf` troca a ACL `reverse_site` (baseada em `dstdomain workshop`) por uma ACL de porta local (`acl reverse_listener localport 8080`), porque com `vhost` o domínio de destino passa a ser o `Host` do browser. Isso mantém `http_access deny all` ao final e só aceita na porta 8080 o tráfego do reverse proxy. A confirmação em ambiente real (o `Host` de um browser chega ao Flask como `127.0.0.1:<porta>`, e `Host: evil.example` via gateway recebe 421) faz parte da verificação final.

**Sessão (Requirement 12):** o módulo `app/session.py` lê `WORKSHOP_CREDENTIALS_EXPIRATION` e calcula o estado no servidor.

```python
EXPIRING_THRESHOLD_S = 600

@dataclass(frozen=True)
class SessionState:
    expires_at: Optional[str]     # ISO 8601 UTC, ou None se ausente ou inválido
    seconds_remaining: int        # nunca negativo
    status: str                   # "valid" | "expiring" | "expired"

def get_session_state(env: Mapping[str, str] = os.environ,
                      now: Callable[[], datetime] = utcnow) -> SessionState: ...

def require_active_session() -> None:
    """Levanta SessionExpiredError (SESSION_EXPIRED, 401) se status == "expired"."""
```

`status` é `expired` se `seconds_remaining <= 0` ou se a variável estiver ausente ou inválida (falha fechada, 12.3), `expiring` se `1 <= seconds_remaining <= 600` e `valid` acima disso (12.2). `require_active_session()` é chamada no início das rotas que chamam a AWS (`POST /api/validate/...`, `POST /api/deploy/...`, `POST /api/teardown/...`, `GET /api/stack-status/...`) antes de criar qualquer cliente boto3 (12.6). As demais rotas (conteúdo, progresso, visit, session, health) continuam funcionando com a sessão expirada.

**Rota de saúde:**

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Retorna `{"status": "ok"}`. Usada pelo healthcheck do Docker e pelo `start.py` |

O Dashboard fica acessível em `http://localhost:${WORKSHOP_PORT}` (padrão 5000), servido via `gateway` (requisito 2.1).

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
        boto3_session: Sessão boto3 autenticada (criada a partir das variáveis de ambiente de credenciais temporárias)
        context: Dicionário com step_id, lab_id, attempt_count e parâmetros extras
    
    Returns:
        ValidationResult com passed, message e hint opcional
    
    Raises:
        Não deve lançar exceções; capturar e retornar ValidationResult(passed=False)
    """
```

**Independência da Trilha (11.4):** o validador não recebe a Trilha. `context` nunca contém a chave `path`, e `validate_step` verifica somente o estado final dos recursos na AWS, que é o mesmo nas duas Trilhas (Console ou CLI). A rota `POST /api/validate/<lab_id>/<step_id>` ignora qualquer `path` presente no corpo da requisição e o `ValidationService` o remove de `context` antes de chamar o validador. Consequências: um recurso criado pelo Console e outro criado pelo CLI passam na mesma validação, e nenhuma mensagem de erro depende da Trilha. A Trilha só afeta o conteúdo exibido (instruções e dica).

**Exemplo de validador (lab01, step-01, bucket S3 criado):**

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
    
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in CREDENTIAL_ERROR_CODES:
            return ValidationResult(
                passed=False,
                message=f"{code}: {e.response['Error']['Message']}. "
                        "Verifique as credenciais AWS do profile em uso."
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
  "preferences": {
    "path": "console"
  },
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

**Preferências (11.3):** `preferences.path` fica no topo do arquivo e aceita `console` ou `cli`, com padrão `console`. É atualizado sempre que o usuário troca de Trilha e usado como Trilha inicial em todos os steps `task` seguintes (quando o step não oferece essa Trilha, o frontend usa a outra disponível sem alterar a preferência). Arquivos sem `preferences` (criados antes desta versão) são lidos como `{"path": "console"}`. Valores diferentes de `console` e `cli` são rejeitados com `INVALID_PATH`. Trocar de Trilha atualiza somente `preferences.path` e `last_updated`; `status`, `attempts`, `last_attempt_at` e `passed_at` dos steps não mudam (11.2).

**Regras de transição de estado de step:**

```
not_visited → failed  (primeira tentativa falhou)
not_visited → passed  (primeira tentativa passou, ou step não-task visitado)
failed      → passed  (retry bem-sucedido)
passed      → passed  (retry após conclusão, sem regressão)
```

**Steps que não são `task` (2.6):** `info`, `deploy`, `teardown` e `completion` não têm validação. Quando o usuário avança além deles, o frontend chama `POST /api/labs/<lab_id>/steps/<step_id>/visit` e o `ProgressStore.mark_visited` grava `status: "passed"` e `passed_at`, sem incrementar `attempts` (permanece 0). Com isso `get_resume_step` avança para o próximo step não concluído, e o indicador do wizard e a navegação direta (3.2) usam o status vindo do servidor, sem `sessionStorage`. `_compute_lab_status` continua considerando somente os steps `task` para `completed`; um step não-task `passed` só influencia a transição `not_started → in_progress` e o contador de steps concluídos (Property 2).

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
├── metadata.json           # Metadados estruturados do lab
├── steps/
│   ├── step-01/            # step do tipo info/deploy/teardown/completion: conteúdo único
│   │   └── content.md
│   ├── step-02/            # step do tipo task: uma pasta com 5 arquivos
│   │   ├── scenario.md     # cenário e critério de aceitação (comum às Trilhas)
│   │   ├── console.md      # instruções da Trilha Console
│   │   ├── cli.md          # instruções da Trilha CLI
│   │   ├── hint-console.md # Dica Detalhada da Trilha Console
│   │   └── hint-cli.md     # Dica Detalhada da Trilha CLI
│   └── ...
├── cloudformation/
│   └── stack.yaml          # Template CloudFormation do lab
└── assets/
    └── *.png               # Diagramas e imagens
```

O arquivo único `content.md` na raiz do lab deixa de existir. Cada step tem seu diretório `steps/<step_id>/`, e o `step_id` do `metadata.json` é o nome do diretório.

Quando uma Trilha não está em `paths` de um step `task` (11.6), os arquivos dela (`console.md` e `hint-console.md`, ou `cli.md` e `hint-cli.md`) não existem, e o motivo fica em `unavailable_paths`.

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
  "services": ["Amazon S3"],
  "prerequisites": {
    "hard": [],
    "recommended": []
  },
  "steps": [
    {
      "step_id": "step-01",
      "title": "Criar bucket S3 para o Data Lake",
      "type": "task",
      "hint_threshold": 3,
      "paths": ["console", "cli"]
    },
    {
      "step_id": "step-04",
      "title": "Explorar o painel de Lake Formation",
      "type": "task",
      "hint_threshold": 3,
      "paths": ["console"],
      "unavailable_paths": {
        "cli": "Esta tarefa depende de uma visualização interativa que não existe na API."
      }
    }
  ],
  "residual_resources": [
    "Bucket S3 criado manualmente (nao gerenciado pela stack)"
  ]
}
```

**Campo `services` (5.7):** obrigatório, lista não vazia de strings não vazias com os nomes dos serviços AWS usados no lab (por exemplo `"Amazon S3"`, `"AWS Glue"`). O `LabCatalog` rejeita na carga um `metadata.json` sem `services`, com lista vazia ou com item que não seja string não vazia. A tela de conclusão exibe esta lista junto dos domínios DEA-C01 (`dea_domains`).

**Campos de Trilha em steps `task`:**
- `paths` (obrigatório em `task`): lista não vazia com `console` e/ou `cli`. Define as Trilhas disponíveis.
- `unavailable_paths` (opcional): objeto `{ "<trilha>": "<motivo>" }`. Toda Trilha ausente de `paths` deve ter motivo não vazio aqui (11.6). Uma Trilha não pode estar em `paths` e em `unavailable_paths` ao mesmo tempo.
- Steps de outros tipos não têm `paths` nem `unavailable_paths`.

**Convenções de conteúdo:**
- Termos técnicos permanecem em inglês no texto em português (4.5).
- `scenario.md` traz o cenário narrativo e o critério de aceitação, iguais para as duas Trilhas, porque o validador verifica o mesmo estado final (11.4).
- **Trilha CLI (`cli.md`, 11.7):** comandos do AWS CLI v2 que usam `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"`, ou placeholders como `<NOME_DO_BUCKET>` para valores que o usuário define. Nunca contém credenciais (chaves `AKIA`/`ASIA`, `aws_secret_access_key`, `aws_session_token`). Cada comando é precedido por uma linha explicando o que ele faz.
- **Trilha Console (`console.md`, 11.8):** caminho de navegação no formato `Serviço > Menu > Botão`, seguido das configurações relevantes da tela que o usuário deve observar e por que importam para o exame DEA-C01, além do mínimo necessário para concluir a tarefa. O mínimo vem primeiro e as explorações ficam em seção separada.
- `hint-console.md` e `hint-cli.md` seguem a mesma convenção da Trilha correspondente.
- O campo `prerequisites` do `lab-01` lista os cinco pré-requisitos do requisito 7.5 (conta AWS com acesso administrativo, SQL básico, linha de comando, Docker, Git básico) e o frontend os exibe no início do lab.
- A tela de aviso de recursos residuais (`residual_resources`) é exibida após a confirmação do teardown, independentemente do status real da exclusão da stack (6.7).

**Tipos de step:**

| Tipo | Descrição |
|------|-----------|
| `info` | Conteúdo informativo sem validação (cenário, pré-requisitos) |
| `deploy` | Instrução de deploy CloudFormation com botão de status |
| `task` | Tarefa com botão "Validar" que chama a API e seletor de Trilha (Console \| CLI). Conteúdo em `scenario.md` + arquivos por Trilha |
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
    ├── cloudformation.js   # Polling de status de stack
    ├── api.js              # fetch central: envia X-Workshop-Request e Content-Type JSON
    └── session.js          # Cronometro de sessao e bloqueio de acoes AWS
```

**Roteamento client-side:**

```
/                    → Dashboard (todos os labs)
/lab/{lab_id}        → Lab (abre no step de retomada)
/lab/{lab_id}/{step} → Step específico (somente se visitado)
```

**Navegação e retomada (2.4, 2.6, 3.2):** o frontend não usa `sessionStorage` nem outro armazenamento do browser para saber o que foi visitado. "Visitado" é o status do step em `GET /api/progress`: um step é navegável diretamente quando seu status é diferente de `not_visited` ou quando é o step de retomada. Ao clicar em "Avançar" (ou em "Finalizar Lab") a partir de um step que não é `task`, `lab.js` chama `POST /api/labs/<lab_id>/steps/<step_id>/visit`, atualiza o estado local com a resposta e só então navega. Falha da chamada exibe o erro e mantém o usuário no step atual. Steps `task` seguem marcados somente pela validação. A tela de conclusão (step `completion`) lista os `services` e os `dea_domains` do lab, vindos de `GET /api/labs/<lab_id>` (5.7).
**Seletor de Trilha (`lab.js`, 11.2, 11.3, 11.5, 11.6):**
- Em steps `task`, o frontend exibe abas `Console | CLI` na mesma tela, acima das instruções.
- A aba inicial é `preferences.path` de `GET /api/progress`. Se o step não oferece essa Trilha, abre a outra disponível sem alterar a preferência.
- Ao clicar em uma aba, o frontend chama `GET /api/labs/<lab_id>/steps/<step_id>/content?path=<trilha>` via `fetch`, substitui o bloco de instruções sem recarregar a página e envia `PUT /api/progress` com `{"preferences": {"path": "<trilha>"}}`. O resultado de validação já exibido, o contador de tentativas e o botão "Validar" permanecem como estão.
- Uma Trilha presente em `unavailable_paths` aparece como aba desabilitada (`aria-disabled="true"`), com o motivo visível no próprio rótulo ou em tooltip e no texto da área de conteúdo.
- O botão "Dica detalhada" (exibido conforme `show_hint_button`) busca `.../hint?path=<trilha ativa>`. Trocar de aba com a dica aberta recarrega a dica da nova Trilha.
- `api.js` centraliza as chamadas `fetch`: em `POST`, `PUT` e `DELETE` envia `Content-Type: application/json` e `X-Workshop-Request: 1` (13.3). Nenhum módulo chama `fetch` diretamente para rotas que alteram estado.
- `session.js` exibe o cronômetro no cabeçalho, consulta `GET /api/session` na carga e a cada 60 s e, entre as consultas, decrementa localmente `seconds_remaining` a cada segundo. Com `status == "expiring"` mostra aviso visível. Com `expired` desabilita Validar, Deploy e Teardown, explica o motivo e mostra `python start.py --refresh` com botão de copiar (12.4, 12.5). O servidor continua sendo a autoridade: ele recusa as rotas AWS mesmo se o frontend for contornado (12.6).
- Os arquivos Markdown de conteúdo são convertidos em HTML no cliente por um renderizador local, sem CDN (8.2). Blocos de código da Trilha CLI têm botão de copiar.

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

**Dockerfile (serviço `workshop`):**

```dockerfile
# Fixada por digest (14.4); o digest real e definido na implementacao
FROM python:3.11-slim@sha256:<digest>

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Usuario nao root (14.1); o diretorio de progresso pertence a ele
RUN groupadd --gid 10001 workshop \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin workshop \
 && mkdir -p /app/progress && chown workshop:workshop /app/progress

COPY app/ ./app/
COPY labs/ ./labs/

USER 10001:10001

# Volume externo (nao copiado na imagem)
# ./progress/ -> /app/progress/
# Nenhuma credencial entra na imagem nem por volume: elas chegam por variaveis de ambiente.

EXPOSE 5000

# python:3.11-slim nao inclui curl; o healthcheck usa a biblioteca padrao
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:5000/health', timeout=3)" || exit 1

# Dentro do container o bind e 0.0.0.0; a restricao a localhost e feita
# na publicacao de porta do gateway (127.0.0.1:...).
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--worker-tmp-dir", "/tmp", "app.server:app"]
```

**docker-compose.yml** (sem a chave `version`, obsoleta no Compose v2):

```yaml
services:
  workshop:
    build: .
    # Sem "ports:". Conectado somente a rede internal.
    networks:
      - workshop-internal
    user: "${WORKSHOP_UID:-10001}:${WORKSHOP_GID:-10001}"
    read_only: true
    tmpfs:
      - /tmp
    cap_drop: [ALL]
    security_opt:
      - no-new-privileges:true
    mem_limit: 512m
    pids_limit: 128
    volumes:
      - "./progress:/app/progress"     # unico volume; nenhum caminho de credenciais
    environment:
      - FLASK_ENV=production
      - WORKSHOP_PORT=${WORKSHOP_PORT:-5000}
      - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
      # Credenciais temporarias: pass-through do ambiente do processo do start.py
      - AWS_ACCESS_KEY_ID
      - AWS_SECRET_ACCESS_KEY
      - AWS_SESSION_TOKEN
      - WORKSHOP_CREDENTIALS_EXPIRATION
      # Nada de ~/.aws, profile ou metadata service no container
      - AWS_SHARED_CREDENTIALS_FILE=/dev/null
      - AWS_CONFIG_FILE=/dev/null
      - AWS_EC2_METADATA_DISABLED=true
      - HTTPS_PROXY=http://gateway:3128
      - HTTP_PROXY=http://gateway:3128
      - NO_PROXY=localhost,127.0.0.1,gateway
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; urllib.request.urlopen('http://localhost:5000/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: on-failure:3

  gateway:
    image: ubuntu/squid:<tag-fixada>@sha256:<digest>   # tag e digest explicitos, nunca "latest" (14.4)
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
      - /var/log/squid
      - /var/spool/squid
    cap_drop: [ALL]
    cap_add: [CHOWN, SETUID, SETGID]   # minimo para o Squid trocar para o usuario proxy; confirmar na implementacao
    security_opt:
      - no-new-privileges:true
    mem_limit: 256m
    pids_limit: 128
    depends_on:
      workshop:
        condition: service_healthy
    networks:
      - workshop-internal
      - egress
    ports:
      - "127.0.0.1:${WORKSHOP_PORT:-5000}:8080"   # unica porta publicada, so loopback
    volumes:
      - "./gateway/squid.conf:/etc/squid/squid.conf:ro"
      - "./gateway/allowlist.txt:/etc/squid/allowlist.txt:ro"
    restart: on-failure:3

networks:
  workshop-internal:
    internal: true
  egress:
    driver: bridge
```

O boto3 respeita `HTTPS_PROXY`, `HTTP_PROXY` e `NO_PROXY`, então nenhuma alteração de código é necessária para direcionar o tráfego AWS ao Squid.

**gateway/squid.conf** (versionado, dois papéis em um arquivo):

```
# Reverse proxy (accel): entrada do browser -> Flask
# vhost: repassa ao Flask o Host original do browser (127.0.0.1:<porta>), que o Flask valida (13.1)
http_port 8080 accel vhost defaultsite=workshop
cache_peer workshop parent 5000 0 no-query originserver name=app
acl reverse_listener localport 8080
cache_peer_access app allow reverse_listener

# Forward proxy: saida do workshop -> AWS, somente CONNECT 443 para a allowlist
http_port 3128
acl allowed_domains dstdomain "/etc/squid/allowlist.txt"
acl SSL_ports port 443
acl CONNECT method CONNECT
acl from_internal src 172.16.0.0/12 10.0.0.0/8 192.168.0.0/16

http_access allow CONNECT SSL_ports allowed_domains from_internal
http_access allow reverse_listener
http_access deny all

# Log de acesso: horario e destino. Squid nao registra cabecalhos de
# autenticacao e nao enxerga o corpo de CONNECT (TLS fim a fim).
access_log stdio:/var/log/squid/access.log squid
```

**gateway/allowlist.txt:**

```
.amazonaws.com
.api.aws
```

**Observações:**
- O `http_port 8080` usa `vhost` para repassar ao Flask o `Host` do browser (`127.0.0.1:<porta>`), necessário para a validação de `Host` (13.1). Como o domínio de destino passa a ser o `Host` do browser, a ACL `reverse_site` por `dstdomain` é trocada por `reverse_listener` (`localport 8080`). A porta 8080 só é publicada em `127.0.0.1` (9.1).
- O formato `squid` do `access_log` registra horário, método, destino e código de resultado (por exemplo `TCP_DENIED/403` para destinos recusados). Não inclui cabeçalhos de autenticação (9.6).
- Em requisições `CONNECT` o tráfego TLS é fim a fim. O Squid só vê o host e a porta de destino, nunca o corpo nem os cabeçalhos `Authorization`.
- As faixas de `from_internal` na ACL devem ser conferidas na implementação contra a sub-rede real atribuída a `workshop-internal`.
- Restart: `on-failure:3` nos dois serviços limita as reinicializações automáticas (1.10).
- O `gateway` só inicia depois que o `workshop` está `healthy` (`condition: service_healthy`).
- Downloads do build (pull da imagem base, `pip install`) ocorrem em `docker compose build`, fora da restrição de runtime. O README deve documentar isso (9.7).

**Credenciais e profile (1.5, 1.12, 9.3):**
- O `AWS_PROFILE` (padrão `default`) é usado somente no host, por `check_requirements.py` e `start.py`. O container não recebe `AWS_PROFILE` nem `~/.aws`.
- O `start.py` exporta credenciais temporárias do profile e as passa ao `workshop` por variáveis de ambiente (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` e `WORKSHOP_CREDENTIALS_EXPIRATION`). O Compose declara as quatro em modo pass-through, sem valor no arquivo, e não há arquivo `.env` temporário. O container ignora arquivos de configuração (`AWS_SHARED_CREDENTIALS_FILE=/dev/null`, `AWS_CONFIG_FILE=/dev/null`) e o serviço de metadata (`AWS_EC2_METADATA_DISABLED=true`), de modo que o boto3 usa só as variáveis.
- A região vem de `AWS_DEFAULT_REGION` (padrão `us-east-1`).
- O container não precisa mais alcançar `portal.sso.*`: o risco de renovação de token com `~/.aws:ro` deixa de existir, porque o container nunca renova nada. Quando a sessão expira, o usuário renova o login no host e executa `python start.py --refresh`.
- Residual: as variáveis de ambiente ficam visíveis a quem tem acesso ao Docker do usuário (`docker inspect`). Isso está dentro da mesma fronteira de confiança do usuário local e é documentado no README. A mitigação é a sessão curta.
- As tasks 9.5 e 15C.3 (teste SSO com `~/.aws:ro`) ficam como histórico concluído. O teste `test_sso_readonly.py` é substituído por um teste que verifica que o container não tem `~/.aws` e só recebe as variáveis esperadas (task 15D.12).

**Arquivos de dependências:**
- `requirements.in`: `flask`, `gunicorn`, `boto3` (dependências diretas)
- `requirements.txt`: gerado a partir de `requirements.in` com hashes de todos os pacotes, instalado com `pip install --require-hashes` (14.5). A geração é reproduzível: `scripts/compile-requirements.sh` executa `pip-compile --generate-hashes` dentro da imagem `python:3.11-slim` fixada por digest, e o procedimento é descrito no `CONTRIBUTING.md`. O Dependabot atualiza `requirements.in`/`requirements.txt` e o CI roda `pip-audit`.
- `requirements-dev.txt`: `pytest`, `hypothesis`

**Estrutura de diretórios do repositório:**

```
.
├── start.py
├── check_requirements.py
├── host_credentials.py
├── docker-compose.yml
├── Dockerfile
├── requirements.in
├── requirements.txt
├── requirements-dev.txt
├── SECURITY.md
├── CONTRIBUTING.md
├── scripts/
│   ├── compile-requirements.sh
│   └── check_dco.py
├── .github/
│   ├── workflows/ci.yml
│   ├── workflows/codeql.yml
│   ├── dependabot.yml
│   ├── CODEOWNERS
│   └── pull_request_template.md
├── gateway/
│   ├── squid.conf
│   └── allowlist.txt
├── app/
│   ├── server.py
│   ├── http_security.py   # Host, Origin, cabecalho proprio e cabecalhos de seguranca
│   ├── session.py         # estado da sessao e guarda SESSION_EXPIRED
│   ├── validators/
│   └── static/
├── labs/
│   └── lab-XX/
├── progress/
│   └── .gitkeep          # progress.json fica no .gitignore
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── js/
│   └── security/          # testes de seguranca (CODEOWNERS)
├── README.md
└── LICENSE
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
      "services": ["Amazon S3"],
      "total_steps": 5,
      "completed_steps": 3,
      "status": "in_progress"
    }
  ]
}
```

**GET /api/labs/{lab_id}**

Para cada step `task`, `paths` lista as Trilhas disponíveis e `unavailable_paths` os motivos das indisponíveis. Steps de outros tipos não trazem esses campos. A resposta inclui `dea_domains` e `services` do lab, usados pela tela de conclusão (5.7).

```json
{
  "lab_id": "lab-01",
  "title": "Fundamentos de S3 e Data Lake",
  "dea_domains": ["D2"],
  "services": ["Amazon S3"],
  "steps": [
    {
      "step_id": "step-02",
      "title": "Criar bucket S3 para o Data Lake",
      "type": "task",
      "hint_threshold": 3,
      "paths": ["console", "cli"],
      "unavailable_paths": {}
    },
    {
      "step_id": "step-04",
      "title": "Explorar o painel de Lake Formation",
      "type": "task",
      "hint_threshold": 3,
      "paths": ["console"],
      "unavailable_paths": {
        "cli": "Esta tarefa depende de uma visualização interativa que não existe na API."
      }
    }
  ]
}
```

**GET /api/labs/{lab_id}/steps/{step_id}/content?path=cli**

```json
{
  "lab_id": "lab-01",
  "step_id": "step-02",
  "path": "cli",
  "markdown": "<conteúdo de scenario.md>\n\n---\n\n<conteúdo de cli.md>"
}
```

**GET /api/labs/{lab_id}/steps/{step_id}/hint?path=cli**

```json
{
  "lab_id": "lab-01",
  "step_id": "step-02",
  "path": "cli",
  "hint": "<conteúdo de hint-cli.md>"
}
```

**POST /api/labs/{lab_id}/steps/{step_id}/visit**

Sem corpo. Resposta (step não `task`):

```json
{
  "lab_id": "lab-01",
  "step_id": "step-01",
  "step_status": "passed",
  "attempt_count": 0,
  "lab_status": "in_progress",
  "resume_step": "step-02"
}
```

Para step `task`, a resposta é o erro `STEP_REQUIRES_VALIDATION` (409).

**POST /api/validate/{lab_id}/{step_id}**

A resposta e o resultado não dependem da Trilha. Um campo `path` eventual no corpo é ignorado (11.4).

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

**GET /api/session**

```json
{
  "expires_at": "2025-01-01T12:00:00Z",
  "seconds_remaining": 1840,
  "status": "valid"
}
```

`status` é `valid`, `expiring` (600 s ou menos) ou `expired`. Nunca contém valores de credenciais. Com a variável ausente ou inválida, retorna `expires_at: null`, `seconds_remaining: 0` e `status: "expired"`.

### Error Response Schema

Todos os erros da API seguem o formato:

```json
{
  "error": true,
  "code": "CREDENTIALS_EXPIRED",
  "message": "ExpiredToken: The security token included in the request is expired. Verifique as credenciais AWS do profile em uso.",
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
| `INVALID_PATH` | 400 | `path` ausente ou diferente de `console`/`cli` |
| `PATH_UNAVAILABLE` | 409 | Trilha válida, mas ausente de `paths` do step; a mensagem traz o motivo de `unavailable_paths` |
| `STEP_REQUIRES_VALIDATION` | 409 | `POST .../visit` em step do tipo `task`; esse step só passa por validação |
| `STACK_NOT_FOUND` | 404 | Stack CloudFormation não existe |
| `STACK_DEPLOY_FAILED` | 422 | Deploy CloudFormation falhou |
| `SESSION_EXPIRED` | 401 | Sessão expirada: rota que chama a AWS recusada antes de qualquer chamada. A mensagem traz o comando `python start.py --refresh` |
| `HOST_NOT_ALLOWED` | 421 | Cabeçalho `Host` fora da allowlist (13.1) |
| `ORIGIN_NOT_ALLOWED` | 403 | `Origin` ausente ou diferente da origem da plataforma em `POST`/`PUT`/`DELETE` (13.2) |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | `Content-Type` diferente de `application/json` em `POST`/`PUT`/`DELETE` (13.2) |
| `MISSING_WORKSHOP_HEADER` | 403 | Falta `X-Workshop-Request: 1` em `POST`/`PUT`/`DELETE` (13.2) |
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
    paths: Optional[list[str]] = None  # somente em task: "console" e/ou "cli"
    unavailable_paths: Optional[dict[str, str]] = None  # somente em task: trilha -> motivo

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
    services: list[str]  # obrigatório, não vazio: serviços AWS usados no lab (5.7)
    prerequisites: dict
    steps: list[StepMetadata]
    residual_resources: list[str]

class LabCatalog:
    """Singleton carregado na inicialização do Flask.
    Rejeita na carga metadata.json sem `services` ou com `services` vazio
    ou com itens que não sejam strings não vazias, além das regras de Trilha."""
    
    def __init__(self, labs_dir: str):
        self._labs: dict[str, LabMetadata] = {}
        self._load_all(labs_dir)
    
    def get_lab(self, lab_id: str) -> Optional[LabMetadata]:
        return self._labs.get(lab_id)

    def get_step_content(self, lab_id: str, step_id: str, path: str) -> str:
        """scenario.md + separador + <path>.md. Levanta InvalidPathError ou
        PathUnavailableError (com o motivo de unavailable_paths)."""

    def get_step_hint(self, lab_id: str, step_id: str, path: str) -> str:
        """Conteúdo de hint-<path>.md, com as mesmas regras de erro."""
    
    def get_all_labs(self) -> list[LabMetadata]:
        return sorted(self._labs.values(), key=lambda l: l.lab_id)
```

### ProgressStore

```python
class ProgressStore:
    """Gerenciador do progress.json, seguro entre threads e entre os 2 workers do gunicorn."""
    
    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = threading.Lock()   # entre threads
        # entre processos: fcntl.flock em arquivo de lock + escrita via os.replace
    
    def get_progress(self) -> dict:
        """Retorna o progresso completo."""
    
    def get_lab_progress(self, lab_id: str) -> dict:
        """Retorna o progresso de um lab específico."""

    def get_preferred_path(self) -> str:
        """Retorna preferences.path; 'console' se ausente."""

    def set_preferred_path(self, path: str) -> None:
        """Valida (console|cli, senão InvalidPathError) e grava somente
        preferences.path e last_updated. Não toca em status nem attempts (11.2, 11.3)."""
    
    def update_step(self, lab_id: str, step_id: str, 
                    status: str, increment_attempts: bool = True) -> None:
        """Atualiza status e tentativas de um step atomicamente."""
    
    def mark_visited(self, lab_id: str, step_id: str,
                     lab_metadata: LabMetadata) -> None:
        """Marca um step que não é `task` como `passed` (com passed_at) sem
        incrementar attempts. Levanta StepRequiresValidationError para `task`
        e LabNotFoundError (`LAB_NOT_FOUND` ou `STEP_NOT_FOUND`) para ids inválidos. Idempotente:
        não altera passed_at de um step já `passed`. Não altera steps `task` (2.6)."""

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
                 progress_store: ProgressStore,
                 validator_loader: Optional[Callable[[], dict]] = None):
        self._catalog = lab_catalog
        self._progress = progress_store
        # validator_loader injetável (create_app o repassa); padrão: app/validators/
        self._validators = (validator_loader or self._load_validators)()
    
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

class InvalidPathError(WorkshopError):
    """Trilha diferente de console/cli."""
    code = "INVALID_PATH"
    http_status = 400

class PathUnavailableError(WorkshopError):
    """Trilha ausente de paths do step; a mensagem traz o motivo."""
    code = "PATH_UNAVAILABLE"
    http_status = 409

class StepRequiresValidationError(WorkshopError):
    """Visita registrada em step task; ele só passa por validação."""
    code = "STEP_REQUIRES_VALIDATION"
    http_status = 409

class StackDeployError(WorkshopError):
    code = "STACK_DEPLOY_FAILED"
    http_status = 422

class SessionExpiredError(WorkshopError):
    """Sessão de credenciais temporárias expirada; rotas AWS são recusadas."""
    code = "SESSION_EXPIRED"
    http_status = 401

class HostNotAllowedError(WorkshopError):
    code = "HOST_NOT_ALLOWED"
    http_status = 421

class OriginNotAllowedError(WorkshopError):
    code = "ORIGIN_NOT_ALLOWED"
    http_status = 403

class UnsupportedMediaTypeError(WorkshopError):
    code = "UNSUPPORTED_MEDIA_TYPE"
    http_status = 415

class MissingWorkshopHeaderError(WorkshopError):
    code = "MISSING_WORKSHOP_HEADER"
    http_status = 403
```

Quando o erro for de credenciais, a mensagem retornada ao usuário acrescenta a sugestão de renovar o login no host e executar `python start.py --refresh` (5.6). A mensagem nunca inclui valores de credenciais. Antes de chegar ao validador, a guarda `require_active_session()` já recusa a chamada com `SESSION_EXPIRED` quando a sessão expirou localmente.

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
    # Nunca registrar os valores de os.environ, cabecalhos ou corpo da requisicao
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
from botocore.exceptions import (
    ClientError, NoCredentialsError, TokenRetrievalError, UnauthorizedSSOTokenError,
)

CREDENTIAL_ERROR_CODES = (
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidClientTokenId",
    "UnrecognizedClientException",
    "InvalidSignatureException",
)
CREDENTIAL_HINT = "Verifique as credenciais AWS do profile em uso."

def _credential_message(code: str, original: str) -> str:
    """Código e mensagem originais do erro AWS, sem alteração, mais a sugestão genérica."""
    return f"{code}: {original}. {CREDENTIAL_HINT}"

def _safe_validate(fn):
    """Decorator que converte exceções AWS em ValidationResult."""
    def wrapper(session, context):
        try:
            return fn(session, context)
        except (NoCredentialsError, UnauthorizedSSOTokenError, TokenRetrievalError) as e:
            # Não são ClientError: usa o nome da exceção como código e str(e) como mensagem.
            return ValidationResult(
                passed=False,
                message=_credential_message(type(e).__name__, str(e))
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in CREDENTIAL_ERROR_CODES:
                return ValidationResult(
                    passed=False,
                    message=_credential_message(code, e.response["Error"]["Message"])
                )
            return ValidationResult(
                passed=False,
                message=f"Erro AWS ({code}): {e.response['Error']['Message']}"
            )
    return wrapper
```

### Estratégia de Polling de Stack CloudFormation

O frontend chama `GET /api/stack-status/{lab_id}` a cada 5 segundos enquanto o status for `*_IN_PROGRESS`. O backend não mantém estado de polling: cada chamada executa `describe_stacks` diretamente.

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
- Porta publicada (Property 14): gerar valores de `WORKSHOP_PORT`, renderizar o compose (`docker compose config` ou parse do YAML com substituição de variáveis) e verificar que o binding é `127.0.0.1`
- Diagnóstico de timeout (Property 15): gerar saídas arbitrárias de `docker compose ps`/`logs` e estados de porta via mocks de `subprocess`/`urllib`/relógio, e verificar exit code 1 e conteúdo do diagnóstico
- Completude de conteúdo por Trilha (Property 16): percorrer o catálogo real e `metadata.json` gerados com `hypothesis` (combinações de `paths` e `unavailable_paths`) e verificar `scenario.md`, arquivos por Trilha e motivos não vazios
- Troca de Trilha (Property 17): gerar progressos válidos e sequências de `console`/`cli`, aplicar `set_preferred_path` e comparar `preferences.path` e os campos dos steps antes e depois
- Steps não-`task` visitados (Property 19): gerar labs com tipos de step mistos e progressos válidos, aplicar `mark_visited` em subconjuntos de steps não-`task` e comparar status e `attempts` dos steps `task` antes e depois, além do `get_resume_step`
- Sem credenciais na Trilha CLI (Property 18): varrer todos os `cli.md` do repositório e testar o detector (regex) com textos gerados que contêm ou não os padrões `AKIA`/`ASIA` + 16 caracteres, `aws_secret_access_key` e `aws_session_token`
- Matcher de allowlist (apoio à Property 13): função pura que espelha a regra `dstdomain` (`.amazonaws.com`, `.api.aws`), testada com domínios gerados, incluindo sufixos enganosos como `amazonaws.com.evil.example`

### Testes de Exemplo (Unit/Integration Tests)

Usados para cenários específicos, pontos de integração e edge cases:
- Dashboard exibe exatamente 10 labs com metadados corretos
- Disclaimer de custos aparece antes do primeiro step de tarefa
- Confirmação de teardown é exigida antes de deletar a stack
- Resposta de validação é JSON sem recarregar página
- `start.py` com `urlopen` mockado que responde na N-ésima tentativa: imprime a URL e chama `webbrowser.open` (1.4, 1.11)
- `start.py` com relógio e `sleep` injetados: o polling ocorre a cada 2 s e termina em 60 s (1.4)
- `GET /api/labs/<lab_id>` retorna `paths` e `unavailable_paths` por step `task` (11.1, 11.6)
- `GET .../content?path=console|cli` retorna `scenario.md` seguido do arquivo da Trilha; `path` inválido retorna `INVALID_PATH` e Trilha indisponível retorna `PATH_UNAVAILABLE` com o motivo (11.1, 11.6)
- `GET .../hint?path=cli` retorna `hint-cli.md` e `path=console` retorna `hint-console.md` (11.5)
- `POST /api/validate` com `path` no corpo: o validador recebe um `context` sem `path` e o resultado é idêntico para `console` e `cli` (11.4)
- `progress.json` sem `preferences` é lido como `console`; `PUT /api/progress` com `preferences.path` inválido retorna `INVALID_PATH` (11.3)
- `POST /api/labs/<lab_id>/steps/<step_id>/visit`: step `info`/`deploy`/`teardown`/`completion` vira `passed` com `attempt_count` 0 e `resume_step` avança; repetir a chamada não altera `passed_at`; step `task` retorna `STEP_REQUIRES_VALIDATION` (409); ids inválidos retornam 404 (2.6)
- `create_app({... "validator_loader": fn})` usa o carregador injetado sem variável de ambiente (2.6, suporte aos testes)
- `metadata.json` sem `services`, com `services` vazio ou com item não string/vazio é rejeitado na carga do `LabCatalog`; `GET /api/labs` e `GET /api/labs/<lab_id>` retornam `services` (5.7)
- Frontend (teste de DOM): ao avançar de um step não-`task`, `lab.js` chama a rota `visit`; a navegação direta usa o status do servidor e não há uso de `sessionStorage`; a tela de conclusão lista `services` e `dea_domains` (2.6, 3.2, 5.7)
- Frontend (teste de DOM): aba de Trilha indisponível fica desabilitada e exibe o motivo; clicar em uma aba carrega o conteúdo via `fetch` sem recarregar a página e mantém o resultado da última validação (11.2, 11.6)
- `host_credentials.export_credentials` com `subprocess` mockado: JSON completo vira `TempCredentials`; ausência de `SessionToken` ou de `Expiration` levanta `LongLivedCredentialsError`; comando com falha ou saída inválida levanta `CredentialsExportError`; nenhuma mensagem de erro nem `repr` contém valores de credenciais (1.5, 1.14)
- `start.py` com `run` injetado: o ambiente passado ao `docker compose up` contém as quatro variáveis e nenhum arquivo é criado; `--refresh` executa exatamente `docker compose up -d --force-recreate --no-deps workshop`; nada é impresso com valores de credenciais; credenciais de longa duração interrompem com código 1 antes de qualquer `docker compose` (1.5, 1.14, 1.15)
- `GET /api/session` com relógio injetado: `valid` acima de 600 s, `expiring` de 1 a 600 s, `expired` em 0 ou menos, variável ausente ou inválida; resposta sem valores de credenciais (12.1, 12.2, 12.3)
- Cabeçalhos de segurança presentes em respostas 200, 4xx e 5xx; `GET /health` responde com qualquer `Host`; `POST` com `Origin` ausente, `Origin` de outro domínio, `Content-Type` diferente de JSON ou sem `X-Workshop-Request` é recusado e não altera o progresso (13.1, 13.2, 13.4)
- Frontend (teste de DOM): `api.js` envia `X-Workshop-Request: 1` e `Content-Type: application/json` em `POST`/`PUT`; `session.js` exibe o aviso em `expiring`, bloqueia Validar, Deploy e Teardown em `expired` e mostra o comando `python start.py --refresh` (12.4, 12.5, 13.3)
- `check_requirements.py` com `subprocess` mockado: Docker 18 reprovado, daemon parado, Compose v1 reprovado, AWS CLI 1.x reprovado, `sts` com erro, porta ocupada (1.2, 1.3)

### Testes de Segurança (`tests/security/`)

Os testes de segurança ficam em `tests/security/`, coberta pelo CODEOWNERS. Esta pasta reúne os testes de smoke de configuração (compose, Dockerfile, requirements, workflows), os testes de propriedade 13, 14, 20, 21 e 22, o teste do matcher de allowlist e os testes de integração com Docker (egress e ambiente do container). Os testes que precisam de Docker são ignorados quando o Docker não está disponível.

- Property 20 (credenciais nunca expostas): gerar valores de credenciais (`AKIA`/`ASIA` + 16 caracteres, secrets e tokens aleatórios), injetá-los no ambiente da aplicação, exercitar todas as rotas e erros (inclusive exceções forçadas) e verificar que nenhum corpo de resposta, cabeçalho, nem registro capturado de log contém os valores
- Property 21 (sessão expirada bloqueia rotas AWS): gerar instantes de expiração e relógios e verificar a classificação de `status` e que as rotas AWS retornam `SESSION_EXPIRED` sem criar cliente boto3
- Property 22 (requisições inválidas recusadas): gerar combinações de `Host`, `Origin`, `Content-Type` e cabeçalho próprio em rotas de `POST`/`PUT`/`DELETE` e verificar que só a combinação totalmente válida é aceita e que as recusadas não alteram o `progress.json`

### Testes de Smoke

Verificações estáticas de configuração executadas uma vez:
- `docker-compose.yml` não monta `~/.aws`, `~/.ssh`, `~/.config`, `~/.docker` nem o socket do Docker (9.3, 14.6); o `workshop` só recebe as variáveis esperadas (as quatro de credenciais, `AWS_SHARED_CREDENTIALS_FILE=/dev/null`, `AWS_CONFIG_FILE=/dev/null`, `AWS_EC2_METADATA_DISABLED=true`, `AWS_DEFAULT_REGION`, `WORKSHOP_PORT`, `FLASK_ENV` e as de proxy) e não recebe `AWS_PROFILE`
- `progress.json` está no `.gitignore`
- 10 arquivos `cloudformation/stack.yaml` existem com sintaxe YAML válida
- O serviço `workshop` não tem `ports:` e está somente na rede `workshop-internal` com `internal: true` (9.5)
- Somente o serviço `gateway` publica porta, no formato `127.0.0.1:${WORKSHOP_PORT:-5000}:8080` (9.1, 1.9)
- Ambos os serviços têm `restart: on-failure:3` (1.10)
- `gateway` tem `depends_on` do `workshop` com `condition: service_healthy`
- O compose não contém a chave `version` e a imagem do gateway tem tag fixada, diferente de `latest`
- O healthcheck não usa `curl`
- `check_requirements.py` e `start.py` usam `--profile` (1.12) e o compose não repassa `AWS_PROFILE` ao `workshop`
- `gateway/squid.conf` termina em `http_access deny all` e `gateway/allowlist.txt` contém `.amazonaws.com` e `.api.aws` (9.5)
- O README documenta que downloads do build ocorrem fora da restrição de runtime e que o Squid não registra cabeçalhos de autenticação (9.6, 9.7)
- `requirements.txt` contém flask, gunicorn e boto3 com hashes (`--hash=sha256:`) em todas as entradas e o Dockerfile instala com `--require-hashes` (14.5); `requirements-dev.txt` contém pytest e hypothesis
- Dockerfile define `USER` não root; o compose define `read_only: true`, `tmpfs` em `/tmp`, `cap_drop: [ALL]`, `no-new-privileges:true`, `mem_limit` e `pids_limit` nos dois serviços (14.1, 14.3)
- As imagens `python:3.11-slim` e `ubuntu/squid` estão fixadas por `@sha256:` (14.4)
- Workflows em `.github/workflows/`: sem `pull_request_target`, `permissions` no topo restritas a `contents: read` (`security-events: write` só no job do CodeQL), todas as actions de terceiros fixadas por SHA de 40 caracteres e nenhuma referência a `secrets.` (15.1, 15.2, 15.4)
- `.github/CODEOWNERS` cobre os caminhos sensíveis com `@CaeirOps`; `dependabot.yml` cobre `pip`, `docker` e `github-actions` com frequência semanal (15.5, 15.6)
- `SECURITY.md`, `CONTRIBUTING.md` e `.github/pull_request_template.md` existem; o README não contém instruções de configuração administrativa do GitHub (16.1, 16.2, 16.3)
- Todo `cli.md` usa `--profile "$AWS_PROFILE"` e `--region "$AWS_REGION"` (ou placeholders `<...>`) e todo `console.md` contém um caminho de navegação `Serviço > Menu > Botão` (11.7, 11.8; verificação de presença, o conteúdo editorial é revisado manualmente)

### Testes de Integração de Rede (egress)

Executados com a stack no ar (`docker compose up -d --build`), com poucos exemplos representativos, porque o comportamento é de infraestrutura e não varia com o input:
- A partir do container `workshop`, uma requisição HTTPS via proxy a um domínio permitido (por exemplo `https://sts.amazonaws.com`) é aceita pelo Squid. A resposta HTTP da AWS pode ter qualquer status; o que importa é o `CONNECT` ter sido aceito.
- A partir do container `workshop`, uma requisição a um domínio fora da allowlist (por exemplo `https://example.com`) falha, e o `access.log` do gateway registra destino e horário, sem cabeçalhos de autenticação.
- A partir do container `workshop`, uma conexão direta sem proxy a um IP público falha, porque a rede é `internal`.
- A partir do host, `http://127.0.0.1:${WORKSHOP_PORT}/health` responde 200, e o serviço não é alcançável pelo IP não-loopback do host.
- O container `workshop` em execução não tem `~/.aws` (nem qualquer caminho de credenciais do host), roda com usuário não root, sistema de arquivos `read_only` com `/tmp` e `./progress` graváveis, e o ambiente contém exatamente as variáveis esperadas (9.3, 14.1, 14.6).
- `Host` do browser chega ao Flask como `127.0.0.1:<porta>` pelo gateway; `Host: evil.example` pelo gateway recebe 421; `POST` sem `Origin` recebe 403 (13.1, 13.2, 13.5).

### Verificação de ambiente com Docker e AWS real (somente leitura)

Executada uma vez, antes do primeiro lab real (tarefas 15C), com Docker instalado e um profile SSO válido (`AWS_PROFILE=Caeiro-Admin`). Nenhuma etapa cria recurso AWS nem faz deploy de stack; só chamadas de leitura.
- `docker compose config`, `docker compose build` e `squid -k parse` executado com a imagem fixada do gateway sobre `gateway/squid.conf`
- CIDR da ACL `from_internal` conferido com `docker network inspect` da rede `workshop-internal`; `squid.conf` ajustado se o CIDR não cobrir a sub-rede real
- `python check_requirements.py` com `AWS_PROFILE=Caeiro-Admin` e `WORKSHOP_PORT` livre
- `python start.py` sobe a plataforma, `http://127.0.0.1:${WORKSHOP_PORT}/health` responde pelo gateway e `docker compose down` encerra a stack ao final
- Testes de integração de egress (`WORKSHOP_EGRESS_TEST=1`) e de SSO com `~/.aws:ro` (`WORKSHOP_SSO_TEST_PROFILE=Caeiro-Admin`), com o resultado registrado na seção "Credenciais SSO" do README
- Chamada real somente leitura dentro do container `workshop` (`sts:GetCallerIdentity` via boto3), passando pelo proxy do gateway

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

*Para qualquer* combinação de pré-requisitos ausentes ou inválidos (Docker abaixo da versão mínima ou daemon parado, Docker Compose v1, AWS CLI ausente ou abaixo da versão 2, `aws sts get-caller-identity` com falha, porta `WORKSHOP_PORT` ocupada), o `check_requirements.py` deve retornar exit code não-zero e exibir uma mensagem identificando especificamente qual pré-requisito está faltante.

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

*Para qualquer* validador de qualquer lab, quando `validate_step` é chamado com uma sessão boto3 que lança `ClientError` ou `NoCredentialsError`, a função deve retornar `ValidationResult(passed=False)` com mensagem não-vazia, sem propagar a exceção. Quando a exceção é `NoCredentialsError` ou um erro de credencial (`ClientError` com código em `ExpiredToken`, `ExpiredTokenException`, `InvalidClientTokenId`, `UnrecognizedClientException`, `InvalidSignatureException`, ou `UnauthorizedSSOTokenError`/`TokenRetrievalError`), a mensagem deve conter o código de erro original e a sugestão "Verifique as credenciais AWS do profile em uso. e a orientação de renovar o login no host e executar `python start.py --refresh`, sem valores de credenciais.

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

---

### Property 13: Saída restrita à Allowlist

*Para qualquer* domínio de destino fora da Allowlist, uma tentativa de conexão de saída a partir do container `workshop` deve falhar e ser registrada no log do Gateway com destino e horário. *Para qualquer* domínio da Allowlist (`.amazonaws.com`, `.api.aws`) na porta 443, a conexão via proxy deve ser aceita. A verificação em rede real usa poucos exemplos representativos (teste de integração). A regra de correspondência de domínio é verificada como propriedade em uma função pura que espelha o `dstdomain` do Squid.

**Validates: Requirements 9.5, 9.6**

---

### Property 14: Porta publicada somente em loopback

*Para qualquer* valor válido de `WORKSHOP_PORT` (inclusive ausente, que resulta em 5000), a configuração renderizada do Compose deve publicar exatamente uma porta, no serviço `gateway`, vinculada a `127.0.0.1` e nunca a `0.0.0.0` ou a endereço não especificado, e o serviço `workshop` não deve publicar nenhuma porta.

**Validates: Requirements 9.1, 1.9**

---

### Property 15: Timeout de health gera diagnóstico completo e falha

*Para quaisquer* saídas de `docker compose ps` e `docker compose logs`, e qualquer estado de ocupação da porta, se `/health` não responder com sucesso em 60 s, o `start.py` deve terminar com código de saída diferente de zero, e o diagnóstico impresso deve conter o estado dos containers, as últimas 50 linhas de log, o resultado da verificação de porta e o comando `docker compose down`, sem executar `docker compose down` por conta própria.

**Validates: Requirements 1.8**

---

### Property 16: Conteúdo completo por Trilha em todo step task

*Para qualquer* step do tipo `task` de qualquer lab, o diretório `labs/<lab_id>/steps/<step_id>/` deve conter `scenario.md`; para cada Trilha em `paths`, devem existir o arquivo de instruções (`console.md` ou `cli.md`) e o de dica (`hint-console.md` ou `hint-cli.md`), não vazios; e para cada Trilha (`console`, `cli`) ausente de `paths`, `unavailable_paths` deve conter essa Trilha com motivo não vazio. `paths` nunca é vazio.

**Validates: Requirements 11.1, 11.5, 11.6**

---

### Property 17: Troca de Trilha só altera a preferência

*Para qualquer* progresso válido e qualquer sequência não vazia de trocas de Trilha (`console` ou `cli`), após aplicar a sequência `preferences.path` deve ser igual à última Trilha escolhida, e `status`, `attempts`, `last_attempt_at` e `passed_at` de todos os steps de todos os labs devem permanecer idênticos aos de antes.

**Validates: Requirements 11.2, 11.3**

---

### Property 18: Trilha CLI não contém credenciais

*Para qualquer* arquivo `cli.md` (ou `hint-cli.md`) do repositório, o texto não deve conter `AKIA` ou `ASIA` seguidos de 16 caracteres alfanuméricos maiúsculos, nem as strings `aws_secret_access_key` e `aws_session_token` (sem diferenciar maiúsculas de minúsculas). *Para qualquer* texto gerado que contenha um desses padrões, o detector deve sinalizá-lo, e *para qualquer* texto gerado sem eles, não deve sinalizar.

**Validates: Requirements 11.7, 9.3**

---

### Property 19: Marcar steps não-task não altera os steps task e avança a retomada

*Para qualquer* lab com steps de tipos mistos e qualquer progresso válido, aplicar `mark_visited` a qualquer subconjunto de steps que não são `task` deve (a) manter inalterados `status`, `attempts`, `last_attempt_at` e `passed_at` de todos os steps `task`, (b) deixar `attempts` dos steps marcados em 0, com `status == "passed"`, e (c) fazer `get_resume_step` retornar o primeiro step, pela ordem de `metadata.json`, cujo status não é `"passed"`. `_compute_lab_status` só retorna `"completed"` quando todos os steps `task` estão `passed`, independentemente dos steps não-task marcados. Chamar `mark_visited` em um step `task` levanta `StepRequiresValidationError` e não altera o progresso.

**Validates: Requirements 2.4, 2.6, 3.2**

---

### Property 20: Credenciais nunca aparecem em respostas nem em logs

*Para qualquer* valor de `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN` presente no ambiente da aplicação e *para qualquer* rota da API (inclusive `GET /api/session`, respostas de erro e erros inesperados forçados), nenhum corpo de resposta, cabeçalho de resposta ou registro de log da aplicação contém esses valores. No host, nenhuma mensagem de `start.py`, `check_requirements.py` ou `host_credentials.py` (saída padrão, erro padrão e `repr` de `TempCredentials`) contém esses valores, e nenhum arquivo é criado em disco durante o fluxo.

**Validates: Requirements 1.5, 5.6, 9.3, 12.1**

---

### Property 21: Sessão expirada bloqueia as rotas que chamam a AWS

*Para qualquer* valor de `WORKSHOP_CREDENTIALS_EXPIRATION` (instantes passados, futuros, ausente ou inválido) e *para qualquer* instante atual, `status` é `expired` se e somente se `seconds_remaining <= 0` ou a variável é ausente ou inválida; `expiring` se e somente se `1 <= seconds_remaining <= 600`; e `valid` caso contrário. Quando `status == "expired"`, `POST /api/validate/<lab_id>/<step_id>`, `POST /api/deploy/<lab_id>`, `POST /api/teardown/<lab_id>` e `GET /api/stack-status/<lab_id>` retornam `SESSION_EXPIRED` (HTTP 401) sem criar nenhum cliente boto3 e sem alterar o `progress.json`.

**Validates: Requirements 12.2, 12.3, 12.6**

---

### Property 22: Requisições sem Host, Origin, Content-Type ou cabeçalho próprio válidos são recusadas

*Para qualquer* combinação de `Host`, `Origin`, `Content-Type` e `X-Workshop-Request` em uma requisição `POST`, `PUT` ou `DELETE` à API, a requisição só é aceita se `Host` for `127.0.0.1:<porta>` ou `localhost:<porta>`, `Origin` estiver presente e for `http://127.0.0.1:<porta>` ou `http://localhost:<porta>`, `Content-Type` for `application/json` e `X-Workshop-Request` for `1`. Qualquer outra combinação é recusada com o código de erro correspondente e não altera o estado (`progress.json` idêntico antes e depois). *Para qualquer* requisição `GET` com `Host` fora da allowlist, exceto `/health`, a resposta é 421. Todas as respostas incluem os cinco cabeçalhos de segurança.

**Validates: Requirements 13.1, 13.2, 13.4**
