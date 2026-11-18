"""Testes de unidade do CloudFormationService, sem chamadas AWS reais.

Usa `botocore.stub.Stubber` sobre um cliente real (sem rede) injetado pela
fábrica de sessão do serviço.
"""
import json
from datetime import datetime, timezone

import boto3
import pytest
from botocore.exceptions import NoCredentialsError
from botocore.stub import Stubber

from app.cloudformation_service import MAX_TEMPLATE_BYTES, CloudFormationService
from app.errors import (
    CredentialsError,
    CredentialsMissingError,
    LabNotFoundError,
    PermissionsError,
    StackDeployError,
    StackNotFoundError,
)
from app.lab_catalog import LabCatalog
from app.validators.base import CREDENTIAL_HINT
from tests.fixtures import INFRA_FIELDS, write_stack

LAB_ID = "lab-a"
STACK = "workshop-lab-a"
RESIDUAL = ["Bucket S3 de saída", "Log group /aws/lambda/x"]
PLAIN_TEMPLATE = "Resources:\n  B:\n    Type: AWS::S3::Bucket\n"
IAM_TEMPLATE = "Resources:\n  R:\n    Type: AWS::IAM::Role\n"
NOW = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def make_catalog(tmp_path, template=PLAIN_TEMPLATE, residual=None):
    """Monta um módulo mínimo com infraestrutura em `tmp_path`.

    `template=None` remove o stack.yaml depois da carga do catálogo, para
    simular o arquivo apagado com o servidor no ar.
    """
    lab_dir = tmp_path / LAB_ID
    lab_dir.mkdir()
    meta = {
        "lab_id": LAB_ID,
        "title": "Lab A",
        "description": "d",
        "difficulty": "iniciante",
        "estimated_duration_minutes": 10,
        "estimated_cost_usd": 0.1,
        "cost_disclaimer": "c",
        "dea_domains": [],
        "dea_tasks": [],
        "services": ["Amazon S3"],
        **INFRA_FIELDS,
        "steps": [
            {"step_id": "i1", "title": "Info", "type": "info"},
            {"step_id": "d1", "title": "Deploy", "type": "deploy"},
            {"step_id": "x1", "title": "Teardown", "type": "teardown"},
        ],
        "residual_resources": RESIDUAL if residual is None else residual,
    }
    (lab_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    write_stack(lab_dir, template if template is not None else PLAIN_TEMPLATE)
    catalog = LabCatalog(str(tmp_path))
    if template is None:
        (lab_dir / "cloudformation" / "stack.yaml").unlink()
    return catalog


class Harness:
    """Cliente cloudformation real com Stubber e a fábrica de sessão fake."""

    def __init__(self, tmp_path, **catalog_kwargs):
        self.client = boto3.client(
            "cloudformation",
            region_name="us-east-1",
            aws_access_key_id="x",
            aws_secret_access_key="x",
        )
        self.stubber = Stubber(self.client)
        self.stubber.activate()
        client = self.client

        class Session:
            def client(self, name):
                assert name == "cloudformation"
                return client

        self.service = CloudFormationService(
            make_catalog(tmp_path, **catalog_kwargs), session_factory=lambda: Session()
        )

    def stack(self, status, **extra):
        return {
            "StackName": STACK,
            "CreationTime": NOW,
            "StackStatus": status,
            **extra,
        }

    def expect_describe(self, status=None, **extra):
        """Stack existente com `status`; `None` simula stack inexistente."""
        if status is None:
            self.stubber.add_client_error(
                "describe_stacks",
                service_error_code="ValidationError",
                service_message=f"Stack with id {STACK} does not exist",
                expected_params={"StackName": STACK},
            )
        else:
            self.stubber.add_response(
                "describe_stacks",
                {"Stacks": [self.stack(status, **extra)]},
                {"StackName": STACK},
            )

    def done(self):
        self.stubber.assert_no_pending_responses()


def event(logical_id, status, reason=None, n=1):
    ev = {
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/x/1",
        "EventId": f"e{n}-{logical_id}",
        "StackName": STACK,
        "LogicalResourceId": logical_id,
        "ResourceStatus": status,
        "Timestamp": NOW,
    }
    if reason:
        ev["ResourceStatusReason"] = reason
    return ev


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path)


# ----------------------------------------------------------------------
# deploy
# ----------------------------------------------------------------------


