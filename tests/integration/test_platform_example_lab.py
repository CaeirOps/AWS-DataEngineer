"""Testes de integração da plataforma com o lab de exemplo (`lab-example`).

Cobrem Flask + LabCatalog + ProgressStore + ValidationService +
CloudFormationService, com sessão boto3 fake (sem AWS real e sem Docker).

Valida: 2.2, 2.3, 5.1, 6.2, 11.1, 11.3, 11.5, 11.6.
"""

import json
from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError

from app.lab_catalog import LabCatalog
from app.progress_store import ProgressStore
from app.server import create_app
from tests.fixtures.http_client import workshop_client
from app.validation_service import ValidationService
from tests.fixtures import EXAMPLE_LAB_ID, LABS_FIXTURE_DIR, THEORY_LAB_ID, example_validator_loader

LAB = EXAMPLE_LAB_ID
STACK = f"workshop-{LAB}"


class FakeS3:
    """S3 fake: a lista de buckets é controlada pelo teste."""

    def __init__(self):
        self.buckets = []
        self.error = None

    def list_buckets(self):
        if self.error is not None:
            raise self.error
        return {"Buckets": [{"Name": n} for n in self.buckets]}


class FakeCloudFormation:
    """CloudFormation fake com ciclo de vida simples da stack."""

    def __init__(self):
        self.status = None  # None = stack inexistente
        self.create_calls = []
        self.delete_calls = []
        self._polls_left = 0

    def describe_stacks(self, StackName):
        if self.status is None:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ValidationError",
                        "Message": f"Stack with id {StackName} does not exist",
                    }
                },
                "DescribeStacks",
            )
        # Cada consulta em andamento avança o estado, simulando o polling.
        status = self.status
        if status == "CREATE_IN_PROGRESS":
            if self._polls_left <= 0:
                self.status = "CREATE_COMPLETE"
            else:
                self._polls_left -= 1
        return {
            "Stacks": [
                {
                    "StackName": StackName,
                    "StackStatus": status,
                    "CreationTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    "Outputs": [{"OutputKey": "Exemplo", "OutputValue": "ok"}],
                }
            ]
        }

    def create_stack(self, **kwargs):
        self.create_calls.append(kwargs)
        self.status = "CREATE_IN_PROGRESS"
        self._polls_left = 1

    def delete_stack(self, StackName):
        self.delete_calls.append(StackName)
        self.status = "DELETE_IN_PROGRESS"


class FakeSession:
    def __init__(self, s3, cfn):
        self._clients = {"s3": s3, "cloudformation": cfn}

    def client(self, name):
        return self._clients[name]


@pytest.fixture
def env(tmp_path):
    s3, cfn = FakeS3(), FakeCloudFormation()
    session = FakeSession(s3, cfn)
    progress_file = tmp_path / "progress" / "progress.json"
    catalog = LabCatalog(str(LABS_FIXTURE_DIR))
    store = ProgressStore(str(progress_file))
    validation = ValidationService(
        catalog,
        store,
        session_factory=lambda: session,
        validator_loader=example_validator_loader,
    )
    app = create_app(
        {
            "catalog": catalog,
            "progress_store": store,
            "validation_service": validation,
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_file": str(progress_file),
            "session_factory": lambda: session,
            "static_folder": str(tmp_path / "static"),
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2999-01-01T00:00:00Z"},
        }
    )
    return {
        "client": workshop_client(app),
        "s3": s3,
        "cfn": cfn,
        "progress_file": progress_file,
        "store": store,
        "catalog": catalog,
    }


def _validate(client, step_id, **body):
    return client.post(f"/api/validate/{LAB}/{step_id}", json=body or {})


def test_listagem_mostra_lab_de_exemplo_com_retomada_no_primeiro_step(env):
    data = env["client"].get("/api/labs").get_json()
    labs = {lab["lab_id"]: lab for lab in data["labs"]}
    assert set(labs) == {LAB, THEORY_LAB_ID}
    lab = labs[LAB]
    assert lab["total_steps"] == 8
    assert lab["completed_steps"] == 0
    assert lab["status"] == "not_started"
    assert lab["resume_step"] == "step-01"


