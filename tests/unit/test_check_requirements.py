"""Testes de propriedade para check_requirements.py.

**Feature: aws-data-engineer-workshop, Property 1: Pre-requisito ausente
sempre resulta em falha descritiva**

**Validates: Requirements 1.2, 1.3**

Nenhum teste chama Docker ou AWS reais: `run`, `port_checker`, `env` e `out`
sao injetados.
"""

import io
import json
import subprocess

from hypothesis import given, settings, strategies as st

import check_requirements as cr

# Estados possiveis de cada pre-requisito. "ok" significa atendido.
DOCKER_STATES = ["ok", "old", "stopped"]
COMPOSE_STATES = ["ok", "old", "unavailable"]
AWS_STATES = ["ok", "old"]
CREDS_STATES = ["ok", "invalid"]
PORT_STATES = ["free", "busy"]

# Trecho do nome de cada pre-requisito, usado para localiza-lo na saida.
NAME = {
    "docker": "Docker >=",
    "compose": "Docker Compose",
    "aws": "AWS CLI",
    "creds": "Credenciais AWS",
    "port": "Porta",
}


def make_run(docker="ok", compose="ok", aws="ok", creds="ok",
             docker_major=24, compose_major=2, aws_major=2,
             missing=()):
    """Cria um `run` falso. `missing` lista binarios inexistentes."""

    def run(cmd):
        if cmd[0] in missing:
            raise FileNotFoundError(cmd[0])
        if cmd[:2] == ["docker", "version"]:
            if docker == "stopped":
                return 1, "", "Cannot connect to the Docker daemon"
            return 0, "%d.0.1\n" % docker_major, ""
        if cmd[:3] == ["docker", "compose", "version"]:
            if compose == "unavailable":
                return 1, "", "docker: 'compose' is not a docker command"
            return 0, "%d.20.0\n" % compose_major, ""
        if cmd[:2] == ["aws", "--version"]:
            return 0, "aws-cli/%d.15.0 Python/3.11 Linux\n" % aws_major, ""
        if cmd[:3] == ["aws", "sts", "get-caller-identity"]:
            if creds == "invalid":
                return 255, "", "The security token included in the request is expired"
            return 0, json.dumps({"Account": "123456789012"}), ""
        raise AssertionError("comando inesperado: %r" % (cmd,))

    return run


def port_checker_for(state):
    return lambda port: "Address already in use" if state == "busy" else None


def execute(run, port_state="free", env=None):
    out = io.StringIO()
    code = cr.main(
        env=env if env is not None else {},
        run=run,
        port_checker=port_checker_for(port_state),
        out=out,
    )
    return code, out.getvalue()


def assert_failure_described(output, prerequisite_keys):
    """Cada pre-requisito faltante aparece com 'Encontrado' e 'Como corrigir'."""
    blocks = output.split("[FALHA] ")[1:]
    assert len(blocks) == len(prerequisite_keys)
    for key in prerequisite_keys:
        matching = [b for b in blocks if NAME[key] in b.splitlines()[0]]
        assert len(matching) == 1, "falha de %s nao identificada" % key
        assert "Encontrado:" in matching[0]
        assert "Como corrigir:" in matching[0]
        # Passo de correcao nao vazio.
        fix = matching[0].split("Como corrigir:", 1)[1].strip()
        assert fix


# ---------------------------------------------------------------------------
# Propriedades
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    docker=st.sampled_from(DOCKER_STATES),
    compose=st.sampled_from(COMPOSE_STATES),
    aws=st.sampled_from(AWS_STATES),
    creds=st.sampled_from(CREDS_STATES),
    port=st.sampled_from(PORT_STATES),
    docker_bad=st.integers(min_value=0, max_value=cr.MIN_DOCKER_MAJOR - 1),
    docker_good=st.integers(min_value=cr.MIN_DOCKER_MAJOR, max_value=99),
    compose_bad=st.integers(min_value=0, max_value=cr.MIN_COMPOSE_MAJOR - 1),
    compose_good=st.integers(min_value=cr.MIN_COMPOSE_MAJOR, max_value=9),
    aws_bad=st.integers(min_value=0, max_value=cr.MIN_AWS_CLI_MAJOR - 1),
    aws_good=st.integers(min_value=cr.MIN_AWS_CLI_MAJOR, max_value=9),
)
def test_combinacoes_de_falhas(docker, compose, aws, creds, port,
                               docker_bad, docker_good, compose_bad,
                               compose_good, aws_bad, aws_good):
    """Exit code != 0 e cada falha identificada; tudo valido retorna 0."""
    run = make_run(
        docker=docker,
        compose=compose,
        aws=aws,
        creds=creds,
        docker_major=docker_bad if docker == "old" else docker_good,
        compose_major=compose_bad if compose == "old" else compose_good,
        aws_major=aws_bad if aws == "old" else aws_good,
    )
    code, output = execute(run, port)

    expected = []
    if docker != "ok":
        expected.append("docker")
    if compose != "ok":
        expected.append("compose")
    if aws != "ok":
        expected.append("aws")
    if creds != "ok":
        expected.append("creds")
    if port != "free":
        expected.append("port")

    if not expected:
        assert code == 0
        assert "[FALHA]" not in output
    else:
        assert code != 0
        assert_failure_described(output, expected)