def test_deploy_new_stack_sends_template_tags_and_onfailure(tmp_path):
    h = Harness(tmp_path)
    h.expect_describe(None)
    h.stubber.add_response(
        "create_stack",
        {"StackId": "id"},
        {
            "StackName": STACK,
            "TemplateBody": PLAIN_TEMPLATE,
            "Capabilities": [],
            "OnFailure": "ROLLBACK",
            "Tags": [
                {"Key": "Project", "Value": "aws-data-engineer-workshop"},
                {"Key": "Lab", "Value": LAB_ID},
            ],
        },
    )
    result = h.service.deploy(LAB_ID)
    h.done()
    assert result["stack_name"] == STACK
    assert result["status"] == "CREATE_IN_PROGRESS"


def test_deploy_requests_iam_capabilities_only_when_template_has_iam(tmp_path):
    h = Harness(tmp_path, template=IAM_TEMPLATE)
    h.expect_describe(None)
    h.stubber.add_response(
        "create_stack",
        {"StackId": "id"},
        {
            "StackName": STACK,
            "TemplateBody": IAM_TEMPLATE,
            "Capabilities": ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
            "OnFailure": "ROLLBACK",
            "Tags": [
                {"Key": "Project", "Value": "aws-data-engineer-workshop"},
                {"Key": "Lab", "Value": LAB_ID},
            ],
        },
    )
    assert h.service.deploy(LAB_ID)["status"] == "CREATE_IN_PROGRESS"
    h.done()


def test_deploy_existing_stack_does_not_recreate(h):
    h.expect_describe("CREATE_COMPLETE")
    result = h.service.deploy(LAB_ID)
    h.done()  # nenhum create_stack foi enfileirado: chamá-lo falharia
    assert result["status"] == "CREATE_COMPLETE"
    assert "já existe" in result["message"]


def test_deploy_after_rollback_complete_guides_teardown(h):
    h.expect_describe("ROLLBACK_COMPLETE")
    result = h.service.deploy(LAB_ID)
    h.done()
    assert result["status"] == "ROLLBACK_COMPLETE"
    assert "teardown" in result["message"]


def test_deploy_missing_template_raises(tmp_path):
    h = Harness(tmp_path, template=None)
    with pytest.raises(StackDeployError):
        h.service.deploy(LAB_ID)


def test_deploy_template_over_limit_raises(tmp_path):
    big = "#" * (MAX_TEMPLATE_BYTES + 1)
    h = Harness(tmp_path, template=big)
    with pytest.raises(StackDeployError, match=str(MAX_TEMPLATE_BYTES)):
        h.service.deploy(LAB_ID)


def test_deploy_unknown_lab_raises(h):
    with pytest.raises(LabNotFoundError):
        h.service.deploy("nao-existe")


def test_deploy_generic_aws_error_becomes_stack_deploy_error(h):
    h.expect_describe(None)
    h.stubber.add_client_error(
        "create_stack",
        service_error_code="LimitExceededException",
        service_message="Too many stacks",
    )
    with pytest.raises(StackDeployError, match="LimitExceededException"):
        h.service.deploy(LAB_ID)


# ----------------------------------------------------------------------
# get_status
# ----------------------------------------------------------------------


def test_get_status_success_returns_outputs(h):
    h.expect_describe(
        "CREATE_COMPLETE",
        Outputs=[{"OutputKey": "BucketName", "OutputValue": "meu-bucket"}],
    )
    result = h.service.get_status(LAB_ID)
    assert result["status"] == "CREATE_COMPLETE"
    assert result["status_reason"] is None
    assert result["outputs"] == {"BucketName": "meu-bucket"}
    assert result["last_updated"] == "2025-01-01T12:00:00Z"


def test_get_status_failure_reason_is_oldest_failed_event_across_pages(h):
    h.expect_describe("ROLLBACK_COMPLETE")
    # A API devolve do evento mais novo para o mais antigo.
    h.stubber.add_response(
        "describe_stack_events",
        {
            "StackEvents": [
                event("Stack", "ROLLBACK_COMPLETE", n=6),
                # Falha de rollback: não é a causa raiz.
                event("Role", "DELETE_FAILED", "Role em uso", n=5),
                event("Other", "CREATE_FAILED", "Resource creation cancelled", n=4),
            ],
            "NextToken": "p2",
        },
        {"StackName": STACK},
    )
    h.stubber.add_response(
        "describe_stack_events",
        {
            "StackEvents": [
                event("Bucket", "CREATE_FAILED", "Bucket already exists", n=2),
                event("Stack", "CREATE_IN_PROGRESS", n=1),
            ]
        },
        {"StackName": STACK, "NextToken": "p2"},
    )
    result = h.service.get_status(LAB_ID)
    h.done()
    assert result["status_reason"] == "Bucket: Bucket already exists"


