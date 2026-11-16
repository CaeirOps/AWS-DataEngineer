## Descrição

<!-- O que mudou e por quê? Cite issues relacionadas. -->

## Tipo de mudança

- [ ] Lab ou conteúdo didático
- [ ] Correção de bug
- [ ] Nova funcionalidade
- [ ] Infraestrutura, CI ou dependências
- [ ] Documentação

## Checklist geral

- [ ] Todos os commits têm assinatura DCO (`git commit -s`).
- [ ] Os testes passam localmente (`python -m pytest tests/unit -q` e `node --test "tests/js/*.test.mjs"`).
- [ ] Usei apenas dados fictícios, sem dados pessoais ou de empresas reais.
- [ ] Não incluí credenciais, tokens, chaves de acesso nem IDs de conta reais, nem em exemplos, logs ou capturas de tela.
- [ ] Atualizei a documentação afetada.

## Checklist para labs

Preencha esta seção apenas se o Pull Request criar ou alterar um lab.

- [ ] Cada tarefa tem as duas trilhas: **Console** (passo a passo pelas telas) e **CLI** (comandos do AWS CLI).
- [ ] O lab inclui o **teardown** completo dos recursos criados.
- [ ] O lab informa a **estimativa de custo** antes do deploy e usa recursos de baixo custo.

## Mudanças em arquivos sensíveis

Marque se o Pull Request altera algum destes itens: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `start.py`, `check_requirements.py`, `host_credentials.py`, `gateway/`, `app/server.py`, `app/session.py`, `app/http_security.py`, `app/validators/base.py`, `requirements*.txt`, `requirements.in`, `scripts/`, `.github/`, `.gitleaks.toml`, `tests/security/`, `tests/fixtures/http_client.py`, `LICENSE*`, `NOTICE`, `SECURITY.md`.

- [ ] Este Pull Request **não** altera arquivos sensíveis.
- [ ] Este Pull Request altera arquivos sensíveis e a justificativa está abaixo.

**Justificativa (obrigatória se alterou arquivos sensíveis):**

<!-- Quais arquivos mudaram, por que a mudança é necessária e qual o impacto na segurança. -->

## Verificações de CI

- [ ] Nenhuma verificação do CI foi desativada ou contornada.
