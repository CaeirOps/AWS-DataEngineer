"""Validadores do Módulo 02 com boto3 simulado (task 18.7).

Valida: Requirements 5.1, 5.2, 5.3.
"""

import json
from datetime import datetime, timezone

import boto3
import pytest
from botocore.stub import Stubber

from app.validators import lab02

ACCOUNT = "123456789012"
REGION = "us-east-1"
BUCKET = f"workshop-lab-02-dados-{ACCOUNT}-{REGION}"
DB = "workshop-lab-02-anycompany"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/workshop-lab-02-crawler-{REGION}"
NOW = datetime(2026, 3, 11, tzinfo=timezone.utc)


class FakeSession:
    region_name = REGION

    def __init__(self):
        kw = dict(region_name=REGION, aws_access_key_id="x", aws_secret_access_key="x")
        self.clients = {n: boto3.client(n, **kw) for n in ("sts", "glue", "s3")}
        self.stubs = {n: Stubber(c) for n, c in self.clients.items()}
        for s in self.stubs.values():
            s.activate()
        self.stubs["sts"].add_response("get_caller_identity", {"Account": ACCOUNT, "Arn": "arn:aws:iam::1:user/x", "UserId": "x"})

    def client(self, name):
        return self.clients[name]

    def glue(self, method, response):
        self.stubs["glue"].add_response(method, response)

    def glue_error(self, method, code="EntityNotFoundException"):
        self.stubs["glue"].add_client_error(method, service_error_code=code, http_status_code=400)

    def s3(self, method, response):
        self.stubs["s3"].add_response(method, response)


@pytest.fixture
def s():
    return FakeSession()


def run(step, session):
    return lab02.validate_step(session, {"step_id": step})


def crawler(name="workshop-lab-02-pedidos", paths=("pedidos",), status="SUCCEEDED", role=ROLE, **over):
    data = {
        "Name": name, "Role": role, "DatabaseName": DB,
        "Targets": {"S3Targets": [{"Path": f"s3://{BUCKET}/{p}/"} for p in paths]},
        "State": "READY",
        "SchemaChangePolicy": {"UpdateBehavior": "LOG", "DeleteBehavior": "LOG"},
    }
    if status:
        data["LastCrawl"] = {"Status": status}
    data.update(over)
    return {"Crawler": data}


def table(name="pedidos", keys=("dt",), cols=("id_pedido", "valor"), **over):
    t = {"Name": name, "DatabaseName": DB, "PartitionKeys": [{"Name": k, "Type": "string"} for k in keys],
         "StorageDescriptor": {"Columns": [{"Name": c, "Type": "string"} for c in cols]}}
    t.update(over)
    return t


def partitions(datas, base="pedidos"):
    return {"Partitions": [{"Values": [d], "DatabaseName": DB, "TableName": "pedidos",
                            "StorageDescriptor": {"Location": f"s3://{BUCKET}/{base}/dt={d}/"}} for d in datas]}


# --------------------------------------------------------------- step 04
def test_step04_ok(s):
    s.glue("get_crawler", crawler())
    s.glue("get_table", {"Table": table()})
    s.glue("get_partitions", partitions(lab02.DATAS))
    assert run("step-04", s).passed is True


def test_step04_crawler_inexistente(s):
    s.glue_error("get_crawler")
    result = run("step-04", s)
    assert not result.passed and "não existe" in result.message


def test_step04_alvo_errado(s):
    s.glue("get_crawler", crawler(paths=("clientes",)))
    result = run("step-04", s)
    assert not result.passed and "pedidos/" in result.message


def test_step04_bucket_inteiro_como_alvo_e_recusado(s):
    data = crawler()
    data["Crawler"]["Targets"]["S3Targets"] = [{"Path": f"s3://{BUCKET}/"}]
    s.glue("get_crawler", data)
    assert not run("step-04", s).passed


@pytest.mark.parametrize("role", [ROLE, f"workshop-lab-02-crawler-{REGION}"])
def test_step04_aceita_role_por_arn_ou_por_nome(s, role):
    """A API do Glue devolve só o nome da role, mesmo quando o crawler foi criado com o ARN."""
    s.glue("get_crawler", crawler(role=role))
    s.glue("get_table", {"Table": table()})
    s.glue("get_partitions", partitions(lab02.DATAS))
    assert run("step-04", s).passed is True


