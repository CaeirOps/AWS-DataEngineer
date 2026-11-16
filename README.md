# AWS Data Engineer Workshop (DEA-C01)

[![AWS](https://img.shields.io/badge/AWS-Data%20Engineer-orange?logo=amazon-aws)](https://aws.amazon.com/certification/certified-data-engineer-associate/)
[![Código: Apache 2.0](https://img.shields.io/badge/c%C3%B3digo-Apache%202.0-blue.svg)](LICENSE)
[![Conteúdo: CC BY-SA 4.0](https://img.shields.io/badge/conte%C3%BAdo-CC%20BY--SA%204.0-lightgrey.svg)](LICENSE-CONTENT)
[![Status](https://img.shields.io/badge/status-em%20desenvolvimento-blue)](#status)

Workshop interativo, open source e *self-paced* para quem está se preparando para a certificação **AWS Certified Data Engineer - Associate (DEA-C01)**. A ideia é a mesma dos workshops oficiais da AWS: você recebe um cenário pré-configurado, constrói a solução na sua própria conta AWS e uma validação automática confere se o desafio foi resolvido.

> Documentação em **português**, preservando os termos técnicos em inglês.

---

## Status

**Em desenvolvimento.** A plataforma ainda não está pronta para uso. Os requisitos, o design técnico e o plano de implementação estão versionados em `.kiro/specs/aws-data-engineer-workshop/`.

---

## Como vai funcionar

1. Você clona o repositório.
2. Roda `python check_requirements.py` para validar o ambiente local.
3. Roda `python start.py`, que exporta as credenciais temporárias do seu profile, sobe os containers e abre o workshop em `http://localhost:5000`.
4. Em cada lab, faz o deploy do cenário (CloudFormation), executa as tarefas na sua conta AWS e clica em **Validar**.
   Cada tarefa tem duas trilhas: **Console**, com o passo a passo pelas telas do serviço, e **CLI**, com os comandos do AWS CLI. Você escolhe a que preferir e pode alternar a qualquer momento.
5. Ao terminar, clica em **Finalizar Lab** para remover a infraestrutura e evitar custos.

Tudo roda localmente. Não há servidor externo, login ou coleta de dados.

---

## Laboratórios planejados

A progressão vai do iniciante absoluto ao pipeline completo, cobrindo os quatro domínios do [guia oficial do exame](https://docs.aws.amazon.com/aws-certification/latest/data-engineer-associate-01/data-engineer-associate-01.html).

| Lab | Tema | Domínio | Nível |
|---|---|---|---|
| 01 | Fundamentos de S3 e Data Lake | D2 | ⭐ |
| 02 | Catalogação e descoberta de dados (Glue Crawler, Data Catalog) | D2 | ⭐⭐ |
| 03 | Transformação ETL com AWS Glue e PySpark | D1 | ⭐⭐ |
| 04 | Consultas analíticas com Athena | D3 | ⭐⭐ |
| 05 | Qualidade de dados com Glue DataBrew | D3 | ⭐⭐⭐ |
| 06 | Ingestão de streaming com Kinesis | D1 | ⭐⭐⭐ |
| 07 | Data Warehouse com Redshift | D2 | ⭐⭐⭐ |
| 08 | Orquestração com Step Functions e EventBridge | D3 | ⭐⭐⭐⭐ |
| 09 | Segurança e governança (Lake Formation, KMS, Macie, CloudTrail) | D4 | ⭐⭐⭐⭐ |
| 10 | Pipeline end-to-end | D1-D4 | ⭐⭐⭐⭐⭐ |

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

**Os labs criam recursos reais na sua conta AWS e podem gerar cobrança.** Cada lab mostra uma estimativa de custo antes do deploy. Faça um lab por vez e sempre use **Finalizar Lab** ao terminar. A responsabilidade pelos custos da conta é sua.

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
2. Crie uma *branch* descritiva, por exemplo `lab/04-athena`.
3. Abra um *Pull Request* explicando o que foi adicionado.

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