def test_detalhes_do_lab_trazem_trilhas_e_content_dos_steps_nao_task(env):
    data = env["client"].get(f"/api/labs/{LAB}").get_json()
    steps = {s["step_id"]: s for s in data["steps"]}
    assert steps["step-03"]["paths"] == ["console", "cli"]
    assert steps["step-03"]["unavailable_paths"] == {}
    assert steps["step-04"]["paths"] == ["console"]
    assert "cli" in steps["step-04"]["unavailable_paths"]
    assert steps["step-04"]["unavailable_paths"]["cli"]
    for sid in ("step-01", "step-02", "step-05", "step-06"):
        assert steps[sid]["content"].strip()
    for sid in ("step-03", "step-04", "step-07", "step-08"):
        assert "content" not in steps[sid]
    assert data["residual_resources"]


def test_conteudo_e_dica_por_trilha_e_trilha_indisponivel(env):
    client = env["client"]
    base = f"/api/labs/{LAB}/steps"
    console = client.get(f"{base}/step-03/content?path=console").get_json()
    cli = client.get(f"{base}/step-03/content?path=cli").get_json()
    assert "Trilha Console" in console["markdown"]
    assert "Trilha CLI" in cli["markdown"]
    assert "Criar bucket S3 de exemplo" in console["markdown"]  # cenário comum
    assert "Criar bucket S3 de exemplo" in cli["markdown"]
    assert console["markdown"] != cli["markdown"]

    hint_console = client.get(f"{base}/step-03/hint?path=console").get_json()["hint"]
    hint_cli = client.get(f"{base}/step-03/hint?path=cli").get_json()["hint"]
    assert "aws s3api" in hint_cli
    assert "aws s3api" not in hint_console

    # Trilha indisponível: 409 com o motivo declarado no metadata.
    for route in ("content", "hint"):
        resp = client.get(f"{base}/step-04/{route}?path=cli")
        assert resp.status_code == 409
        body = resp.get_json()
        assert body["code"] == "PATH_UNAVAILABLE"
        assert "visualização interativa" in body["message"]

    assert client.get(f"{base}/step-03/content?path=xyz").status_code == 400


def test_validacao_ate_o_limiar_da_dica_e_depois_conclui_o_lab(env):
    client = env["client"]

    # Bucket ausente: falha, e a dica só aparece a partir do limiar (3).
    for attempt in (1, 2):
        body = _validate(client, "step-03").get_json()
        assert body["passed"] is False
        assert body["attempt_count"] == attempt
        assert body["step_status"] == "failed"
        assert body["show_hint_button"] is False
        assert body["hint"] is None
    body = _validate(client, "step-03").get_json()
    assert body["attempt_count"] == 3
    assert body["show_hint_button"] is True
    assert body["hint"]

    detail = client.get(f"/api/labs/{LAB}").get_json()
    assert detail["status"] == "in_progress"
    assert detail["resume_step"] == "step-01"

    # Bucket presente: passa; a Trilha enviada no corpo é ignorada.
    env["s3"].buckets = ["workshop-example-123"]
    body = _validate(client, "step-03", path="cli").get_json()
    assert body["passed"] is True
    assert body["step_status"] == "passed"
    assert body["attempt_count"] == 4
    assert body["hint"] is None

    # Ainda falta o step-04, então o lab não está concluído.
    assert client.get(f"/api/labs/{LAB}").get_json()["status"] == "in_progress"

    body = _validate(client, "step-04").get_json()
    assert body["passed"] is True
    # Falta o quiz (step-08); a Prática opcional (step-07) não conta.
    assert client.get(f"/api/labs/{LAB}").get_json()["status"] == "in_progress"

    # A correção do quiz chega na task 15N; aqui o resultado vai direto ao store.
    lab_meta = env["catalog"].get_lab(LAB)
    env["store"].update_step(LAB, "step-08", "passed", lab_metadata=lab_meta)
    detail = client.get(f"/api/labs/{LAB}").get_json()
    assert detail["status"] == "completed"
    summary = {l["lab_id"]: l for l in client.get("/api/labs").get_json()["labs"]}[LAB]
    assert summary["status"] == "completed"
    assert summary["completed_steps"] == 3
    # step-01 e step-02 (não task) não passaram: a retomada ainda aponta para eles.
    assert detail["resume_step"] == "step-01"


