# ADR-0002: Credenciais temporárias por variável de ambiente

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisões da v0.1.0 e do hotfix v0.2.1)

## Contexto
A plataforma precisa chamar a AWS para fazer deploy, validar tarefas e excluir recursos. Montar o diretório `~/.aws` no container exporia chaves de longa duração e tokens de SSO de todos os profiles da pessoa.

## Decisão
- O `start.py` exporta, no host, só as **credenciais temporárias** do profile escolhido e as entrega ao container por variáveis de ambiente do subprocesso do Docker Compose. Nada é gravado em arquivo nem impresso, só a hora de expiração.
- **Chaves de longa duração são recusadas**. Use SSO (`aws configure sso`) ou `aws login`.
- No container, `AWS_CONFIG_FILE` e `AWS_SHARED_CREDENTIALS_FILE` apontam para `/dev/null`, e o IMDS fica desativado.
- A sessão boto3 da plataforma só usa um profile nomeado quando `AWS_PROFILE` existe. Sem ela, segue a cadeia padrão do SDK e lê as credenciais do ambiente (correção da v0.2.1).
- A **renovação é manual**, no host: `aws sso login` e depois `python start.py --refresh`. A interface avisa 10 minutos antes de expirar e bloqueia as ações AWS ao expirar.

## Alternativas rejeitadas
- Montar `~/.aws` somente leitura: expõe todas as chaves e tokens.
- Renovação automática dentro do container: exigiria levar ao container um token capaz de emitir credenciais novas.

## Consequências
- Sessões curtas exigem renovar durante o estudo.
- As variáveis do container ficam visíveis a quem tem acesso ao Docker do usuário (`docker inspect`). Esse risco está documentado no README.
- Testes de container confirmam que não há `~/.aws` e que a sessão usa as credenciais do ambiente.
