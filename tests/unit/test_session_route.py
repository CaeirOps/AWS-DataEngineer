"""Testes de unidade da rota `GET /api/session` (Requirements 12.1, 12.2, 12.4, 12.5).

O relógio e o ambiente são injetados em `create_app`, então nada depende de
`os.environ` nem da hora real.
"""

from datetime import datetime, timezone

import pytest

from app.server import create_app
from tests.fixtures.http_client import workshop_client

NOW = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
EXPIRATION_ENV = "WORKSHOP_CREDENTIALS_EXPIRATION"


def make_client(tmp_path, env, now=NOW):
    labs = tmp_path / "labs"
    labs.mkdir(exist_ok=True)
    app = create_app(
        {
            "labs_dir": str(labs),
            "progress_file": str(tmp_path / "progress.json"),
            "session_env": env,
            "session_clock": lambda: now,
            # Porta explícita: não depende de WORKSHOP_PORT.
            "workshop_port": "5000",
        }
    )
    return workshop_client(app)


def expiration_after(seconds):
    return datetime.fromtimestamp(NOW.timestamp() + seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@pytest.mark.parametrize(
    "remaining, status",
    [
        (7200, "valid"),
        (601, "valid"),
        (600, "expiring"),
        (1, "expiring"),
        (0, "expired"),
        (-30, "expired"),
    ],
)
def test_session_status_by_remaining_seconds(tmp_path, remaining, status):
    client = make_client(tmp_path, {EXPIRATION_ENV: expiration_after(remaining)})
    response = client.get("/api/session")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == status
    assert body["seconds_remaining"] == max(0, remaining)
    assert body["expires_at"] == expiration_after(remaining)


@pytest.mark.parametrize("env", [{}, {EXPIRATION_ENV: ""}, {EXPIRATION_ENV: "ontem"}])
def test_missing_or_invalid_variable_fails_closed(tmp_path, env):
    body = make_client(tmp_path, env).get("/api/session").get_json()
    assert body == {"expires_at": None, "seconds_remaining": 0, "status": "expired"}


def test_response_has_only_expected_fields(tmp_path):
    env = {
        EXPIRATION_ENV: expiration_after(3600),
        "AWS_ACCESS_KEY_ID": "AKIAFAKEFAKEFAKEFAKE",
        "AWS_SECRET_ACCESS_KEY": "segredo-falso",
        "AWS_SESSION_TOKEN": "token-falso",
    }
    response = make_client(tmp_path, env).get("/api/session")
    assert set(response.get_json()) == {"expires_at", "seconds_remaining", "status"}
    text = response.get_data(as_text=True)
    for value in ("AKIAFAKEFAKEFAKEFAKE", "segredo-falso", "token-falso"):
        assert value not in text


def test_response_is_not_cacheable(tmp_path):
    response = make_client(tmp_path, {EXPIRATION_ENV: expiration_after(3600)}).get("/api/session")
    assert response.headers["Cache-Control"] == "no-store"