def test_retomada_avanca_conforme_os_steps_passam(env):
    client = env["client"]
    env["s3"].buckets = ["workshop-example-1"]
    # A API não marca steps informativos; o progresso deles vem do ProgressStore.
    lab = env["catalog"].get_lab(LAB)
    for sid in ("step-01", "step-02"):
        env["store"].update_step(LAB, sid, "passed", lab_metadata=lab)
    assert client.get(f"/api/labs/{LAB}").get_json()["resume_step"] == "step-03"
    assert _validate(client, "step-03").get_json()["passed"] is True
    assert client.get(f"/api/labs/{LAB}").get_json()["resume_step"] == "step-04"


def test_validar_step_que_nao_e_task_retorna_erro(env):
    resp = _validate(env["client"], "step-01")
    assert resp.status_code == 404
    assert resp.get_json()["error"] is True


def test_erro_de_credencial_aparece_com_codigo_original_e_sugestao(env):
    env["s3"].error = ClientError(
        {"Error": {"Code": "ExpiredToken", "Message": "The security token expired"}},
        "ListBuckets",
    )
    resp = _validate(env["client"], "step-03")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["passed"] is False
    assert "ExpiredToken" in body["message"]
    assert "The security token expired" in body["message"]
    assert "Verifique as credenciais AWS do profile em uso." in body["message"]
    assert body["attempt_count"] == 1


def test_deploy_status_com_polling_e_teardown_com_confirmacao(env):
    client, cfn = env["client"], env["cfn"]

    deploy = client.post(f"/api/deploy/{LAB}").get_json()
    assert deploy["stack_name"] == STACK
    assert deploy["status"] == "CREATE_IN_PROGRESS"
    assert len(cfn.create_calls) == 1
    assert cfn.create_calls[0]["StackName"] == STACK
    assert "WaitConditionHandle" in cfn.create_calls[0]["TemplateBody"]

    # Polling: primeiro em andamento, depois concluída.
    statuses = [client.get(f"/api/stack-status/{LAB}").get_json() for _ in range(3)]
    names = [s["status"] for s in statuses]
    assert names[0] == "CREATE_IN_PROGRESS"
    assert names[-1] == "CREATE_COMPLETE"
    assert statuses[-1]["outputs"] == {"Exemplo": "ok"}

    # Teardown sem confirmação é rejeitado e não exclui nada.
    resp = client.post(f"/api/teardown/{LAB}", json={})
    assert resp.status_code == 400
    assert cfn.delete_calls == []

    resp = client.post(f"/api/teardown/{LAB}", json={"confirm": True})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "DELETE_IN_PROGRESS"
    assert cfn.delete_calls == [STACK]
    assert body["residual_resources"] == [
        "Bucket S3 de exemplo (fictício, criado manualmente e não gerenciado pela stack)"
    ]


def test_status_de_stack_inexistente_retorna_404(env):
    resp = env["client"].get(f"/api/stack-status/{LAB}")
    assert resp.status_code == 404
    assert resp.get_json()["error"] is True


def test_troca_de_trilha_e_persistida_e_refletida_no_get(env):
    client = env["client"]
    assert client.get("/api/progress").get_json()["preferences"]["path"] == "console"

    resp = client.put("/api/progress", json={"preferences": {"path": "cli"}})
    assert resp.status_code == 200
    assert client.get("/api/progress").get_json()["preferences"]["path"] == "cli"

    saved = json.loads(env["progress_file"].read_text(encoding="utf-8"))
    assert saved["preferences"]["path"] == "cli"

    # Trilha inválida é rejeitada e a preferência anterior permanece.
    resp = client.put("/api/progress", json={"preferences": {"path": "web"}})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_PATH"
    assert client.get("/api/progress").get_json()["preferences"]["path"] == "cli"

    # Trocar a Trilha não altera tentativas nem status dos steps.
    _validate(client, "step-03")
    before = client.get("/api/progress").get_json()["labs"][LAB]["steps"]["step-03"]
    client.put("/api/progress", json={"preferences": {"path": "console"}})
    after = client.get("/api/progress").get_json()["labs"][LAB]["steps"]["step-03"]
    assert before == after
