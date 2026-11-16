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
3. Roda `python start.py`, que sobe os containers e abre o workshop em `http://localhost:5000`.
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

## Credenciais SSO

O container monta `~/.aws` como somente leitura. Por decisão de segurança, **a renovação do token é sempre manual e feita pelo usuário no host**: a plataforma nunca renova sessões nem grava em `~/.aws`. Quando a sessão expirar, rode `aws sso login --profile <profile>` (ou `aws login`) no seu terminal e clique em **Validar** novamente.

Para verificar, com Docker instalado e uma sessão válida:

```
aws sso login --profile <profile>
WORKSHOP_SSO_TEST_PROFILE=<profile> python -m pytest tests/integration/test_sso_readonly.py -q -rs
```

Para testar também a sessão expirada, defina `WORKSHOP_SSO_TEST_EXPIRED_PROFILE` com um profile cujo token expirou. Sem essas variáveis o teste é ignorado.

Se a sessão expirar durante um lab, renove no host (`aws sso login --profile <profile>` ou `aws login`) e clique em **Validar** novamente. A plataforma mostra o erro original da AWS seguido de uma orientação para verificar as credenciais.

Resultado do teste (2026-11-15):

- Profile testado: `Caeiro-Admin` (tipo SSO), com token válido.
- Sessão válida: dentro do container, com `~/.aws` montado como `:ro`, `sts:GetCallerIdentity` retornou sucesso. Não houve erro `Read-only file system`, nem traceback, e nenhum arquivo de `~/.aws` foi alterado (o teste compara o snapshot de caminhos e mtimes antes e depois).
- Sessão expirada: **não testada**. Não havia profile com token expirado disponível, então `test_expired_session_reports_original_aws_error` foi ignorado.
- Limite do resultado: o token estava válido. A renovação automática dentro do container não é suportada por design; com a sessão expirada, o esperado é a plataforma mostrar o erro original da AWS e o usuário renovar no host.

---

## Custos

**Os labs criam recursos reais na sua conta AWS e podem gerar cobrança.** Cada lab mostra uma estimativa de custo antes do deploy. Faça um lab por vez e sempre use **Finalizar Lab** ao terminar. A responsabilidade pelos custos da conta é sua.

---

## Segurança

- Suas credenciais ficam no seu `~/.aws`, montado como somente leitura no container. Elas não são copiadas para a imagem nem enviadas a terceiros.
- A interface fica acessível apenas em `127.0.0.1`.
- O container da aplicação não tem acesso direto à internet. Toda saída passa por um proxy que só permite domínios da AWS.
- A restrição de saída vale apenas em runtime. Os downloads do build (`docker compose build`), como o pull da imagem base e o `pip install`, ocorrem fora dessa restrição.
- O log do proxy registra horário e destino de cada conexão, sem cabeçalhos de autenticação.
- Verificado em rede real (2026-11-15, `tests/integration/test_egress.py`): `sts.amazonaws.com` e `s3.us-east-1.amazonaws.com` na porta 443 são aceitos (apenas handshake TLS, sem chamada de API). `example.com` e `amazonaws.com.evil.example` recebem 403 e aparecem no log como `TCP_DENIED/403`.
- Verificado com credenciais SSO reais (2026-11-16): dentro do container, `sts:GetCallerIdentity` via boto3 com o profile SSO funcionou e aparece no log do proxy como `TCP_TUNNEL/200 CONNECT sts.us-east-1.amazonaws.com:443`. Uma conexão TCP direta do container para `sts.amazonaws.com:443`, sem proxy, falhou (sem resolução de nome, rede `internal`). `/health` e `/api/labs` responderam pelo gateway. Nenhum recurso foi criado.

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
