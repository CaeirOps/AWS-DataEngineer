"""Validadores do Módulo 02 (Catálogo de dados).

Só fazem leituras na conta. Os nomes seguem o template
`labs/lab-02/cloudformation/stack.yaml`, calculados a partir da conta e da
Region da sessão:

    workshop-lab-02-dados-<conta>-<region>   (bucket)
    workshop-lab-02-anycompany               (database do Glue)
    workshop-lab-02-crawler-<region>         (role dos crawlers)
"""

from typing import Any, Optional

from botocore.exceptions import ClientError

from app.models import ValidationResult
from app.validators.base import _safe_validate, dispatch_step

STACK = "workshop-lab-02"
DATABASE = f"{STACK}-anycompany"
CRAWLER_PEDIDOS = f"{STACK}-pedidos"
CRAWLER_FONTES = f"{STACK}-fontes"
CONEXAO = f"{STACK}-banco"
CRAWLER_JDBC = f"{STACK}-banco"
PREFIXO_RAW = "raw_"
DATAS = ("2026-03-08", "2026-03-09", "2026-03-10")
NOVA_PARTICAO = "2026-03-11"
COLUNA_NOVA = "categoria"


class Names:
    """Nomes dos recursos do módulo na conta e Region da sessão."""

    def __init__(self, session: Any):
        self.region = session.region_name or "us-east-1"
        self.account = session.client("sts").get_caller_identity()["Account"]
        self.bucket = f"{STACK}-dados-{self.account}-{self.region}"
        self.role_arn = f"arn:aws:iam::{self.account}:role/{STACK}-crawler-{self.region}"


def _fail(message: str, hint: Optional[str] = None) -> ValidationResult:
    return ValidationResult(passed=False, message=message, hint=hint)


def _code(exc: ClientError) -> str:
    return exc.response.get("Error", {}).get("Code", "")


def _get_crawler(glue: Any, name: str) -> Optional[dict]:
    try:
        return glue.get_crawler(Name=name)["Crawler"]
    except ClientError as exc:
        if _code(exc) == "EntityNotFoundException":
            return None
        raise


def _get_table(glue: Any, name: str) -> Optional[dict]:
    try:
        return glue.get_table(DatabaseName=DATABASE, Name=name)["Table"]
    except ClientError as exc:
        if _code(exc) == "EntityNotFoundException":
            return None
        raise


def _tables(glue: Any) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for page in glue.get_paginator("get_tables").paginate(DatabaseName=DATABASE):
        for table in page.get("TableList", []):
            result[table["Name"]] = table
    return result


def _partitions(glue: Any, table: str) -> list[dict]:
    items: list[dict] = []
    for page in glue.get_paginator("get_partitions").paginate(DatabaseName=DATABASE, TableName=table):
        items.extend(page.get("Partitions", []))
    return items


def _s3_paths(crawler: dict) -> list[str]:
    return [t.get("Path", "") for t in (crawler.get("Targets") or {}).get("S3Targets", [])]


def _same_path(path: str, bucket: str, prefix: str) -> bool:
    """Compara o alvo S3 do crawler com `s3://<bucket>/<prefix>/`, ignorando a barra final."""
    return path.rstrip("/") == f"s3://{bucket}/{prefix}".rstrip("/")


def _ran_successfully(crawler: dict) -> bool:
    return (crawler.get("LastCrawl") or {}).get("Status") == "SUCCEEDED"


def _column_names(table: dict) -> list[str]:
    return [c["Name"] for c in (table.get("StorageDescriptor") or {}).get("Columns", [])]


def _crawler_role_ok(crawler: dict, names: Names) -> bool:
    role = crawler.get("Role", "")
    return role == names.role_arn or role.endswith(f"role/{STACK}-crawler-{names.region}")


