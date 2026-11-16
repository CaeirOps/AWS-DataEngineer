"""Hierarquia de exceções da plataforma.

Cada exceção define o `code` e o `http_status` usados no schema de erro da API.
"""


class WorkshopError(Exception):
    """Base para todos os erros da plataforma."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500


class CredentialsError(WorkshopError):
    """Token AWS expirado."""

    code = "CREDENTIALS_EXPIRED"
    http_status = 401


class CredentialsMissingError(WorkshopError):
    """Nenhuma credencial AWS configurada."""

    code = "CREDENTIALS_MISSING"
    http_status = 401


class PermissionsError(WorkshopError):
    """Permissão AWS insuficiente."""

    code = "PERMISSIONS_DENIED"
    http_status = 403


class LabNotFoundError(WorkshopError):
    """lab_id inválido."""

    code = "LAB_NOT_FOUND"
    http_status = 404


class StepNotFoundError(WorkshopError):
    """step_id inválido para o lab."""

    code = "STEP_NOT_FOUND"
    http_status = 404


class InvalidPathError(WorkshopError):
    """Trilha ausente ou diferente de `console`/`cli`."""

    code = "INVALID_PATH"
    http_status = 400


class InvalidPayloadError(WorkshopError):
    """Corpo de `PUT /api/progress` sem nenhuma atualização suportada."""

    code = "INVALID_PAYLOAD"
    http_status = 400


class PathUnavailableError(WorkshopError):
    """Trilha válida, mas ausente de `paths` do step.

    A mensagem deve trazer o motivo registrado em `unavailable_paths`.
    """

    code = "PATH_UNAVAILABLE"
    http_status = 409

    def __init__(self, path: str, reason: str = ""):
        self.path = path
        self.reason = reason
        message = f"Trilha '{path}' indisponível neste step."
        if reason:
            message += f" Motivo: {reason}"
        super().__init__(message)


class StepRequiresValidationError(WorkshopError):
    """Step do tipo `task` só pode ser concluído por validação, não por visita."""

    code = "STEP_REQUIRES_VALIDATION"
    http_status = 409


class StackNotFoundError(WorkshopError):
    """Stack CloudFormation não existe."""

    code = "STACK_NOT_FOUND"
    http_status = 404


class StackDeployError(WorkshopError):
    """Deploy CloudFormation falhou."""

    code = "STACK_DEPLOY_FAILED"
    http_status = 422
