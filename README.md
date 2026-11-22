# AWS Data Engineer Workshop (DEA-C01)

[![AWS](https://img.shields.io/badge/AWS-Data%20Engineer-orange?logo=amazon-aws)](https://aws.amazon.com/certification/certified-data-engineer-associate/)
[![Código: Apache 2.0](https://img.shields.io/badge/c%C3%B3digo-Apache%202.0-blue.svg)](LICENSE)
[![Conteúdo: CC BY-SA 4.0](https://img.shields.io/badge/conte%C3%BAdo-CC%20BY--SA%204.0-lightgrey.svg)](LICENSE-CONTENT)
[![Status](https://img.shields.io/badge/status-em%20desenvolvimento-blue)](#status)

Workshop interativo, open source e *self-paced* para quem está se preparando para a certificação **AWS Certified Data Engineer - Associate (DEA-C01)**. A ideia é a mesma dos workshops oficiais da AWS: você recebe um cenário pré-configurado, constrói a solução na sua própria conta AWS e uma validação automática confere se o desafio foi resolvido.

> Documentação em **português**, preservando os termos técnicos em inglês.

---

## Status

**Plataforma pronta (v0.2.0), módulos em produção.** A plataforma já tem catálogo de módulos, trilhas Console e CLI, validação automática, Verificação de conhecimento, Simulado, prática opcional e Aviso de custo. Os 19 módulos estão sendo escritos um por vez, cada um revisado pelo mantenedor antes de entrar. Os requisitos, o design técnico e o plano de implementação estão em `.kiro/specs/aws-data-engineer-workshop/`.

---

## Como funciona

1. Você clona o repositório.
2. Roda `python check_requirements.py` para validar o ambiente local.
3. Roda `python start.py`, que exporta as credenciais temporárias do seu profile, sobe os containers e abre o workshop em `http://localhost:5000` (ou na porta definida em `WORKSHOP_PORT`).
4. Cada módulo segue a mesma sequência: objetivos com as skills do exame, conceitos intercalados com práticas, Verificação de conhecimento e resumo com links para a documentação oficial. Você lê a teoria e executa a prática ao mesmo tempo.
5. Nas práticas, faz o deploy do cenário (CloudFormation), executa a tarefa na sua conta AWS e clica em **Validar**.
   Cada tarefa tem duas trilhas: **Console**, com o passo a passo pelas telas do serviço, e **CLI**, com os comandos do AWS CLI. Você escolhe a que preferir e pode alternar a qualquer momento.
6. Ao terminar, clica em **Finalizar Lab** para remover a infraestrutura e evitar custos.

Tudo roda localmente. Não há servidor externo, login ou coleta de dados. O cenário de todos os módulos é a **AnyCompany**, uma empresa fictícia de varejo, com dados fictícios.

---

## Módulos

A progressão vai dos fundamentos ao projeto final e cobre as 120 skills dos quatro domínios do [guia oficial do exame](https://docs.aws.amazon.com/aws-certification/latest/data-engineer-associate-01/data-engineer-associate-01.html). A relação entre skills e módulos está na Matriz de cobertura, em `docs/exam-coverage.json`. Para ver o resumo, rode `python scripts/coverage_report.py`.

| Módulo | Tema | Domínios |
|---|---|---|
| 00 | Fundamentos de engenharia de dados (só teoria, sem custo) | D1, D2 |
| 01 | S3 e data lake | D2, D1 |
| 02 | Catálogo de dados | D2 |
| 03 | Athena e SQL analítico | D3 |
| 04 | ETL com Glue e PySpark | D1, D3 |
| 05 | EMR Serverless e escolha do motor de processamento | D1, D3 |
| 06 | Qualidade de dados | D3 |
| 07 | Streaming | D1 |
| 08 | DynamoDB e bancos operacionais | D2, D1 |
| 09 | Migração e CDC | D1, D2, D4 |
| 10 | Redshift | D2, D3, D4 |
| 11 | Open table formats | D2 |
| 12 | Orquestração | D1, D3 |
| 13 | Observabilidade e operação | D3, D4 |
| 14 | Segurança | D4 |
| 15 | Governança | D4 |
| 16 | Dados para IA | D1, D2 |
| 17 | Data APIs, IaC e CI/CD | D1, D3 |
| 18 | Projeto final | D1, D2, D3, D4 |

Na interface e na API, cada módulo usa o identificador `lab-NN` (por exemplo `lab-03`).

### Verificação de conhecimento

Cada módulo termina com questões no formato do exame:
- **Escolha única:** uma alternativa correta entre quatro.
- **Múltipla escolha:** duas ou mais alternativas corretas entre cinco ou mais. A questão só conta como certa se você marcar exatamente as corretas, como na prova.

O gabarito fica no servidor e só aparece depois do envio, com a explicação de cada alternativa. A nota mínima padrão é 70%, as tentativas são ilimitadas e o quiz não usa a AWS.

### Simulado final

O Simulado sorteia questões das Verificações de conhecimento de todos os módulos, sem repetição. Por padrão são 65 questões, com a distribuição de domínios do exame: D1 34%, D2 26%, D3 22% e D4 18%.
- O cronômetro de 130 minutos é opcional.
- O resultado mostra a nota geral, a nota por domínio e as explicações.
- As 20 tentativas mais recentes ficam no histórico.
- Se faltarem questões em algum domínio, o sorteio completa com os outros domínios e avisa na tela.

---

## Pré-requisitos

- Conta AWS própria, com acesso administrativo
- Docker 20+ com Docker Compose v2
- AWS CLI v2 com um profile configurado (`aws configure`, `aws configure sso` ou `aws login`)
- Python 3.9+ no host, usado apenas pelos scripts de verificação e inicialização (sem pacotes extras)
- Conhecimento básico de SQL, linha de comando e Git

---

## Credenciais AWS

O `python start.py` lê o profile escolhido (`AWS_PROFILE`, padrão `default`), exporta somente as **credenciais temporárias** dele e as entrega ao container por variável de ambiente. Nada de `~/.aws` é montado no container, e as credenciais não são gravadas em arquivo nem impressas; o script mostra apenas a hora de expiração.

- Chaves de longa duração (access key de usuário IAM) são recusadas. Use um profile SSO (`aws configure sso`) ou `aws login`.
- A renovação é sempre manual e feita no host. Quando a sessão expirar, rode `aws sso login --profile <profile>` (ou `aws login`) e depois `python start.py --refresh`, que recria apenas o serviço `workshop` com as novas credenciais.
- O cronômetro no cabeçalho da interface avisa quando faltam 10 minutos e bloqueia as ações AWS (deploy, validação, finalização) ao expirar.

## Custos

**As práticas criam recursos reais na sua conta AWS e podem gerar cobrança.** A responsabilidade pelos custos da conta é sua.

- **Aviso de custo:** antes do deploy, o módulo lista os serviços cobrados, cada um com o link da página oficial de preços em `aws.amazon.com`. O workshop não mostra valores em USD. Uma estimativa só seria confiável com premissas de uso revisadas, e a AWS Pricing Calculator pública não tem API para gerar estimativas (veja [Melhorias futuras](#melhorias-futuras)).
- **Prática opcional:** serviços de custo mais alto (por exemplo Amazon MWAA, Amazon MSK, Amazon OpenSearch Service e Amazon QuickSight) ficam em práticas marcadas como **Opcional**, com um aviso de custo reforçado. Você pode pulá-las e concluir o módulo mesmo assim.
- **Sem custo:** o Módulo 00, as Verificações de conhecimento e o Simulado não usam a AWS.
- Faça um módulo por vez e sempre use **Finalizar Lab** ao terminar.

---

## Segurança

- Suas credenciais de longa duração ficam no host. O container recebe apenas credenciais temporárias, por variável de ambiente, e não há volume de credenciais.
- A interface fica acessível apenas em `127.0.0.1`.
- A API local rejeita requisições de outros sites (valida `Host` e `Origin`), o que protege contra páginas maliciosas abertas no seu browser.
- O container da aplicação roda como usuário não root, com sistema de arquivos somente leitura e sem capabilities extras.
- O container não tem acesso direto à internet. Toda saída passa por um proxy (gateway) que só permite domínios da AWS, definidos em `gateway/allowlist.txt`.
- A restrição de saída vale apenas em runtime. Os downloads do build (`docker compose build`), como o pull da imagem base e o `pip install`, ocorrem fora dela.
- O log do proxy registra horário e destino de cada conexão, sem cabeçalhos de autenticação.

---

## Recomendações de segurança para sua conta AWS

As recomendações abaixo seguem a documentação oficial da AWS. Elas reduzem o impacto de qualquer problema durante o uso do workshop, inclusive de um erro seu num lab.

- **Use uma conta AWS dedicada ao workshop**, separada de contas com dados reais. Uma opção é criar uma conta de sandbox como [member account no AWS Organizations](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_accounts_create.html). Assim, o que existe na conta é só o que o workshop criou.
- **Configure um alerta no AWS Budgets** para ser avisado antes de o custo passar do esperado. Veja [Creating a budget](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-create.html).
- **Use um permission set com o mínimo necessário** em vez de `AdministratorAccess`, sempre que possível. Se um lab exigir mais permissões, use temporariamente um permission set mais amplo. Veja [Manage AWS accounts with permission sets](https://docs.aws.amazon.com/singlesignon/latest/userguide/permissionsetsconcept.html) e [Apply least-privilege permissions](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege).
- **Prefira sessões curtas.** A duração da sessão é definida no permission set ([Set session duration for AWS accounts](https://docs.aws.amazon.com/singlesignon/latest/userguide/howtosessionduration.html)). Quando a sessão expirar, renove no host (`aws sso login --profile <profile>` ou `aws login`) e rode `python start.py --refresh`.
- **Ative o MFA** para os usuários que acessam a conta, incluindo o root user. Veja [AWS Multi-factor authentication in IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa.html) e [Security best practices in IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html).

### Risco residual

A Allowlist por domínio impede que o container se comunique com sites fora da AWS. Ela não impede que um código malicioso envie dados para um recurso AWS de terceiros, como um bucket S3 de outra conta, porque esse destino também está em `*.amazonaws.com`. A mitigação é combinar conta isolada, privilégio mínimo e sessão curta: assim, há pouco para ser enviado e pouco tempo para isso.

Além disso, as variáveis de ambiente do container ficam visíveis a quem tem acesso ao Docker do seu usuário no host (por exemplo, via `docker inspect`). Use o workshop numa máquina que só você controla.

### Portal SSO

O container não precisa acessar o portal SSO (`portal.sso.*`). Ele recebe somente as credenciais temporárias já emitidas pelo `start.py`, e o login no portal acontece no host.

---

## Como contribuir

1. Faça um *fork* do repositório.
2. Descubra a release ativa e crie sua *branch* a partir dela, por exemplo `lab/04-athena` (veja o [fluxo de trabalho](#fluxo-de-trabalho-gitflow)).
3. Abra um *Pull Request* para a release ativa, explicando o que foi adicionado.

Todo commit precisa da assinatura do **DCO** ([Developer Certificate of Origin](https://developercertificate.org/)). Com ela, você declara que tem o direito de enviar a contribuição sob as licenças do projeto. Basta usar `git commit -s`, que adiciona ao commit uma linha como:

```
Signed-off-by: Seu Nome <seu@email.com>
```

Ao contribuir, você concorda que o código enviado fica sob a Apache 2.0 e o conteúdo didático sob a CC BY-SA 4.0.

**Diretrizes:**
- Documentação em português, termos técnicos em inglês.
- Apenas dados fictícios.
- Nunca inclua credenciais, tokens ou informações sensíveis.
- Prefira recursos AWS de baixo custo e sempre inclua o teardown.

### Fluxo de trabalho (gitflow)

O projeto usa um GitFlow simplificado com branches de release. A `main` é a única branch permanente e está sempre estável. Cada versão é integrada em uma branch `release/vX.Y.Z`, e o trabalho do dia a dia chega a ela por Pull Requests.

```
main       o-----------------------------o---------->  (tag vX.Y.Z)
            \                           /
release      o---o---o---o---o---o---o              (release/vX.Y.Z)
                  \     /     \     /
trabalho           o---o       o---o                (feat/, fix/, docs/, chore/, lab/NN-)
```

| Branch | Criada a partir de | Destino do PR | Quando apagar |
|---|---|---|---|
| `main` | n/a | recebe PRs de `release/vX.Y.Z`, `hotfix/vX.Y.Z` e do Dependabot | nunca |
| `release/vX.Y.Z` | `main` | `main` | depois do merge na `main` |
| `feat/<descricao>`, `fix/<descricao>`, `docs/<descricao>`, `chore/<descricao>`, `lab/NN-<descricao>` | release ativa | release ativa | depois do merge na release |
| `hotfix/vX.Y.Z` | `main` | `main` | depois do merge; a correção é levada também para a release ativa |

A `main` só aceita PR com os checks verdes. A release ativa é a branch `release/*` aberta mais recente:

```
git ls-remote --heads origin 'release/*'
```

Se não houver release aberta, abra uma issue antes. O mantenedor cria a release.

**Passo a passo de uma contribuição:**

1. Faça um *fork* e clone o seu fork.
2. Descubra a release ativa e crie a branch de trabalho a partir dela, por exemplo `git switch -c lab/04-athena origin/release/vX.Y.Z`.
3. Faça os commits com `git commit -s`, no padrão Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `test:`, `refactor:`).
4. Abra o Pull Request para a release ativa, não para a `main`.
5. Aguarde o CI ficar verde e corrija o que falhar.
6. Se a release andar enquanto o PR está aberto, atualize a sua branch com `git rebase origin/release/vX.Y.Z` e envie com `git push --force-with-lease`. Não use merge para atualizar a branch.

**Método de merge:** o único método usado é *rebase and merge*. Ele preserva cada commit com o próprio `Signed-off-by` e mantém o histórico linear. O *squash* cria um commit novo com o e-mail padrão do GitHub do autor, que pode divergir do sign-off e quebrar o DCO. O *merge commit* quebra o histórico linear.

**Como nasce uma release:** a branch `release/vX.Y.Z` é criada no mesmo commit da `main`, sem commits próprios. As regras da branch exigem os checks do CI, e um push que já traz commits novos é recusado (`GH013`, *required status checks are expected*). Por isso, o mantenedor cria a branch apontando para a `main` e leva as mudanças por Pull Request:

```
git fetch origin
git push origin origin/main:refs/heads/release/vX.Y.Z
```

**Como sai uma versão:**

1. O mantenedor abre o PR de `release/vX.Y.Z` para a `main`.
2. Com o CI verde, o PR é integrado por *rebase and merge*.
3. O mantenedor cria a tag anotada `vX.Y.Z` (SemVer) na `main` e publica o GitHub Release com as notas.
4. A branch da release é apagada.

---

## Melhorias futuras

- **Prática opcional de crawler JDBC no Módulo 02.** Foi testada na conta com Amazon Aurora PostgreSQL Serverless v2, RDS Data API, secret gerenciado pelo RDS e conexão do Glue na VPC, e não funcionou: o crawler falhou com `Test connection failed` sem chegar ao banco, e com driver JDBC próprio falhou com `JDBC connection not found`. A prática foi retirada para o módulo não publicar um passo que não funciona. As skills 2.2.5 e 1.2.2 seguem cobertas pela teoria e pela Verificação de conhecimento, e voltam com prática no Módulo 09 (migração e CDC).
- **Estimativa de custo em USD por módulo.** A ideia é gerá-la por script a partir do AWS Price List API (`pricing:GetProducts`, somente leitura), com premissas de uso versionadas e revisadas, cálculo determinístico e data da consulta. Ela só entra quando o método for reprodutível e revisado pelo mantenedor. Até lá, o Aviso de custo mostra os serviços cobrados e as páginas oficiais de preços.

---

## Licença

O projeto usa duas licenças, uma para o código e outra para o conteúdo didático.

| Parte | Licença | Arquivo |
|---|---|---|
| Código e configuração: Python, JavaScript, CSS, HTML, Dockerfile, Compose, Squid, templates CloudFormation, `metadata.json` | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) | [LICENSE](LICENSE) |
| Conteúdo didático: arquivos Markdown (incluindo este README) e tudo em `labs/**/assets/` | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.pt-br) | [LICENSE-CONTENT](LICENSE-CONTENT) |

Comandos e trechos de código dentro dos arquivos Markdown também podem ser usados sob a Apache 2.0, para que você possa copiá-los para seus próprios scripts.

### Usando ou adaptando este projeto

Você pode usar, copiar, modificar e redistribuir o projeto, inclusive para fins comerciais, desde que:

- **Código:** mantenha os arquivos `LICENSE` e `NOTICE` e indique nos arquivos alterados que eles foram modificados.
- **Conteúdo:** dê crédito ao projeto original, coloque o link para ele, indique o que mudou e publique a sua adaptação também sob a CC BY-SA 4.0.

Sugestão de crédito:

> Baseado em [AWS Data Engineer Workshop (DEA-C01)](https://github.com/CaeirOps/AWS-DataEngineer), de Ricardo Caeiro e contribuidores, licenciado sob CC BY-SA 4.0 (conteúdo) e Apache 2.0 (código).

As licenças não dão direito de uso do nome do projeto. Pedimos que forks usem um nome próprio e deixem claro que são uma versão derivada.

## Aviso de marca

Este projeto é independente e não é afiliado, patrocinado ou endossado pela Amazon Web Services, Inc. ou suas afiliadas. Amazon Web Services, AWS e as marcas relacionadas são marcas registradas da Amazon.com, Inc. ou de suas afiliadas.

## Autor

**Ricardo Caeiro** - [@CaeirOps](https://github.com/CaeirOps)
