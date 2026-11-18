# Contribuindo

Obrigado pelo interesse em contribuir com o **AWS Data Engineer Workshop (DEA-C01)**. Este guia descreve o processo esperado.

Para reportar uma vulnerabilidade, **não abra issue pública**. Siga o [SECURITY.md](SECURITY.md).

## Fluxo de contribuição

1. Faça um *fork* do repositório.
2. Crie uma *branch* descritiva a partir da release ativa, por exemplo `lab/04-athena` ou `fix/validator-timeout`.
3. Faça suas alterações e rode os testes localmente.
4. Assine os commits (veja [DCO](#dco)).
5. Abra um *Pull Request* para a release ativa, explicando o que mudou e por quê.

## Fluxo de trabalho (gitflow)
O fluxo completo está na seção [Fluxo de trabalho (gitflow)](README.md#fluxo-de-trabalho-gitflow) do README. As regras práticas:
- **Branch base correta:** crie a branch de trabalho (`feat/`, `fix/`, `docs/`, `chore/`, `lab/NN-`) a partir da release ativa, a branch `release/*` aberta mais recente (`git ls-remote --heads origin 'release/*'`), e abra o PR para ela. A `main` só recebe PRs de `release/vX.Y.Z` e `hotfix/vX.Y.Z`.
- **Sem release aberta:** abra uma issue antes. O mantenedor cria a release.
- **Rebase em vez de merge:** para atualizar a sua branch quando a release andar, use `git rebase origin/release/vX.Y.Z` e `git push --force-with-lease`. Não faça merge da release na sua branch.
- **Um assunto por PR:** PRs pequenos e focados são revisados mais rápido.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `test:`, `refactor:`), sempre com `git commit -s`.
- **Merge:** o único método usado é *rebase and merge*, que preserva o `Signed-off-by` de cada commit.

## Preparando o ambiente

Pré-requisitos: Python 3.9+, Docker 20+ com Docker Compose v2 e, para os testes de JavaScript, Node.js.

```
git clone <seu-fork>
cd AWS-DataEngineer
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

Para subir a plataforma localmente, use `python check_requirements.py` e depois `python start.py`.

## Rodando os testes

Testes Python:

```
python -m pytest tests/unit -q
```

Os testes em `tests/integration` precisam de Docker e, em alguns casos, de credenciais AWS válidas no host. Eles são ignorados quando as variáveis de ambiente necessárias não estão definidas. Leia o cabeçalho de cada arquivo antes de rodá-los.

Testes JavaScript (usam o test runner nativo do Node.js, sem dependências extras):

```
node --test "tests/js/*.test.mjs"
```

## DCO

Todo commit precisa da assinatura do **DCO** ([Developer Certificate of Origin](https://developercertificate.org/)). Com ela, você declara que tem o direito de enviar a contribuição sob as licenças do projeto. Use:

```
git commit -s -m "Descreva a mudança"
```

O comando adiciona ao commit uma linha como:

```
Signed-off-by: Seu Nome <seu@email.com>
```

Se esqueceu de assinar, corrija o último commit com `git commit --amend -s --no-edit`. Para vários commits, use `git rebase --signoff <base>`. O CI verifica a assinatura de todos os commits do Pull Request.

Ao contribuir, você concorda que o código enviado fica sob a Apache 2.0 e o conteúdo didático sob a CC BY-SA 4.0. Veja `LICENSE` e `LICENSE-CONTENT`.

## CI obrigatório

O CI roda em todo Pull Request e precisa passar antes do merge. Ele executa, entre outras verificações, os testes Python e JS, a checagem de DCO, a varredura de segredos, o `pip-audit`, o `hadolint`, o `cfn-lint` e o `cfn-guard`. Corrija as falhas no seu Pull Request. Não é aceito desativar ou contornar uma verificação para fazê-la passar.

## Revisão do mantenedor para arquivos sensíveis

Mudanças nos arquivos abaixo exigem revisão e aprovação do mantenedor, e a descrição do Pull Request deve explicar o que muda e o impacto na segurança:

- infraestrutura: `Dockerfile`, `docker-compose.yml`, `start.py`, `check_requirements.py`, `host_credentials.py`;
- gateway e allowlist de rede: `gateway/`;
- código que lida com sessão, credenciais e cabeçalhos HTTP em `app/`;
- dependências: `requirements.in`, `requirements.txt`, `requirements-dev.txt`;
- CI e automações: `.github/`;
- testes de segurança: `tests/security/`;
- licenças e avisos: `LICENSE`, `LICENSE-CONTENT` e `NOTICE`.

## Regenerando o `requirements.txt`

O `requirements.txt` tem hashes de todas as dependências, inclusive as transitivas, e é instalado com `pip install --require-hashes`. Não o edite à mão. Para adicionar, remover ou atualizar uma dependência:

1. Edite `requirements.in`.
2. Rode `scripts/compile-requirements.sh`, que executa `pip-compile --generate-hashes` dentro da imagem `python:3.15-slim` fixada por digest, para que o resultado seja reproduzível.
3. Faça o commit de `requirements.in` e `requirements.txt` juntos e explique a mudança no Pull Request.

## Diretrizes de conteúdo

- **Idioma:** documentação em português, preservando os termos técnicos em inglês (por exemplo *crawler*, *bucket*, *job*, *partition*).
- **Dados fictícios:** use apenas dados fictícios. Não inclua dados pessoais ou de empresas reais.
- **Sem credenciais:** nunca inclua credenciais, tokens, chaves de acesso, IDs de conta reais ou outras informações sensíveis, nem em exemplos, logs e capturas de tela.
- **Trilhas Console e CLI:** cada tarefa de lab deve ter as duas trilhas, a do **Console**, com o passo a passo pelas telas do serviço, e a do **CLI**, com os comandos do AWS CLI.
- **Teardown:** todo lab deve incluir a remoção completa dos recursos criados, para evitar custos.
- **Estimativa de custo:** informe a estimativa de custo do lab antes do deploy e prefira recursos AWS de baixo custo.

## Código de conduta

Seja respeitoso e construtivo nas issues e nos Pull Requests. Críticas devem ser sobre o código e o conteúdo, não sobre as pessoas.