@settings(max_examples=50, deadline=None)
@given(
    docker=st.integers(min_value=0, max_value=99),
    compose=st.integers(min_value=0, max_value=9),
    aws=st.integers(min_value=0, max_value=9),
)
def test_limite_de_versoes(docker, compose, aws):
    """A versao minima e aceita; abaixo dela falha, para qualquer major."""
    run = make_run(docker_major=docker, compose_major=compose, aws_major=aws)
    code, output = execute(run)
    expected = []
    if docker < cr.MIN_DOCKER_MAJOR:
        expected.append("docker")
    if compose < cr.MIN_COMPOSE_MAJOR:
        expected.append("compose")
    if aws < cr.MIN_AWS_CLI_MAJOR:
        expected.append("aws")
    assert (code == 0) == (not expected)
    if expected:
        assert_failure_described(output, expected)


# ---------------------------------------------------------------------------
# Exemplos explicitos, um por pre-requisito
# ---------------------------------------------------------------------------

def test_tudo_valido_retorna_zero():
    code, output = execute(make_run())
    assert code == 0
    assert "[FALHA]" not in output


def test_docker_abaixo_do_minimo():
    code, output = execute(make_run(docker_major=19))
    assert code == 1
    assert_failure_described(output, ["docker"])
    assert "19.0.1" in output


def test_docker_daemon_parado():
    code, output = execute(make_run(docker="stopped"))
    assert code == 1
    assert_failure_described(output, ["docker"])
    assert "daemon" in output


def test_docker_ausente_falha_docker_e_compose():
    code, output = execute(make_run(missing=("docker",)))
    assert code == 1
    assert_failure_described(output, ["docker", "compose"])


def test_compose_v1():
    code, output = execute(make_run(compose_major=1))
    assert code == 1
    assert_failure_described(output, ["compose"])


def test_compose_plugin_ausente():
    code, output = execute(make_run(compose="unavailable"))
    assert code == 1
    assert_failure_described(output, ["compose"])


def test_aws_cli_v1():
    code, output = execute(make_run(aws_major=1))
    assert code == 1
    assert_failure_described(output, ["aws"])


def test_aws_cli_ausente_falha_cli_e_credenciais():
    code, output = execute(make_run(missing=("aws",)))
    assert code == 1
    assert_failure_described(output, ["aws", "creds"])


def test_aws_cli_v1_escrevendo_versao_em_stderr():
    base = make_run()

    def run(cmd):
        if cmd[:2] == ["aws", "--version"]:
            return 0, "", "aws-cli/1.27.0 Python/3.9 Linux\n"
        return base(cmd)

    code, output = execute(run)
    assert code == 1
    assert_failure_described(output, ["aws"])


def test_credenciais_invalidas_usam_profile_informado():
    code, output = execute(make_run(creds="invalid"), env={"AWS_PROFILE": "meu"})
    assert code == 1
    assert_failure_described(output, ["creds"])
    assert "meu" in output


def test_porta_ocupada():
    code, output = execute(make_run(), port_state="busy")
    assert code == 1
    assert_failure_described(output, ["port"])
    assert "5000" in output


def test_workshop_port_invalida():
    code, output = execute(make_run(), env={"WORKSHOP_PORT": "abc"})
    assert code == 1
    assert "WORKSHOP_PORT" in output
    assert "Como corrigir:" in output


def test_timeout_do_comando_e_reportado():
    def run(cmd):
        raise subprocess.TimeoutExpired(cmd, 30)

    code, output = execute(run)
    assert code == 1
    assert_failure_described(output, ["docker", "compose", "aws", "creds"])