@pytest.mark.parametrize("role", [f"arn:aws:iam::{ACCOUNT}:role/workshop-lab-02-crawler-sa-east-1", "outra", f"x/workshop-lab-02-crawler-{REGION}"])
def test_step04_recusa_outras_roles(s, role):
    s.glue("get_crawler", crawler(role=role))
    assert "role" in run("step-04", s).message


def test_step04_role_errada(s):
    s.glue("get_crawler", crawler(role=f"arn:aws:iam::{ACCOUNT}:role/outra"))
    assert "role" in run("step-04", s).message


@pytest.mark.parametrize("status,trecho", [(None, "ainda não terminou"), ("FAILED", "FAILED")])
def test_step04_sem_execucao_bem_sucedida(s, status, trecho):
    s.glue("get_crawler", crawler(status=status))
    result = run("step-04", s)
    assert not result.passed and trecho in result.message and "READY" in result.hint


def test_step04_dt_duplicado_como_coluna_e_particao(s):
    s.glue("get_crawler", crawler())
    s.glue("get_table", {"Table": table(cols=("id_pedido", "valor", "dt"))})
    s.glue("get_partitions", partitions(lab02.DATAS))
    result = run("step-04", s)
    assert not result.passed and "chave de partição" in result.message


def test_step04_tabela_ausente(s):
    s.glue("get_crawler", crawler())
    s.glue_error("get_table")
    assert "tabela pedidos não apareceu" in run("step-04", s).message


def test_step04_sem_particao_dt(s):
    s.glue("get_crawler", crawler())
    s.glue("get_table", {"Table": table(keys=("partition_0",))})
    assert "partição" in run("step-04", s).message


def test_step04_particoes_faltando(s):
    s.glue("get_crawler", crawler())
    s.glue("get_table", {"Table": table()})
    s.glue("get_partitions", partitions(lab02.DATAS[:2]))
    result = run("step-04", s)
    assert not result.passed and "dt=2026-03-10" in result.message


# --------------------------------------------------------------- step 06
def fontes(**over):
    base = dict(name="workshop-lab-02-fontes", paths=("pedidos", "clientes", "fornecedores"), TablePrefix="raw_",
                Schedule={"ScheduleExpression": "cron(0 6 * * ? *)", "State": "SCHEDULED"})
    base.update(over)
    return crawler(**base)


def tabelas(*nomes):
    return {"TableList": [table(n) for n in nomes]}


def test_step06_ok(s):
    s.glue("get_crawler", fontes())
    s.glue("get_tables", tabelas("raw_pedidos", "raw_clientes", "raw_fornecedores"))
    assert run("step-06", s).passed is True


def test_step06_alvo_faltando(s):
    s.glue("get_crawler", fontes(paths=("pedidos", "clientes")))
    result = run("step-06", s)
    assert not result.passed and "fornecedores/" in result.message


def test_step06_prefixo_errado(s):
    s.glue("get_crawler", fontes(TablePrefix="bruto_"))
    assert "prefixo" in run("step-06", s).message


@pytest.mark.parametrize("schedule", [
    None,
    {"ScheduleExpression": "cron(0 6 * * ? *)", "State": "NOT_SCHEDULED"},
    {"ScheduleExpression": "cron(0/15 * * * ? *)", "State": "SCHEDULED"},
    {"ScheduleExpression": "cron(0 6 ? * MON *)", "State": "SCHEDULED"},
])
def test_step06_agenda_invalida(s, schedule):
    over = {"Schedule": schedule} if schedule else {}
    data = fontes(**over)
    if schedule is None:
        data["Crawler"].pop("Schedule")
    s.glue("get_crawler", data)
    assert "agenda" in run("step-06", s).message


def test_step06_sem_execucao(s):
    s.glue("get_crawler", fontes(status=None))
    assert "Execute o crawler" in run("step-06", s).message


def test_step06_tabelas_faltando(s):
    s.glue("get_crawler", fontes())
    s.glue("get_tables", tabelas("raw_pedidos"))
    assert "raw_clientes" in run("step-06", s).message


