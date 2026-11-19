"""Validadores do Módulo 01 com boto3 simulado (task 17.7).

Valida: Requirements 5.1, 5.2, 5.3.
"""

import json
from datetime import datetime, timezone

import boto3
import pytest
from botocore.stub import Stubber

from app.validators import lab01

ACCOUNT = "123456789012"
REGION = "us-east-1"
RAW = f"workshop-lab-01-raw-{ACCOUNT}-{REGION}"
CURATED = f"workshop-lab-01-curated-{ACCOUNT}-{REGION}"
FN_ARN = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:workshop-lab-01-indexador"
ANALISTA = f"arn:aws:iam::{ACCOUNT}:role/workshop-lab-01-analista-{REGION}"
AP_ARN = f"arn:aws:s3:{REGION}:{ACCOUNT}:accesspoint/analytics"
NOW = datetime(2026, 3, 11, tzinfo=timezone.utc)


class FakeSession:
    region_name = REGION

    def __init__(self):
        kwargs = dict(region_name=REGION, aws_access_key_id="x", aws_secret_access_key="x")
        self.clients = {n: boto3.client(n, **kwargs) for n in ("sts", "s3", "s3control")}
        self.stubs = {n: Stubber(c) for n, c in self.clients.items()}
        for s in self.stubs.values():
            s.activate()
        self.stubs["sts"].add_response(
            "get_caller_identity", {"Account": ACCOUNT, "Arn": "arn:aws:iam::123456789012:user/x", "UserId": "x"}
        )

    def client(self, name):
        return self.clients[name]

    def s3(self, method, response, params=None):
        self.stubs["s3"].add_response(method, response, params)

    def s3_error(self, method, code):
        self.stubs["s3"].add_client_error(method, service_error_code=code, http_status_code=404)

    def s3c(self, method, response):
        self.stubs["s3control"].add_response(method, response)

    def s3c_error(self, method, code):
        self.stubs["s3control"].add_client_error(method, service_error_code=code, http_status_code=404)


def run(step, session):
    return lab01.validate_step(session, {"step_id": step})


def listing(keys):
    return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}


@pytest.fixture
def s():
    return FakeSession()


# --------------------------------------------------------------- step 04
def organizado():
    pedidos = [f"pedidos/dt={d}/pedidos-{d}.csv" for d in lab01.DATAS]
    clientes = [f"clientes/{c}.json" for c in lab01.CLIENTES]
    return [], pedidos, clientes


def test_organizar_ok(s):
    for keys in organizado():
        s.s3("list_objects_v2", listing(keys))
    assert run("step-04", s).passed is True


def test_organizar_falta_data(s):
    entrada, pedidos, clientes = organizado()
    for keys in (entrada, pedidos[:2], clientes):
        s.s3("list_objects_v2", listing(keys))
    result = run("step-04", s)
    assert not result.passed and "2026-03-10" in result.message


def test_organizar_entrada_nao_vazia(s):
    _, pedidos, clientes = organizado()
    for keys in (["entrada/pedidos-2026-03-08.csv"], pedidos, clientes):
        s.s3("list_objects_v2", listing(keys))
    result = run("step-04", s)
    assert not result.passed and "entrada/" in result.message and "mv" in result.hint


def test_organizar_aceita_cliente_42_ja_excluido(s):
    entrada, pedidos, clientes = organizado()
    for keys in (entrada, pedidos, [k for k in clientes if "0042" not in k]):
        s.s3("list_objects_v2", listing(keys))
    assert run("step-04", s).passed is True


def test_organizar_bucket_inexistente(s):
    s.s3_error("list_objects_v2", "NoSuchBucket")
    result = run("step-04", s)
    assert not result.passed and "Region us-east-1" in result.message


# --------------------------------------------------------------- step 06
@pytest.mark.parametrize("status,passed", [("Enabled", True), ("Suspended", False), (None, False)])
def test_versionamento(s, status, passed):
    s.s3("get_bucket_versioning", {"Status": status} if status else {}, {"Bucket": RAW})
    assert run("step-06", s).passed is passed


# --------------------------------------------------------------- step 08
def regra(**over):
    rule = {
        "ID": "pedidos", "Status": "Enabled", "Filter": {"Prefix": "pedidos/"},
        "Transitions": [{"Days": 30, "StorageClass": "STANDARD_IA"}, {"Days": 90, "StorageClass": "GLACIER_IR"}],
        "Expiration": {"Days": 365}, "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
    }
    rule.update(over)
    return rule


