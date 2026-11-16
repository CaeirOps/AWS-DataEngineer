"""Property 21: sessão expirada bloqueia as rotas que chamam a AWS.

**Validates: Requirements 12.2, 12.3, 12.6**

Gera expirações e relógios (passado, limite exato, até 10 min, acima de 10 min,
ausente, inválida, com e sem fuso) e verifica a classificação de `status`, a
coerência de `seconds_remaining` e que, expirada, as quatro rotas AWS devolvem
401 `SESSION_EXPIRED` sem criar sessão boto3 e sem alterar o `progress.json`.
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hypothesis import given, settings, strategies as st

from app.server import create_app
from app.session import EXPIRATION_ENV, get_session_state
from tests.fixtures import EXAMPLE_LAB_ID, LABS_FIXTURE_DIR
from tests.fixtures.http_client import PORT, workshop_client

LAB = EXAMPLE_LAB_ID
LIMIT = 600

# Valores de credencial fictícios presentes no ambiente injetado.
FAKE_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEKEYFAKEKEY12",
    "AWS_SECRET_ACCESS_KEY": "fakeSecretAccessKey/ValueForTestsOnly0123456789",
    "AWS_SESSION_TOKEN": "fakeSessionTokenValueForTestsOnly//ABCDEFGH==",
}


class SessionFactoryCalled(AssertionError):
    """Levantada se alguma rota criar a sessão boto3."""


def _failing_session_factory():
    raise SessionFactoryCalled("sessão boto3 criada com a sessão expirada")


# --- Estratégias -----------------------------------------------------------

# Relógios com fuso diferente de UTC, ou sem fuso (tratado como UTC).
_clock_base = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2090, 1, 1),
    timezones=st.sampled_from(
        [
            timezone.utc,
            timezone(timedelta(hours=-3)),
            timezone(timedelta(hours=5, minutes=30)),
        ]
    )
    | st.none(),
).map(lambda d: d.replace(microsecond=0))

# Deslocamentos em segundos entre expiração e relógio, com limites exatos.
_offsets = st.one_of(
    st.sampled_from([-1, 0, 1, 599, 600, 601]),
    st.integers(min_value=-7 * 86400, max_value=0),
    st.integers(min_value=1, max_value=LIMIT),
    st.integers(min_value=LIMIT + 1, max_value=7 * 86400),
)

# Formatos da expiração: `Z`, offset numérico, outro fuso e sem fuso (UTC).
_formats = st.sampled_from(["z", "plus0000", "minus0300", "naive"])


def _as_utc(clock: datetime) -> datetime:
    if clock.tzinfo is None:
        return clock.replace(tzinfo=timezone.utc)
    return clock.astimezone(timezone.utc)


def _format_expiration(instant_utc: datetime, fmt: str) -> str:
    if fmt == "z":
        return instant_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    if fmt == "plus0000":
        return instant_utc.strftime("%Y-%m-%dT%H:%M:%S") + "+00:00"
    if fmt == "minus0300":
        local = instant_utc.astimezone(timezone(timedelta(hours=-3)))
        return local.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"
    return instant_utc.strftime("%Y-%m-%dT%H:%M:%S")


def _expected_status(remaining: int) -> str:
    if remaining <= 0:
        return "expired"
    if remaining <= LIMIT:
        return "expiring"
    return "valid"


_invalid_values = st.one_of(
    st.just(""),
    st.just("   "),
    st.sampled_from(["não-é-data", "2024-13-45T99:00:00Z", "yesterday", "0", "None"]),
    st.text(max_size=20).filter(lambda s: _safe_invalid(s)),
)


def _safe_invalid(text: str) -> bool:
    """Descarta textos que por acaso sejam ISO 8601 válidos."""
    from app.session import _parse_expiration

    return _parse_expiration(text) is None


@st.composite
def scenarios(draw):
    """Retorna (env, clock, remaining_esperado ou None para ausente/inválida)."""
    clock = draw(_clock_base)
    kind = draw(st.sampled_from(["valid_value", "valid_value", "absent", "invalid"]))
    if kind == "absent":
        return {}, clock, None
    if kind == "invalid":
        return {EXPIRATION_ENV: draw(_invalid_values)}, clock, None
    offset = draw(_offsets)
    instant = _as_utc(clock) + timedelta(seconds=offset)
    raw = _format_expiration(instant, draw(_formats))
    return {EXPIRATION_ENV: raw}, clock, offset


def _build_app(tmp: Path, env: dict, clock: datetime):
    progress_file = tmp / "progress.json"
    full_env = {**FAKE_ENV, **env}
    app = create_app(
        {
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_file": str(progress_file),
            "session_factory": _failing_session_factory,
            "session_env": full_env,
            "session_clock": lambda: clock,
            "static_folder": str(tmp / "static"),
            # Porta fixa, independente de WORKSHOP_PORT no ambiente.
            "workshop_port": PORT,
        }
    )
    return app, progress_file


def _snapshot(path: Path):
    return path.read_bytes() if path.exists() else None


@settings(max_examples=150, deadline=None)
@given(scenarios())
def test_status_classification_and_remaining(scenario):
    """`status` e `seconds_remaining` seguem a regra da Property 21."""
    env, clock, offset = scenario
    state = get_session_state({**FAKE_ENV, **env}, lambda: clock)

    assert state.seconds_remaining >= 0
    if offset is None:
        # Ausente ou inválida: falha fechada.
        assert state.status == "expired"
        assert state.expires_at is None
        assert state.seconds_remaining == 0
    else:
        assert state.seconds_remaining == max(0, offset)
        assert state.status == _expected_status(offset)
        assert state.expires_at is not None
    # Equivalências da propriedade.
    assert (state.status == "expired") == (state.seconds_remaining <= 0)
    assert (state.status == "expiring") == (1 <= state.seconds_remaining <= LIMIT)


@settings(max_examples=60, deadline=None)
@given(scenarios())
def test_aws_routes_blocked_when_expired(scenario):
    """Expirada: quatro rotas AWS dão 401 sem boto3 e sem tocar o progress.json."""
    env, clock, offset = scenario
    with tempfile.TemporaryDirectory() as tmp_name:
        app, progress_file = _build_app(Path(tmp_name), env, clock)
        client = workshop_client(app)
        before = _snapshot(progress_file)

        session_resp = client.get("/api/session")
        assert session_resp.status_code == 200
        body = session_resp.get_json()
        assert set(body) == {"expires_at", "seconds_remaining", "status"}
        assert body["seconds_remaining"] >= 0
        raw_text = session_resp.get_data(as_text=True)
        for secret in FAKE_ENV.values():
            assert secret not in raw_text
            assert secret not in str(session_resp.headers)

        expired = offset is None or offset <= 0
        assert (body["status"] == "expired") == expired

        if expired:
            responses = [
                client.post(f"/api/validate/{LAB}/step-03", json={"context": {}}),
                client.post(f"/api/deploy/{LAB}"),
                client.post(f"/api/teardown/{LAB}", json={"confirm": True}),
                client.get(f"/api/stack-status/{LAB}"),
            ]
            for resp in responses:
                assert resp.status_code == 401
                payload = resp.get_json()
                assert payload["code"] == "SESSION_EXPIRED"
                assert payload["error"] is True
                for secret in FAKE_ENV.values():
                    assert secret not in resp.get_data(as_text=True)
            assert _snapshot(progress_file) == before
