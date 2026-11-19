"""Validadores do Módulo 01 (S3 e data lake).

Só fazem leituras na conta. Os nomes seguem o template
`labs/lab-01/cloudformation/stack.yaml`, calculados a partir da conta e da
Region da sessão:

    workshop-lab-01-raw-<conta>-<region>
    workshop-lab-01-curated-<conta>-<region>
    workshop-lab-01-indexador
    workshop-lab-01-analista-<region>
"""

import json
from typing import Any, Iterable, Optional

from botocore.exceptions import ClientError

from app.models import ValidationResult
from app.validators.base import _safe_validate, dispatch_step

STACK = "workshop-lab-01"
DATAS = ("2026-03-08", "2026-03-09", "2026-03-10")
CLIENTES = ("cliente-0041", "cliente-0042", "cliente-0043")
CLIENTE_EXCLUIDO = "cliente-0042"
ACCESS_POINT = "analytics"
WRITE_ACTIONS = ("s3:*", "*", "s3:putobject", "s3:deleteobject", "s3:deleteobjectversion",
                 "s3:putobjectacl", "s3:put*", "s3:delete*")


class Names:
    """Nomes dos recursos do módulo na conta e Region da sessão."""

    def __init__(self, session: Any):
        self.region = session.region_name or "us-east-1"
        self.account = session.client("sts").get_caller_identity()["Account"]
        self.raw = f"{STACK}-raw-{self.account}-{self.region}"
        self.curated = f"{STACK}-curated-{self.account}-{self.region}"
        self.function = f"{STACK}-indexador"
        self.function_arn = f"arn:aws:lambda:{self.region}:{self.account}:function:{self.function}"
        self.analista_arn = f"arn:aws:iam::{self.account}:role/{STACK}-analista-{self.region}"


def _fail(message: str, hint: Optional[str] = None) -> ValidationResult:
    return ValidationResult(passed=False, message=message, hint=hint)


def _error_code(exc: ClientError) -> str:
    return exc.response.get("Error", {}).get("Code", "")


