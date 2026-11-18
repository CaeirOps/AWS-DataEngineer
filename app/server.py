"""Servidor Flask da plataforma de workshop.

Executado pelo gunicorn (`app.server:app`). Expõe a API REST, serve a SPA
estática e registra os serviços como singletons por processo. CORS fica
desabilitado: o browser acessa a mesma origem, via gateway.

Decisão sobre `content.md`: `GET /api/labs/<lab_id>` inclui o campo
`content` nos steps info, deploy, teardown e completion. Steps `task` não
trazem `content`; o conteúdo deles vem das rotas `.../content?path=` e
`.../hint?path=`. Steps `quiz` também não: as questões vêm das rotas de quiz.

Os nomes `lab_id` e `/api/labs` ficam por compatibilidade; na documentação
cada lab é um módulo. `estimated_cost_usd` não é exposto (19.4).
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory

from app.cloudformation_service import CloudFormationService
from app.errors import (
    InvalidPayloadError,
    LabNotFoundError,
    NoInfrastructureError,
    WorkshopError,
)
from app.http_security import register_request_guards
from app.lab_catalog import LabCatalog
from app.models import LabMetadata, StepMetadata
from app import session as session_module
from app.progress_store import ProgressStore
from app.redaction import log_exception, mask_json
from app.validation_service import ValidationService

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _json_body() -> dict:
    """Corpo JSON da requisição como objeto; vazio ou inválido vira `{}`."""
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _step_to_dict(step: StepMetadata) -> dict:
    data = {
        "step_id": step.step_id,
        "title": step.title,
        "type": step.type,
        "hint_threshold": step.hint_threshold,
        "skills": list(step.skills),
    }
    if step.type == "task":
        data["paths"] = list(step.paths or [])
        data["unavailable_paths"] = dict(step.unavailable_paths or {})
        data["optional"] = step.optional
        if step.optional:
            data["cost_note"] = step.cost_note
    if step.type == "quiz":
        data["pass_score"] = step.pass_score
    return data


def _module_fields(lab: LabMetadata) -> dict:
    """Campos de módulo comuns à listagem e ao detalhe."""
    return {
        "skills": list(lab.skills),
        "has_infrastructure": lab.has_infrastructure,
        "cost_notice": {
            "services": [dict(s) for s in lab.cost_notice.get("services", [])]
        }
        if lab.cost_notice
        else {},
    }


def create_app(config: Optional[dict] = None) -> Flask:
    """Cria a aplicação Flask.

    Args:
        config: dicionário opcional para testes. Chaves aceitas:
            `catalog`, `progress_store`, `validation_service` e
            `cloudformation_service` (instâncias prontas), `labs_dir` e
            `progress_file` (usados quando a instância não é informada),
            `session_factory` (repassado aos serviços AWS criados aqui),
            `validator_loader` (repassado ao `ValidationService` criado aqui),
            `workshop_port` (porta da allowlist de `Host` e `Origin`; padrão
            `WORKSHOP_PORT`) e `static_folder`.
    """
    config = config or {}
    app = Flask(
        __name__,
        static_folder=str(config.get("static_folder", STATIC_DIR)),
        static_url_path="/static",
    )
    app.config["DEBUG"] = False

    catalog = config.get("catalog") or LabCatalog(config.get("labs_dir"))
    store = config.get("progress_store") or ProgressStore(config.get("progress_file"))
    session_factory = config.get("session_factory")
    validation = config.get("validation_service") or ValidationService(
        catalog,
        store,
        session_factory=session_factory,
        validator_loader=config.get("validator_loader"),
    )
    cfn = config.get("cloudformation_service") or CloudFormationService(
        catalog, session_factory=session_factory
    )
    app.extensions["workshop"] = {
        "catalog": catalog,
        "progress": store,
        "validation": validation,
        "cloudformation": cfn,
    }

    register_request_guards(app, config.get("workshop_port"))

    session_env = config.get("session_env", os.environ)
    session_clock = config.get("session_clock", session_module.utcnow)

    def guard_session() -> None:
        session_module.require_active_session(session_env, session_clock)

    def require_lab(lab_id: str) -> LabMetadata:
        lab = catalog.get_lab(lab_id)
        if lab is None:
            raise LabNotFoundError(f"Lab '{lab_id}' não encontrado.")
        return lab

    def require_infrastructure(lab_id: str) -> LabMetadata:
        """Módulo sem infraestrutura responde 409 antes de qualquer chamada AWS (6.8)."""
        lab = require_lab(lab_id)
        if not lab.has_infrastructure:
            raise NoInfrastructureError(
                f"O módulo '{lab_id}' não tem infraestrutura: não há stack para criar, "
                "consultar ou excluir."
            )
        return lab

    # ------------------------------------------------------------------
    # Páginas e saúde
    # ------------------------------------------------------------------

    def serve_index():
        index = Path(app.static_folder) / "index.html"
        if not index.is_file():
            return (
                jsonify(
                    {
                        "error": True,
                        "code": "NOT_FOUND",
                        "message": "Frontend não encontrado (static/index.html).",
                        "http_status": 404,
                    }
                ),
                404,
            )
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/")
    def index():
        return serve_index()

    @app.get("/lab/<lab_id>")
    @app.get("/lab/<lab_id>/<step_id>")
    def lab_page(lab_id, step_id=None):
        return serve_index()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # ------------------------------------------------------------------
    # Catálogo
    # ------------------------------------------------------------------

    @app.get("/api/labs")
    def list_labs():
        labs = []
        for lab in catalog.get_all_labs():
            completed, total = store.get_lab_counts(lab.lab_id, lab)
            labs.append(
                {
                    "lab_id": lab.lab_id,
                    "title": lab.title,
                    "description": lab.description,
                    "difficulty": lab.difficulty,
                    "estimated_duration_minutes": lab.estimated_duration_minutes,
                    "dea_domains": lab.dea_domains,
                    "services": lab.services,
                    **_module_fields(lab),
                    "total_steps": total,
                    "completed_steps": completed,
                    "status": store.get_lab_progress(lab.lab_id)["status"],
                    "resume_step": store.get_resume_step(lab.lab_id, lab),
                }
            )
        return jsonify({"labs": labs})

    @app.get("/api/labs/<lab_id>")
    def get_lab(lab_id):
        lab = require_lab(lab_id)
        progress = store.get_lab_progress(lab_id)
        steps = []
        for step in lab.steps:
            data = _step_to_dict(step)
            if step.type not in ("task", "quiz"):
                data["content"] = catalog.get_step_single_content(lab_id, step.step_id)
            data["status"] = progress["steps"].get(step.step_id, {}).get("status", "not_visited")
            data["attempts"] = progress["steps"].get(step.step_id, {}).get("attempts", 0)
            steps.append(data)
        return jsonify(
            {
                "lab_id": lab.lab_id,
                "title": lab.title,
                "description": lab.description,
                "difficulty": lab.difficulty,
                "estimated_duration_minutes": lab.estimated_duration_minutes,
                "cost_disclaimer": lab.cost_disclaimer,
                **_module_fields(lab),
                "dea_domains": lab.dea_domains,
                "dea_tasks": lab.dea_tasks,
                "services": lab.services,
                "prerequisites": lab.prerequisites,
                "residual_resources": lab.residual_resources,
                "status": progress["status"],
                "resume_step": store.get_resume_step(lab_id, lab),
                "steps": steps,
            }
        )

    @app.post("/api/labs/<lab_id>/steps/<step_id>/visit")
    def visit_step(lab_id, step_id):
        lab = require_lab(lab_id)
        result = store.mark_visited(lab_id, step_id, lab)
        return jsonify({"lab_id": lab_id, "step_id": step_id, **result})

    @app.get("/api/labs/<lab_id>/steps/<step_id>/content")
    def step_content(lab_id, step_id):
        path = request.args.get("path")
        markdown = catalog.get_step_content(lab_id, step_id, path)
        return jsonify(
            {"lab_id": lab_id, "step_id": step_id, "path": path, "markdown": markdown}
        )

    @app.get("/api/labs/<lab_id>/steps/<step_id>/hint")
    def step_hint(lab_id, step_id):
        path = request.args.get("path")
        hint = catalog.get_step_hint(lab_id, step_id, path)
        return jsonify({"lab_id": lab_id, "step_id": step_id, "path": path, "hint": hint})

    # ------------------------------------------------------------------
    # Progresso
    # ------------------------------------------------------------------

    @app.get("/api/progress")
    def get_progress():
        return jsonify(store.get_progress())

    @app.put("/api/progress")
    def put_progress():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise InvalidPayloadError("Corpo JSON inválido.")
        return jsonify(store.apply_update(payload))

    # ------------------------------------------------------------------
    # Validação e CloudFormation
    # ------------------------------------------------------------------

    @app.post("/api/validate/<lab_id>/<step_id>")
    def validate(lab_id, step_id):
        guard_session()
        context = _json_body().get("context")
        context = context if isinstance(context, dict) else {}
        # `path` no corpo ou no context é ignorado (11.4).
        return jsonify(validation.validate(lab_id, step_id, context))

    @app.post("/api/deploy/<lab_id>")
    def deploy(lab_id):
        guard_session()
        lab = require_infrastructure(lab_id)
        return jsonify(cfn.deploy(lab_id, lab))

    @app.post("/api/teardown/<lab_id>")
    def teardown(lab_id):
        guard_session()
        require_infrastructure(lab_id)
        if _json_body().get("confirm") is not True:
            raise InvalidPayloadError(
                'Confirmação obrigatória. Envie {"confirm": true} para excluir a stack.'
            )
        return jsonify(cfn.teardown(lab_id))

    @app.get("/api/stack-status/<lab_id>")
    def stack_status(lab_id):
        guard_session()
        require_infrastructure(lab_id)
        return jsonify(cfn.get_status(lab_id))

    @app.get("/api/session")
    def get_session():
        """Estado da sessão, sem valores de credenciais (12.1)."""
        return jsonify(session_module.get_session_state(session_env, session_clock).to_dict())

    @app.after_request
    def mask_credentials_in_json(response):
        """Mascara valores de credenciais que o erro original da AWS repita (12.1)."""
        if response.mimetype == "application/json" and not response.direct_passthrough:
            data = response.get_json(silent=True)
            masked = mask_json(data)
            if masked != data:
                response.set_data(json.dumps(masked, ensure_ascii=False))
        return response

    # ------------------------------------------------------------------
    # Erros
    # ------------------------------------------------------------------

    def error_response(code: str, message: str, status: int):
        return (
            jsonify(
                {"error": True, "code": code, "message": message, "http_status": status}
            ),
            status,
        )

    @app.errorhandler(WorkshopError)
    def handle_workshop_error(exc: WorkshopError):
        return error_response(exc.code, str(exc), exc.http_status)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return error_response(
                "NOT_FOUND" if exc.code == 404 else "HTTP_ERROR",
                exc.description or exc.name,
                exc.code or 500,
            )
        log_exception(logger, "Erro inesperado")
        return error_response("INTERNAL_ERROR", "Erro interno do servidor.", 500)

    return app


app = create_app()
