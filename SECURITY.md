# Política de Segurança

Este documento explica como reportar vulnerabilidades no **AWS Data Engineer Workshop (DEA-C01)**.

## Escopo

Esta política cobre o código e a configuração deste repositório:

- a aplicação Flask e a interface web (`app/`);
- os scripts de inicialização e verificação (`start.py`, `check_requirements.py`, `host_credentials.py`);
- o `Dockerfile`, o `docker-compose.yml` e o gateway Squid (`gateway/`);
- os templates CloudFormation e os validadores dos labs;
- os workflows de CI e a cadeia de dependências.

Exemplos de problemas relevantes: vazamento ou escrita indevida de credenciais do `~/.aws`, saída de rede fora da allowlist do gateway, exposição da interface fora de `127.0.0.1`, execução de código ou path traversal pela API, e templates de lab que criem permissões mais amplas do que o necessário.

## Versões suportadas

Apenas a branch `main` recebe correções de segurança. Não há releases com suporte separado.

| Versão | Suportada |
|---|---|
| `main` | Sim |
| Outras branches, forks e commits antigos | Não |

## Como reportar uma vulnerabilidade

Use o **GitHub Private Vulnerability Reporting**:

1. Abra a página do repositório no GitHub.
2. Vá à aba **Security**.
3. Clique em **Report a vulnerability** e preencha o formulário.

Inclua, se possível:

- uma descrição do problema e do impacto;
- os passos para reproduzir;
- os arquivos ou componentes afetados;
- a versão (commit) em que você observou o problema.

Use apenas dados fictícios no relato. **Nunca inclua credenciais, tokens ou dados reais da sua conta AWS.**

## O que não fazer

- Não abra uma issue pública, um Pull Request ou uma discussão para descrever a vulnerabilidade.
- Não divulgue o problema publicamente antes de uma correção estar disponível ou de combinarmos um prazo.
- Não teste contra contas AWS, sistemas ou pessoas que não sejam seus.

## Prazo de resposta

Este é um projeto mantido por voluntários, então os prazos abaixo são indicativos e não um compromisso contratual:

| Etapa | Prazo indicativo |
|---|---|
| Confirmação de recebimento | até 7 dias |
| Avaliação inicial e classificação | até 14 dias |
| Correção ou plano de mitigação | até 90 dias, conforme a gravidade |

Você será informado sobre o andamento pelo próprio relato privado. Se desejar, damos o crédito pela descoberta quando a correção for publicada.

## Fora de escopo

- Custos gerados na conta AWS de quem usa os labs. Os labs criam recursos reais e a responsabilidade pelos custos é do usuário.
- Configuração da conta AWS do usuário, como permissões do profile, políticas de IAM da conta, SSO e Budgets.
- Vulnerabilidades em serviços AWS ou no AWS CLI e SDKs. Reporte-as diretamente à AWS em <https://aws.amazon.com/security/vulnerability-reporting/>.
- Vulnerabilidades em dependências de terceiros sem impacto demonstrável neste projeto. Reporte-as aos mantenedores da dependência.
- Problemas que exigem acesso prévio e privilegiado à máquina do usuário, como um host já comprometido.
- Relatos gerados por ferramentas automáticas sem uma prova de conceito aplicável ao projeto.