def _list_keys(s3: Any, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    return keys


def _missing_bucket(names: Names, exc: ClientError) -> Optional[ValidationResult]:
    if _error_code(exc) in ("NoSuchBucket", "404", "NotFound"):
        return _fail(
            f"Bucket do módulo não encontrado na Region {names.region}.",
            "Confira se o deploy do step 02 terminou e se você está na mesma Region do workshop.",
        )
    return None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


# ----------------------------------------------------------------- step 04
@_safe_validate
def _validate_organizar(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    s3 = session.client("s3")
    try:
        entrada = _list_keys(s3, names.raw, "entrada/")
    except ClientError as exc:
        return _missing_bucket(names, exc) or _fail(f"{_error_code(exc)}: {exc}")
    pedidos = _list_keys(s3, names.raw, "pedidos/")
    clientes = _list_keys(s3, names.raw, "clientes/")
    faltando = [
        d for d in DATAS
        if not any(k.startswith(f"pedidos/dt={d}/") and k.endswith(".csv") for k in pedidos)
    ]
    if faltando:
        return _fail(
            "Faltam os pedidos das datas: " + ", ".join(faltando) + ".",
            "Cada arquivo pedidos-AAAA-MM-DD.csv vai para pedidos/dt=AAAA-MM-DD/, com a data no nome da pasta.",
        )
    sem_cliente = [c for c in CLIENTES if f"clientes/{c}.json" not in clientes]
    # cliente-0042 pode já ter sido excluído no step 12.
    sem_cliente = [c for c in sem_cliente if c != CLIENTE_EXCLUIDO]
    if sem_cliente:
        return _fail(
            "Faltam em clientes/: " + ", ".join(f"{c}.json" for c in sem_cliente) + ".",
            "Os arquivos cliente-*.json vão para o prefixo clientes/, sem subpastas.",
        )
    if entrada:
        return _fail(
            f"O prefixo entrada/ ainda tem {len(entrada)} objeto(s).",
            "Use mover (Move no console, aws s3 mv na CLI) em vez de copiar, ou apague as cópias de entrada/.",
        )
    return ValidationResult(passed=True, message="Data lake organizado: pedidos particionados por dt e clientes separados.")


# ----------------------------------------------------------------- step 06
@_safe_validate
def _validate_versionamento(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    try:
        status = session.client("s3").get_bucket_versioning(Bucket=names.raw).get("Status")
    except ClientError as exc:
        return _missing_bucket(names, exc) or _fail(f"{_error_code(exc)}: {exc}")
    if status == "Enabled":
        return ValidationResult(passed=True, message=f"Versionamento ativado em {names.raw}.")
    if status == "Suspended":
        return _fail("O versionamento está suspenso.", "Suspenso não protege objetos novos. Ative de novo (Enable).")
    return _fail("O versionamento ainda não foi ativado no bucket raw.")


# ----------------------------------------------------------------- step 08
def _rule_prefix(rule: dict) -> Optional[str]:
    filtro = rule.get("Filter")
    if filtro is None:
        return rule.get("Prefix")
    if "Prefix" in filtro:
        return filtro["Prefix"]
    return (filtro.get("And") or {}).get("Prefix")


@_safe_validate
def _validate_lifecycle(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    try:
        rules = session.client("s3").get_bucket_lifecycle_configuration(Bucket=names.raw).get("Rules", [])
    except ClientError as exc:
        if _error_code(exc) == "NoSuchLifecycleConfiguration":
            return _fail("O bucket raw ainda não tem regra de Lifecycle.")
        return _missing_bucket(names, exc) or _fail(f"{_error_code(exc)}: {exc}")
    candidatas = [r for r in rules if r.get("Status") == "Enabled" and _rule_prefix(r) == "pedidos/"]
    if not candidatas:
        return _fail(
            "Nenhuma regra ativa com o filtro de prefixo pedidos/.",
            "O filtro é exatamente pedidos/ (com a barra no fim) e a regra precisa estar Enabled.",
        )
    problemas = []
    for rule in candidatas:
        problemas = []
        transicoes = {t.get("StorageClass"): t.get("Days") for t in rule.get("Transitions", [])}
        if transicoes.get("STANDARD_IA") != 30:
            problemas.append("transição para Standard-IA aos 30 dias")
        if transicoes.get("GLACIER_IR") != 90:
            problemas.append("transição para Glacier Instant Retrieval aos 90 dias")
        if (rule.get("Expiration") or {}).get("Days") != 365:
            problemas.append("expiração das versões atuais aos 365 dias")
        if (rule.get("NoncurrentVersionExpiration") or {}).get("NoncurrentDays") != 30:
            problemas.append("exclusão das versões antigas 30 dias depois de deixarem de ser atuais")
        if not problemas:
            return ValidationResult(passed=True, message="Regra de Lifecycle de pedidos/ configurada.")
    return _fail(
        "A regra de pedidos/ não tem: " + "; ".join(problemas) + ".",
        "Confira os dias de cada ação. As transições contam a partir da criação do objeto.",
    )


# ----------------------------------------------------------------- step 10
def _filter_value(config: dict, name: str) -> Optional[str]:
    rules = ((config.get("Filter") or {}).get("Key") or {}).get("FilterRules", [])
    for rule in rules:
        if str(rule.get("Name", "")).lower() == name:
            return rule.get("Value")
    return None


@_safe_validate
def _validate_evento(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    s3 = session.client("s3")
    try:
        config = s3.get_bucket_notification_configuration(Bucket=names.raw)
    except ClientError as exc:
        return _missing_bucket(names, exc) or _fail(f"{_error_code(exc)}: {exc}")
    ligadas = [
        c for c in config.get("LambdaFunctionConfigurations", [])
        if c.get("LambdaFunctionArn", "").split(":$")[0] == names.function_arn
    ]
    if not ligadas:
        eventbridge = "EventBridgeConfiguration" in config
        return _fail(
            "O bucket raw não tem notificação para a Lambda workshop-lab-01-indexador.",
            "Nesta prática o destino é a função Lambda, não o EventBridge." if eventbridge
            else "Crie a notificação em Properties > Event notifications do bucket raw.",
        )
    corretas = [
        c for c in ligadas
        if any(e.startswith("s3:ObjectCreated:") for e in c.get("Events", []))
        and _filter_value(c, "prefix") == "pedidos/"
        and _filter_value(c, "suffix") == ".csv"
    ]
    if not corretas:
        return _fail(
            "A notificação existe, mas precisa de eventos ObjectCreated, prefixo pedidos/ e sufixo .csv.",
            "Sem o filtro, a Lambda seria chamada para qualquer arquivo do bucket.",
        )
    resumos = _list_keys(s3, names.curated, "resumos/pedidos/")
    if not resumos:
        return _fail(
            "A notificação está certa, mas ainda não há resumos em curated/resumos/pedidos/.",
            "Copie um CSV para pedidos/dt=2026-03-11/ depois de criar a notificação. Se não aparecer, "
            "veja os logs em /aws/lambda/workshop-lab-01-indexador no CloudWatch.",
        )
    return ValidationResult(
        passed=True, message=f"Evento configurado e {len(resumos)} resumo(s) gravado(s) pela Lambda."
    )


# ----------------------------------------------------------------- step 12
def _all_versions(s3: Any, bucket: str) -> Iterable[dict]:
    for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
        for item in page.get("Versions", []):
            yield {**item, "_marker": False}
        for item in page.get("DeleteMarkers", []):
            yield {**item, "_marker": True}


@_safe_validate
def _validate_exclusao(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    s3 = session.client("s3")
    try:
        versoes = list(_all_versions(s3, names.raw))
    except ClientError as exc:
        return _missing_bucket(names, exc) or _fail(f"{_error_code(exc)}: {exc}")
    restos = [v for v in versoes if v["Key"].endswith(f"{CLIENTE_EXCLUIDO}.json")]
    if restos:
        marcadores = [v for v in restos if v["_marker"]]
        dados = [v for v in restos if not v["_marker"]]
        if dados and marcadores:
            dica = ("Excluir sem informar a versão só cria um delete marker: o arquivo some da lista, "
                    "mas a versão com os dados continua no bucket. Mostre as versões e apague cada uma.")
        elif dados:
            dica = "Apague todas as versões do arquivo, informando o VersionId de cada uma."
        else:
            dica = "Os dados já foram apagados. Falta remover o delete marker que sobrou."
        return _fail(
            f"Ainda existem {len(restos)} versão(ões) ou delete marker(s) de {CLIENTE_EXCLUIDO}.json "
            f"({len(dados)} com dados).",
            dica,
        )
    atuais = {v["Key"] for v in versoes if not v["_marker"] and v.get("IsLatest")}
    outros = [c for c in CLIENTES if c != CLIENTE_EXCLUIDO and f"clientes/{c}.json" not in atuais]
    if outros:
        return _fail(
            "Os dados dos outros clientes também sumiram: " + ", ".join(outros) + ".",
            "A solicitação é só do cliente-0042. Se apagou outro por engano, restaure a versão anterior.",
        )
    return ValidationResult(passed=True, message="Dados do cliente-0042 removidos de forma definitiva, sem afetar os outros clientes.")


# ----------------------------------------------------------------- step 14
def _normalize(statement: dict) -> tuple[list, list, list]:
    principal = statement.get("Principal")
    if isinstance(principal, dict):
        principals = _as_list(principal.get("AWS"))
    else:
        principals = _as_list(principal)
    actions = [str(a).lower() for a in _as_list(statement.get("Action"))]
    resources = [str(r) for r in _as_list(statement.get("Resource"))]
    return principals, actions, resources


@_safe_validate
def _validate_access_point(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    s3c = session.client("s3control")
    try:
        ap = s3c.get_access_point(AccountId=names.account, Name=ACCESS_POINT)
    except ClientError as exc:
        if _error_code(exc) in ("NoSuchAccessPoint", "NotFound"):
            return _fail(f"O Access Point {ACCESS_POINT} não existe na Region {names.region}.")
        raise
    if ap.get("Bucket") != names.curated:
        return _fail(f"O Access Point {ACCESS_POINT} aponta para {ap.get('Bucket')}, e não para o bucket curated.")
    try:
        policy = json.loads(s3c.get_access_point_policy(AccountId=names.account, Name=ACCESS_POINT)["Policy"])
    except ClientError as exc:
        if _error_code(exc) in ("NoSuchAccessPointPolicy", "NoSuchPolicy"):
            return _fail("O Access Point existe, mas ainda não tem política.")
        raise
    ap_arn = f"arn:aws:s3:{names.region}:{names.account}:accesspoint/{ACCESS_POINT}"
    allows = [s for s in _as_list(policy.get("Statement")) if s.get("Effect") == "Allow"]
    escrita = [s for s in allows if any(a in WRITE_ACTIONS for a in _normalize(s)[1])]
    if escrita:
        return _fail(
            "A política do Access Point permite escrita ou exclusão.",
            "O time de análise só lê: use apenas s3:GetObject.",
        )
    for statement in allows:
        principals, actions, resources = _normalize(statement)
        if (names.analista_arn in principals and "s3:getobject" in actions
                and resources and all(r.startswith(f"{ap_arn}/object/resumos/") for r in resources)):
            return ValidationResult(passed=True, message="Access Point analytics com leitura de resumos/ para a role analista.")
    return _fail(
        "A política não dá s3:GetObject à role analista só em resumos/.",
        f"Principal: {names.analista_arn}. Resource: {ap_arn}/object/resumos/*",
    )


# ----------------------------------------------------------------- step 15
@_safe_validate
def _validate_replicacao(session: Any, ctx: dict) -> ValidationResult:
    names = Names(session)
    s3 = session.client("s3")
    try:
        config = s3.get_bucket_replication(Bucket=names.raw)["ReplicationConfiguration"]
    except ClientError as exc:
        if _error_code(exc) == "ReplicationConfigurationNotFoundError":
            return _fail("O bucket raw ainda não tem regra de replicação.")
        return _missing_bucket(names, exc) or _fail(f"{_error_code(exc)}: {exc}")
    ativas = [r for r in config.get("Rules", []) if r.get("Status") == "Enabled"]
    if not ativas:
        return _fail("A regra de replicação existe, mas não está ativa.")
    for rule in ativas:
        destino = (rule.get("Destination") or {}).get("Bucket", "").split(":::")[-1]
        if not destino:
            continue
        local = s3.get_bucket_location(Bucket=destino).get("LocationConstraint") or "us-east-1"
        if local != names.region:
            return ValidationResult(
                passed=True, message=f"Replicação ativa do raw para {destino}, na Region {local}."
            )
    return _fail(
        "O bucket de destino está na mesma Region do raw.",
        "Esta prática é de replicação entre Regions (CRR): crie o destino em outra Region.",
    )


STEP_VALIDATORS = {
    "step-04": _validate_organizar,
    "step-06": _validate_versionamento,
    "step-08": _validate_lifecycle,
    "step-10": _validate_evento,
    "step-12": _validate_exclusao,
    "step-14": _validate_access_point,
    "step-15": _validate_replicacao,
}


def validate_step(boto3_session: Any, context: dict) -> ValidationResult:
    return dispatch_step(STEP_VALIDATORS, boto3_session, context)