def test_lifecycle_ok_com_and(s):
    s.s3("get_bucket_lifecycle_configuration",
         {"Rules": [regra(Filter={"And": {"Prefix": "pedidos/", "ObjectSizeGreaterThan": 1}})]})
    assert run("step-08", s).passed is True


@pytest.mark.parametrize("over,trecho", [
    ({"Transitions": [{"Days": 60, "StorageClass": "STANDARD_IA"}, {"Days": 90, "StorageClass": "GLACIER_IR"}]}, "Standard-IA"),
    ({"Expiration": {"Days": 30}}, "365"),
    ({"NoncurrentVersionExpiration": {"NoncurrentDays": 7}}, "versões antigas"),
])
def test_lifecycle_detalhe_errado(s, over, trecho):
    s.s3("get_bucket_lifecycle_configuration", {"Rules": [regra(**over)]})
    result = run("step-08", s)
    assert not result.passed and trecho in result.message


@pytest.mark.parametrize("rule", [regra(Status="Disabled"), regra(Filter={"Prefix": "pedidos"})])
def test_lifecycle_sem_regra_ativa_de_pedidos(s, rule):
    s.s3("get_bucket_lifecycle_configuration", {"Rules": [rule]})
    assert "pedidos/" in run("step-08", s).message


def test_lifecycle_inexistente(s):
    s.s3_error("get_bucket_lifecycle_configuration", "NoSuchLifecycleConfiguration")
    assert "ainda não tem" in run("step-08", s).message


# --------------------------------------------------------------- step 10
def notificacao(prefix="pedidos/", suffix=".csv", arn=FN_ARN, events=("s3:ObjectCreated:*",)):
    return {"LambdaFunctionConfigurations": [{
        "LambdaFunctionArn": arn, "Events": list(events),
        "Filter": {"Key": {"FilterRules": [{"Name": "Prefix", "Value": prefix}, {"Name": "Suffix", "Value": suffix}]}},
    }]}


def test_evento_ok(s):
    s.s3("get_bucket_notification_configuration", notificacao())
    s.s3("list_objects_v2", listing(["resumos/pedidos/dt=2026-03-11/pedidos-2026-03-11.json"]))
    assert run("step-10", s).passed is True


def test_evento_sem_resumo(s):
    s.s3("get_bucket_notification_configuration", notificacao(events=("s3:ObjectCreated:Copy",)))
    s.s3("list_objects_v2", listing([]))
    result = run("step-10", s)
    assert not result.passed and "CloudWatch" in result.hint


@pytest.mark.parametrize("cfg", [notificacao(prefix=""), notificacao(suffix=".json"), notificacao(events=("s3:ObjectRemoved:*",))])
def test_evento_filtro_errado(s, cfg):
    s.s3("get_bucket_notification_configuration", cfg)
    assert "prefixo pedidos/" in run("step-10", s).message


def test_evento_outra_funcao(s):
    s.s3("get_bucket_notification_configuration", notificacao(arn=FN_ARN + "-outra"))
    assert "não tem notificação" in run("step-10", s).message


# --------------------------------------------------------------- step 12
def versoes(versions=(), markers=()):
    v = [{"Key": k, "VersionId": vid, "IsLatest": latest, "LastModified": NOW} for k, vid, latest in versions]
    m = [{"Key": k, "VersionId": vid, "IsLatest": True, "LastModified": NOW} for k, vid in markers]
    return {"Versions": v, "DeleteMarkers": m, "IsTruncated": False}


OUTROS = [("clientes/cliente-0041.json", "null", True), ("clientes/cliente-0043.json", "null", True)]


def test_exclusao_ok(s):
    s.s3("list_object_versions", versoes(OUTROS))
    assert run("step-12", s).passed is True


def test_exclusao_so_com_delete_marker(s):
    s.s3("list_object_versions", versoes(OUTROS + [("clientes/cliente-0042.json", "null", False)],
                                          [("clientes/cliente-0042.json", "m1")]))
    result = run("step-12", s)
    assert not result.passed and "delete marker" in result.hint


def test_exclusao_sobrou_marker(s):
    s.s3("list_object_versions", versoes(OUTROS, [("clientes/cliente-0042.json", "m1")]))
    assert "delete marker" in run("step-12", s).hint


