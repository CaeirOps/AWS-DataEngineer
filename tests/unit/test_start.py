"""Testes de start.py (Property 15 e comportamento de polling).

Nenhum teste espera tempo real nem chama Docker: tudo e injetado.
"""

import io
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

import pytest

import host_credentials
import start
from datetime import datetime, timezone

SEGREDOS = ("AKIAFAKEKEY123456", "segredo-fake-abc", "token-fake-xyz")


def fake_creds(profile="default"):
    return host_credentials.TempCredentials(
        access_key_id=SEGREDOS[0],
        secret_access_key=SEGREDOS[1],
        session_token=SEGREDOS[2],
        expiration=datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )

# Texto arbitrario para saidas de `compose ps` e `compose logs`.
texto = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=200)


class FakeClock:
    """Relogio fake: sleep avanca o tempo e registra os intervalos."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeResp:
    def __init__(self, status):
        self.status = status

    def close(self):
        pass


def make_run(ps_out="", logs_out="", calls=None):
    calls = calls if calls is not None else []

    def run(cmd, env=None):
        calls.append(list(cmd))
        if cmd[:3] == ["docker", "compose", "ps"]:
            return 0, ps_out, ""
        if cmd[:3] == ["docker", "compose", "logs"]:
            return 0, logs_out, ""
        return 0, "", ""  # compose up

    return run, calls


def failing_opener(url, timeout=None):
    raise ConnectionRefusedError("recusada")


def run_main(env, run, opener, fc, port_checker, browser, argv=(), export=fake_creds, **extra):
    out = io.StringIO()
    # Por padrao usa um diretorio temporario para nao tocar no progress/ real.
    if "progress_dir" not in extra:
        extra["progress_dir"] = Path(tempfile.mkdtemp()) / "progress"
    code = start.main(
        env=env,
        run=run,
        opener=opener,
        clock=fc.clock,
        sleep=fc.sleep,
        browser_open=browser,
        port_checker=port_checker,
        out=out,
        argv=list(argv),
        export=export,
        **extra,
    )
    return code, out.getvalue()


# **Validates: Requirements 1.8**
@settings(max_examples=50, deadline=None)
@given(
    ps_out=texto,
    logs_out=texto,
    busy=st.one_of(st.none(), st.text(min_size=1, max_size=40)),
    port=st.integers(min_value=1, max_value=65535),
)
def test_timeout_gera_diagnostico_e_falha(ps_out, logs_out, busy, port):
    """Property 15: timeout de health gera diagnostico completo e exit code 1."""
    run, calls = make_run(ps_out, logs_out)
    fc = FakeClock()
    opened = []
    code, out = run_main(
        {"WORKSHOP_PORT": str(port)},
        run,
        failing_opener,
        fc,
        lambda p: busy,
        opened.append,
    )
    assert code == 1
    assert opened == []
    # Diagnostico completo: saidas dos comandos, porta e instrucao de encerramento.
    assert "docker compose ps" in out
    assert "docker compose logs --tail 50 workshop gateway" in out
    if ps_out.strip():
        assert ps_out.rstrip() in out
    if logs_out.strip():
        assert logs_out.rstrip() in out
    assert "Porta %d" % port in out
    if busy is None:
        assert "Livre" in out
    else:
        assert "Ocupada: %s" % busy in out
    assert "docker compose down" in out  # apenas como instrucao ao usuario
    # Nunca executa `docker compose down`.
    assert not any(c[:3] == ["docker", "compose", "down"] for c in calls)
    assert ["docker", "compose", "logs", "--tail", "50", "workshop", "gateway"] in calls


def test_polling_respeita_intervalo_e_limite():
    fc = FakeClock()
    urls = []

    def opener(url, timeout=None):
        urls.append((url, fc.now))
        raise OSError("sem resposta")

    ok = start.wait_for_health(5000, 60, 2, opener, fc.clock, fc.sleep)
    assert ok is False
    assert set(fc.sleeps) == {2}
    assert fc.now <= 60
    assert fc.now >= 58
    assert urls[0][0] == "http://127.0.0.1:5000/health"
    # Tentativas espacadas de 2 s, dentro do limite de 60 s.
    assert [t for _, t in urls] == [2.0 * i for i in range(len(urls))]
    # Sondagens em t=0, 2, ..., 60: a ultima cai exatamente no limite.
    assert len(urls) == 31
    assert urls[-1][1] == 60.0


def test_health_200_apos_algumas_tentativas():
    fc = FakeClock()
    respostas = [OSError("x"), FakeResp(503), FakeResp(200)]

    def opener(url, timeout=None):
        r = respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    assert start.wait_for_health(5000, 60, 2, opener, fc.clock, fc.sleep) is True
    assert fc.sleeps == [2, 2]


def test_sucesso_abre_browser_e_retorna_zero():
    run, calls = make_run()
    fc = FakeClock()
    opened = []
    code, out = run_main(
        {"WORKSHOP_PORT": "5050", "AWS_PROFILE": "meu"},
        run,
        lambda url, timeout=None: FakeResp(200),
        fc,
        lambda p: None,
        opened.append,
    )
    assert code == 0
    assert opened == ["http://127.0.0.1:5050"]
    assert ["docker", "compose", "up", "-d", "--build"] in calls
    assert "Profile AWS: meu" in out
    assert not any(c[:3] == ["docker", "compose", "down"] for c in calls)


def test_porta_5000_ocupada_sugere_5050():
    run, _ = make_run()
    fc = FakeClock()
    code, out = run_main(
        {}, run, failing_opener, fc, lambda p: "Address already in use", lambda u: None
    )
    assert code == 1
    assert "WORKSHOP_PORT=5050" in out
    assert "Ocupada" in out


def test_sugestao_5050_em_darwin_mesmo_com_porta_livre():
    texto_diag = start.build_diagnostics(5000, make_run()[0], lambda p: None, "darwin")
    assert "AirPlay" in texto_diag
    assert "WORKSHOP_PORT=5050" in texto_diag


def test_porta_invalida_retorna_um_sem_subir_containers():
    run, calls = make_run()
    fc = FakeClock()
    code, out = run_main({"WORKSHOP_PORT": "abc"}, run, failing_opener, fc, lambda p: None, lambda u: None)
    assert code == 1
    assert calls == []
    assert "invalida" in out


def test_falha_no_compose_up_retorna_um():
    def run(cmd, env=None):
        return 1, "", "erro de build"

    fc = FakeClock()
    code, out = run_main({}, run, failing_opener, fc, lambda p: None, lambda u: None)
    assert code == 1
    assert "erro de build" in out
    assert fc.sleeps == []


def test_up_recebe_credenciais_so_no_ambiente_e_nao_imprime_valores():
    capturado = []

    def run(cmd, env=None):
        capturado.append((list(cmd), env))
        return 0, "", ""

    fc = FakeClock()
    code, out = run_main(
        {"WORKSHOP_PORT": "5050"}, run, lambda u, timeout=None: FakeResp(200),
        fc, lambda p: None, lambda u: None,
    )
    assert code == 0
    cmd, env = capturado[0]
    assert cmd == ["docker", "compose", "up", "-d", "--build"]
    assert env["AWS_ACCESS_KEY_ID"] == SEGREDOS[0]
    assert env["AWS_SECRET_ACCESS_KEY"] == SEGREDOS[1]
    assert env["AWS_SESSION_TOKEN"] == SEGREDOS[2]
    assert env["WORKSHOP_CREDENTIALS_EXPIRATION"] == "2030-01-02T03:04:05Z"
    assert not any(s in " ".join(cmd) for s in SEGREDOS)
    assert not any(s in out for s in SEGREDOS)
    assert "2030-01-02 03:04:05" in out


def test_refresh_recria_so_o_workshop_e_faz_polling():
    run, calls = make_run()
    fc = FakeClock()
    opened = []
    code, out = run_main(
        {}, run, lambda u, timeout=None: FakeResp(200), fc, lambda p: None,
        opened.append, argv=["--refresh"],
    )
    assert code == 0
    assert calls == [
        ["docker", "compose", "up", "-d", "--force-recreate", "--no-deps", "workshop"]
    ]
    assert not any("login" in " ".join(c) for c in calls)
    assert opened == ["http://127.0.0.1:5000"]


@pytest.mark.parametrize(
    "exc",
    [
        host_credentials.LongLivedCredentialsError("longa duracao"),
        host_credentials.CredentialsExportError("falha ao exportar"),
    ],
)
def test_erro_de_credenciais_retorna_um_antes_do_compose(exc):
    run, calls = make_run()

    def export(profile):
        raise exc

    code, out = run_main(
        {}, run, failing_opener, FakeClock(), lambda p: None, lambda u: None,
        export=export,
    )
    assert code == 1
    assert calls == []
    assert str(exc) in out


def test_argumento_desconhecido_retorna_um():
    run, calls = make_run()
    code, out = run_main(
        {}, run, failing_opener, FakeClock(), lambda p: None, lambda u: None,
        argv=["--foo"],
    )
    assert code == 1
    assert calls == []


def _captura_env():
    capturado = []

    def run(cmd, env=None):
        capturado.append(env)
        return 0, "", ""

    return run, capturado


def test_cria_progress_e_exporta_uid_gid_do_usuario_no_linux(tmp_path):
    run, capturado = _captura_env()
    pasta = tmp_path / "progress"
    code, _ = run_main(
        {}, run, lambda u, timeout=None: FakeResp(200), FakeClock(),
        lambda p: None, lambda u: None,
        progress_dir=pasta, platform="linux", getuid=lambda: 1000, getgid=lambda: 1001,
    )
    assert code == 0
    assert pasta.is_dir()
    assert capturado[0]["WORKSHOP_UID"] == "1000"
    assert capturado[0]["WORKSHOP_GID"] == "1001"


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_mantem_10001_fora_do_linux(tmp_path, platform):
    run, capturado = _captura_env()
    code, _ = run_main(
        {}, run, lambda u, timeout=None: FakeResp(200), FakeClock(),
        lambda p: None, lambda u: None,
        progress_dir=tmp_path / "progress", platform=platform,
        getuid=lambda: 501, getgid=lambda: 20,
    )
    assert code == 0
    assert capturado[0]["WORKSHOP_UID"] == "10001"
    assert capturado[0]["WORKSHOP_GID"] == "10001"


def test_linux_como_root_mantem_10001():
    assert start.container_user("linux", lambda: 0, lambda: 0) == (10001, 10001)


def test_falha_ao_criar_progress_retorna_um_antes_do_compose(tmp_path):
    run, calls = make_run()
    arquivo = tmp_path / "arquivo"
    arquivo.write_text("x")
    code, out = run_main(
        {}, run, failing_opener, FakeClock(), lambda p: None, lambda u: None,
        progress_dir=arquivo / "progress",
    )
    assert code == 1
    assert calls == []
    assert "diretorio" in out