# ----------------------------------------------------------------- step 04
@_safe_validate
def _validate_crawler_pedidos(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    glue = session.client("glue")
    crawler = _get_crawler(glue, CRAWLER_PEDIDOS)
    if crawler is None:
        return _fail(
            f"O crawler {CRAWLER_PEDIDOS} não existe na Region {names.region}.",
            f"O nome é exatamente {CRAWLER_PEDIDOS}. Confira também a Region do console ou da CLI.",
        )
    if crawler.get("DatabaseName") != DATABASE:
        return _fail(f"O crawler grava no database {crawler.get('DatabaseName')!r}, e não em {DATABASE}.")
    if not any(_same_path(p, names.bucket, "pedidos") for p in _s3_paths(crawler)):
        return _fail(
            "O alvo do crawler precisa ser o prefixo pedidos/ do bucket de dados.",
            f"Use s3://{names.bucket}/pedidos/ (o prefixo de pedidos, e não o bucket inteiro).",
        )
    if not _crawler_role_ok(crawler, names):
        return _fail(f"Use a role workshop-lab-02-crawler-{names.region}, criada pela stack.")
    if not _ran_successfully(crawler):
        status = (crawler.get("LastCrawl") or {}).get("Status")
        return _fail(
            "O crawler existe, mas ainda não terminou uma execução com sucesso."
            if status is None else f"A última execução do crawler terminou com status {status}.",
            "Execute o crawler (Run) e espere o estado voltar para READY. Se falhar, veja a mensagem de erro "
            "da última execução e os logs em /aws-glue/crawlers.",
        )
    table = _get_table(glue, "pedidos")
    if table is None:
        return _fail(
            "O crawler rodou, mas a tabela pedidos não apareceu no database.",
            "Sem prefixo de tabela, o nome da tabela é o nome da pasta. Confira o alvo do crawler.",
        )
    keys = [k["Name"] for k in table.get("PartitionKeys", [])]
    if keys != ["dt"]:
        return _fail(f"A tabela pedidos tem as chaves de partição {keys}, e esperava ['dt'].")
    found = sorted(p["Values"][0] for p in _partitions(glue, "pedidos") if p.get("Values"))
    missing = [d for d in DATAS if d not in found]
    if missing:
        return _fail("Faltam partições no catálogo: " + ", ".join(f"dt={d}" for d in missing) + ".")
    if "valor" not in _column_names(table):
        return _fail("A tabela pedidos não tem a coluna valor.")
    return ValidationResult(
        passed=True, message=f"Tabela pedidos criada com {len(found)} partições dt e as colunas descobertas."
    )


# ----------------------------------------------------------------- step 06
def _daily_schedule(schedule: Optional[dict]) -> bool:
    """Agenda ativa, que roda uma vez por dia (cron com hora fixa e dia-do-mês, mês e ano livres)."""
    if not schedule or schedule.get("State") != "SCHEDULED":
        return False
    parts = schedule.get("ScheduleExpression", "").replace("cron(", "").rstrip(")").split()
    if len(parts) != 6:
        return False
    minute, hour, dom, month, dow, year = parts
    return minute.isdigit() and hour.isdigit() and dom in ("*", "?") and month == "*" and dow in ("*", "?") and year == "*"


@_safe_validate
def _validate_crawler_fontes(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    glue = session.client("glue")
    crawler = _get_crawler(glue, CRAWLER_FONTES)
    if crawler is None:
        return _fail(f"O crawler {CRAWLER_FONTES} não existe na Region {names.region}.")
    if crawler.get("DatabaseName") != DATABASE:
        return _fail(f"O crawler grava no database {crawler.get('DatabaseName')!r}, e não em {DATABASE}.")
    paths = _s3_paths(crawler)
    absent = [p for p in ("pedidos", "clientes", "fornecedores") if not any(_same_path(x, names.bucket, p) for x in paths)]
    if absent:
        return _fail(
            "Faltam alvos no crawler: " + ", ".join(f"{p}/" for p in absent) + ".",
            "Adicione um alvo S3 para cada pasta: pedidos/, clientes/ e fornecedores/.",
        )
    if crawler.get("TablePrefix") != PREFIXO_RAW:
        return _fail(
            f"O prefixo de tabela deve ser {PREFIXO_RAW!r}, e está {crawler.get('TablePrefix')!r}.",
            "O campo se chama Table name prefix (console) ou TablePrefix (CLI).",
        )
    if not _daily_schedule(crawler.get("Schedule")):
        return _fail(
            "O crawler precisa de uma agenda ativa que rode uma vez por dia.",
            "Use uma expressão como cron(0 6 * * ? *). Lembre que o horário é em UTC.",
        )
    if not _ran_successfully(crawler):
        return _fail("Execute o crawler ao menos uma vez com sucesso (Run) e espere o estado READY.")
    tables = _tables(glue)
    esperadas = ("raw_pedidos", "raw_clientes", "raw_fornecedores")
    faltam = [t for t in esperadas if t not in tables]
    if faltam:
        return _fail("Faltam tabelas no catálogo: " + ", ".join(faltam) + ".")
    return ValidationResult(passed=True, message="Crawler agendado e tabelas raw_pedidos, raw_clientes e raw_fornecedores criadas.")


# ----------------------------------------------------------------- step 08
@_safe_validate
def _validate_particao(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    glue = session.client("glue")
    tabela = "pedidos"
    if _get_table(glue, tabela) is None:
        return _fail("A tabela pedidos ainda não existe. Conclua o step 04 primeiro.")
    s3 = session.client("s3")
    chave = f"pedidos/dt={NOVA_PARTICAO}/"
    if not s3.list_objects_v2(Bucket=names.bucket, Prefix=chave, MaxKeys=1).get("KeyCount"):
        return _fail(
            f"A pasta {chave} ainda não existe no bucket.",
            f"Copie pedidos/dt=2026-03-10/pedidos-2026-03-10.csv para {chave}pedidos-{NOVA_PARTICAO}.csv antes de registrar a partição.",
        )
    partitions = {p["Values"][0]: p for p in _partitions(glue, tabela) if p.get("Values")}
    partition = partitions.get(NOVA_PARTICAO)
    if partition is None:
        return _fail(
            f"A partição dt={NOVA_PARTICAO} ainda não está no catálogo.",
            "Registre com BatchCreatePartition (CLI), ALTER TABLE ADD PARTITION (Athena) ou, no console, com Add partition.",
        )
    local = (partition.get("StorageDescriptor") or {}).get("Location", "")
    if local.rstrip("/") != f"s3://{names.bucket}/{chave}".rstrip("/"):
        return _fail(
            f"A partição aponta para {local!r}, e deveria apontar para s3://{names.bucket}/{chave}.",
            "A localização é a pasta da partição, com o prefixo pedidos/dt=2026-03-11/.",
        )
    crawler = _get_crawler(glue, CRAWLER_PEDIDOS)
    if crawler is not None and not _ran_successfully(crawler):
        return _fail("O crawler dos pedidos precisa estar em um estado sem falha. Revise o step 04.")
    return ValidationResult(passed=True, message=f"Partição dt={NOVA_PARTICAO} registrada com a localização correta.")


# ----------------------------------------------------------------- step 11
@_safe_validate
def _validate_esquema(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    glue = session.client("glue")
    crawler = _get_crawler(glue, CRAWLER_FONTES)
    if crawler is None:
        return _fail("O crawler workshop-lab-02-fontes não existe. Conclua o step 06 primeiro.")
    policy = crawler.get("SchemaChangePolicy") or {}
    if policy.get("UpdateBehavior") != "UPDATE_IN_DATABASE":
        return _fail(
            f"UpdateBehavior está {policy.get('UpdateBehavior')!r}, e precisa ser UPDATE_IN_DATABASE.",
            "Com LOG, o crawler só registra a mudança e a tabela continua sem a coluna nova.",
        )
    if policy.get("DeleteBehavior") == "DELETE_FROM_DATABASE":
        return _fail(
            "DeleteBehavior está DELETE_FROM_DATABASE, que apaga tabelas do catálogo.",
            "Use LOG ou DEPRECATE_IN_DATABASE: aqui você só quer acrescentar a coluna, sem apagar nada.",
        )
    s3 = session.client("s3")
    if not s3.list_objects_v2(Bucket=names.bucket, Prefix="fornecedores/estoque-2026-03-10.csv", MaxKeys=1).get("KeyCount"):
        return _fail(
            "O arquivo do fornecedor com a coluna nova não foi enviado.",
            "Grave fornecedores/estoque-2026-03-10.csv com a coluna categoria no fim, como pede a prática.",
        )
    table = _get_table(glue, "raw_fornecedores")
    if table is None:
        return _fail("A tabela raw_fornecedores não existe. Conclua o step 06 primeiro.")
    columns = _column_names(table)
    if COLUNA_NOVA not in columns:
        return _fail(
            f"A tabela raw_fornecedores ainda não tem a coluna {COLUNA_NOVA}.",
            "Depois de ajustar a política, execute o crawler de novo e espere o estado READY.",
        )
    if columns[: len(columns) - 1] != ["sku", "descricao", "quantidade", "preco"]:
        return _fail(
            f"As colunas ficaram fora de ordem: {columns}.",
            f"A coluna {COLUNA_NOVA} deve ficar no fim: em CSV as colunas são lidas por posição.",
        )
    return ValidationResult(passed=True, message=f"Tabela raw_fornecedores atualizada com a coluna {COLUNA_NOVA}.")


# ----------------------------------------------------------------- step 13
@_safe_validate
def _validate_jdbc(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    glue = session.client("glue")
    try:
        connection = glue.get_connection(Name=CONEXAO, HidePassword=True)["Connection"]
    except ClientError as exc:
        if _code(exc) == "EntityNotFoundException":
            return _fail(f"A conexão {CONEXAO} não existe na Region {names.region}.")
        raise
    if connection.get("ConnectionType") != "JDBC":
        return _fail(f"A conexão é do tipo {connection.get('ConnectionType')!r}, e precisa ser JDBC.")
    properties = connection.get("ConnectionProperties") or {}
    if not str(properties.get("JDBC_CONNECTION_URL", "")).startswith("jdbc:"):
        return _fail("A conexão não tem uma URL JDBC válida (jdbc:...).")
    if "PASSWORD" in properties:
        return _fail(
            "A senha está escrita na conexão.",
            "Guarde as credenciais no AWS Secrets Manager e informe só o secret na conexão (SECRET_ID).",
        )
    if not properties.get("SECRET_ID"):
        return _fail("A conexão não referencia um secret do Secrets Manager (SECRET_ID).")
    if not (connection.get("PhysicalConnectionRequirements") or {}).get("SubnetId"):
        return _fail("A conexão precisa de uma subnet e de um security group (PhysicalConnectionRequirements).")
    crawler = _get_crawler(glue, CRAWLER_JDBC)
    if crawler is None:
        return _fail(f"O crawler {CRAWLER_JDBC} não existe.", "Crie um crawler com alvo JDBC que use a conexão.")
    alvos = (crawler.get("Targets") or {}).get("JdbcTargets", [])
    if not any(t.get("ConnectionName") == CONEXAO for t in alvos):
        return _fail(f"O crawler precisa de um alvo JDBC que use a conexão {CONEXAO}.")
    if not _ran_successfully(crawler):
        return _fail("Execute o crawler JDBC com sucesso. Se falhar, use Test connection na conexão.")
    tables = _tables(glue)
    jdbc = [n for n, t in tables.items() if str((t.get("Parameters") or {}).get("connectionName", "")) == CONEXAO
            or str((t.get("Parameters") or {}).get("classification", "")) in ("postgresql", "mysql")]
    if not jdbc:
        return _fail("O crawler rodou, mas nenhuma tabela do banco apareceu no catálogo.")
    return ValidationResult(passed=True, message=f"Conexão JDBC e {len(jdbc)} tabela(s) do banco no catálogo.")


STEP_VALIDATORS = {
    "step-04": _validate_crawler_pedidos,
    "step-06": _validate_crawler_fontes,
    "step-08": _validate_particao,
    "step-11": _validate_esquema,
    "step-13": _validate_jdbc,
}


def validate_step(boto3_session: Any, context: dict) -> ValidationResult:
    return dispatch_step(STEP_VALIDATORS, boto3_session, context)