def test_exclusao_apagou_outros(s):
    s.s3("list_object_versions", versoes(OUTROS[:1]))
    result = run("step-12", s)
    assert not result.passed and "cliente-0043" in result.message


# --------------------------------------------------------------- step 14
def politica(statements):
    return {"Policy": json.dumps({"Version": "2012-10-17", "Statement": statements})}


LEITURA = {"Effect": "Allow", "Principal": {"AWS": ANALISTA}, "Action": "s3:GetObject",
           "Resource": f"{AP_ARN}/object/resumos/*"}


def test_access_point_ok(s):
    s.s3c("get_access_point", {"Name": "analytics", "Bucket": CURATED})
    s.s3c("get_access_point_policy", politica([LEITURA]))
    assert run("step-14", s).passed is True


@pytest.mark.parametrize("statement,trecho", [
    ({**LEITURA, "Action": ["s3:GetObject", "s3:PutObject"]}, "escrita"),
    ({**LEITURA, "Resource": f"{AP_ARN}/object/*"}, "resumos/"),
    ({**LEITURA, "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT}:root"}}, "resumos/"),
])
def test_access_point_politica_errada(s, statement, trecho):
    s.s3c("get_access_point", {"Name": "analytics", "Bucket": CURATED})
    s.s3c("get_access_point_policy", politica([statement]))
    result = run("step-14", s)
    assert not result.passed and trecho in result.message


def test_access_point_bucket_errado(s):
    s.s3c("get_access_point", {"Name": "analytics", "Bucket": RAW})
    assert "não para o bucket curated" in run("step-14", s).message


def test_access_point_inexistente(s):
    s.s3c_error("get_access_point", "NoSuchAccessPoint")
    assert "não existe" in run("step-14", s).message


def test_access_point_sem_politica(s):
    s.s3c("get_access_point", {"Name": "analytics", "Bucket": CURATED})
    s.s3c_error("get_access_point_policy", "NoSuchAccessPointPolicy")
    assert "não tem política" in run("step-14", s).message


# --------------------------------------------------------------- step 15
def replicacao(dest="arn:aws:s3:::anycompany-dr-123", status="Enabled"):
    return {"ReplicationConfiguration": {"Role": "arn:aws:iam::123456789012:role/r", "Rules": [
        {"Status": status, "Priority": 1, "Filter": {}, "DeleteMarkerReplication": {"Status": "Disabled"},
         "Destination": {"Bucket": dest}}]}}


@pytest.mark.parametrize("location,passed", [("sa-east-1", True), (None, False)])
def test_replicacao_regiao(s, location, passed):
    s.s3("get_bucket_replication", replicacao())
    s.s3("get_bucket_location", {"LocationConstraint": location} if location else {})
    assert run("step-15", s).passed is passed


def test_replicacao_inativa(s):
    s.s3("get_bucket_replication", replicacao(status="Disabled"))
    assert "não está ativa" in run("step-15", s).message


def test_replicacao_inexistente(s):
    s.s3_error("get_bucket_replication", "ReplicationConfigurationNotFoundError")
    assert "ainda não tem" in run("step-15", s).message


# --------------------------------------------------------------- erros
def test_erro_de_acesso_vira_resultado_sem_excecao(s):
    s.stubs["s3"].add_client_error("get_bucket_versioning", service_error_code="AccessDenied", http_status_code=403)
    result = run("step-06", s)
    assert not result.passed and "AccessDenied" in result.message


def test_credencial_expirada_vira_mensagem_de_credencial():
    session = FakeSession()
    sts = boto3.client("sts", region_name=REGION, aws_access_key_id="x", aws_secret_access_key="x")
    stub = Stubber(sts)
    stub.add_client_error("get_caller_identity", service_error_code="ExpiredToken", http_status_code=400)
    stub.activate()
    session.clients["sts"] = sts
    result = run("step-06", session)
    assert not result.passed and "credenciais" in result.message.lower()


def test_step_desconhecido(s):
    assert run("step-99", s).passed is False


def test_validators_cobrem_os_tasks_do_metadata():
    meta = json.load(open("labs/lab-01/metadata.json", encoding="utf-8"))
    tasks = {st["step_id"] for st in meta["steps"] if st["type"] == "task"}
    assert tasks == set(lab01.STEP_VALIDATORS)