# --------------------------------------------------------------- step 08
def test_step08_ok(s):
    s.glue("get_table", {"Table": table()})
    s.s3("list_objects_v2", {"KeyCount": 1})
    s.glue("get_partitions", partitions(lab02.DATAS + (lab02.NOVA_PARTICAO,)))
    s.glue("get_crawler", crawler())
    assert run("step-08", s).passed is True


def test_step08_pasta_nao_existe_no_s3(s):
    s.glue("get_table", {"Table": table()})
    s.s3("list_objects_v2", {"KeyCount": 0})
    result = run("step-08", s)
    assert not result.passed and "ainda não existe no bucket" in result.message


def test_step08_particao_nao_registrada(s):
    s.glue("get_table", {"Table": table()})
    s.s3("list_objects_v2", {"KeyCount": 1})
    s.glue("get_partitions", partitions(lab02.DATAS))
    result = run("step-08", s)
    assert not result.passed and "batch-create-partition" in result.hint


def test_step08_localizacao_errada(s):
    s.glue("get_table", {"Table": table()})
    s.s3("list_objects_v2", {"KeyCount": 1})
    data = partitions(lab02.DATAS + (lab02.NOVA_PARTICAO,))
    data["Partitions"][-1]["StorageDescriptor"]["Location"] = f"s3://{BUCKET}/clientes/"
    s.glue("get_partitions", data)
    assert "aponta para" in run("step-08", s).message


def test_step08_tabela_inexistente(s):
    s.glue_error("get_table")
    assert "step 04" in run("step-08", s).message


# --------------------------------------------------------------- step 11
def policy(update="UPDATE_IN_DATABASE", delete="LOG"):
    return {"SchemaChangePolicy": {"UpdateBehavior": update, "DeleteBehavior": delete}}


COLS = ("sku", "descricao", "quantidade", "preco", "categoria")


def test_step11_ok(s):
    s.glue("get_crawler", crawler(name="workshop-lab-02-fontes", **policy()))
    s.s3("list_objects_v2", {"KeyCount": 1})
    s.glue("get_table", {"Table": table("raw_fornecedores", keys=(), cols=COLS)})
    assert run("step-11", s).passed is True


@pytest.mark.parametrize("pol,trecho", [(policy("LOG"), "UPDATE_IN_DATABASE"), (policy(delete="DELETE_FROM_DATABASE"), "apaga tabelas")])
def test_step11_politica_errada(s, pol, trecho):
    s.glue("get_crawler", crawler(name="workshop-lab-02-fontes", **pol))
    assert trecho in run("step-11", s).message


def test_step11_arquivo_novo_ausente(s):
    s.glue("get_crawler", crawler(name="workshop-lab-02-fontes", **policy()))
    s.s3("list_objects_v2", {"KeyCount": 0})
    assert "não foi enviado" in run("step-11", s).message


def test_step11_coluna_ausente(s):
    s.glue("get_crawler", crawler(name="workshop-lab-02-fontes", **policy()))
    s.s3("list_objects_v2", {"KeyCount": 1})
    s.glue("get_table", {"Table": table("raw_fornecedores", keys=(), cols=COLS[:4])})
    result = run("step-11", s)
    assert not result.passed and "categoria" in result.message and "crawler de novo" in result.hint


def test_step11_coluna_fora_do_fim(s):
    s.glue("get_crawler", crawler(name="workshop-lab-02-fontes", **policy()))
    s.s3("list_objects_v2", {"KeyCount": 1})
    s.glue("get_table", {"Table": table("raw_fornecedores", keys=(), cols=("sku", "categoria", "descricao", "quantidade", "preco"))})
    assert "fora de ordem" in run("step-11", s).message


# --------------------------------------------------------------- erros
def test_erro_de_acesso_vira_resultado(s):
    s.glue_error("get_crawler", "AccessDeniedException")
    result = run("step-04", s)
    assert not result.passed and "AccessDeniedException" in result.message


def test_step_desconhecido(s):
    assert run("step-99", s).passed is False


def test_validators_cobrem_os_tasks_do_metadata():
    meta = json.load(open("labs/lab-02/metadata.json", encoding="utf-8"))
    assert {st["step_id"] for st in meta["steps"] if st["type"] == "task"} == set(lab02.STEP_VALIDATORS)