def test_get_status_delete_failed_uses_delete_failed_event(h):
    h.expect_describe("DELETE_FAILED")
    h.stubber.add_response(
        "describe_stack_events",
        {
            "StackEvents": [
                event("Bucket", "DELETE_FAILED", "Bucket não está vazio", n=3),
                event("Bucket", "CREATE_FAILED", "antigo", n=1),
            ]
        },
        {"StackName": STACK},
    )
    assert h.service.get_status(LAB_ID)["status_reason"] == "Bucket: Bucket não está vazio"


def test_get_status_failure_falls_back_to_stack_reason(h):
    h.expect_describe("ROLLBACK_COMPLETE", StackStatusReason="motivo da stack")
    h.stubber.add_response(
        "describe_stack_events",
        {"StackEvents": [event("Stack", "ROLLBACK_COMPLETE")]},
        {"StackName": STACK},
    )
    assert h.service.get_status(LAB_ID)["status_reason"] == "motivo da stack"


def test_get_status_missing_stack_raises(h):
    h.expect_describe(None)
    with pytest.raises(StackNotFoundError):
        h.service.get_status(LAB_ID)


# ----------------------------------------------------------------------
# teardown
# ----------------------------------------------------------------------


def test_teardown_existing_stack_deletes_and_lists_residual(h):
    h.expect_describe("CREATE_COMPLETE")
    h.stubber.add_response("delete_stack", {}, {"StackName": STACK})
    result = h.service.teardown(LAB_ID)
    h.done()
    assert result["status"] == "DELETE_IN_PROGRESS"
    assert result["residual_resources"] == RESIDUAL


def test_teardown_missing_stack_is_not_an_error(h):
    h.expect_describe(None)
    result = h.service.teardown(LAB_ID)
    h.done()
    assert result["status"] == "DELETE_COMPLETE"
    assert result["residual_resources"] == RESIDUAL


def test_teardown_already_deleting_does_not_delete_again(h):
    h.expect_describe("DELETE_IN_PROGRESS")
    result = h.service.teardown(LAB_ID)
    h.done()
    assert result["status"] == "DELETE_IN_PROGRESS"
    assert result["residual_resources"] == RESIDUAL


def test_teardown_validation_error_returns_current_status(h):
    h.expect_describe("UPDATE_IN_PROGRESS")
    h.stubber.add_client_error(
        "delete_stack",
        service_error_code="ValidationError",
        service_message="Stack em atualização",
    )
    result = h.service.teardown(LAB_ID)
    assert result["status"] == "UPDATE_IN_PROGRESS"
    assert "Stack em atualização" in result["message"]
    assert result["residual_resources"] == RESIDUAL


def test_teardown_returns_empty_residual_list_when_lab_has_none(tmp_path):
    h = Harness(tmp_path)
    h.service._catalog.get_lab(LAB_ID).residual_resources.clear()
    h.expect_describe(None)
    assert h.service.teardown(LAB_ID)["residual_resources"] == []


def test_teardown_unknown_lab_raises(h):
    with pytest.raises(LabNotFoundError):
        h.service.teardown("nao-existe")


# ----------------------------------------------------------------------
# Erros de credenciais e permissões
# ----------------------------------------------------------------------


def test_expired_token_raises_credentials_error_with_hint(h):
    h.stubber.add_client_error(
        "describe_stacks",
        service_error_code="ExpiredToken",
        service_message="The security token included in the request is expired",
    )
    with pytest.raises(CredentialsError) as exc:
        h.service.get_status(LAB_ID)
    assert "ExpiredToken" in str(exc.value)
    assert CREDENTIAL_HINT in str(exc.value)


def test_no_credentials_raises_credentials_missing_error(tmp_path):
    class Session:
        def client(self, name):
            raise NoCredentialsError()

    service = CloudFormationService(make_catalog(tmp_path), session_factory=lambda: Session())
    with pytest.raises(CredentialsMissingError) as exc:
        service.deploy(LAB_ID)
    assert CREDENTIAL_HINT in str(exc.value)


def test_access_denied_raises_permissions_error(h):
    h.stubber.add_client_error(
        "describe_stacks",
        service_error_code="AccessDenied",
        service_message="User is not authorized",
    )
    with pytest.raises(PermissionsError, match="AccessDenied"):
        h.service.teardown(LAB_ID)
