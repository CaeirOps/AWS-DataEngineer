# Requirements Document

## Introduction

Este documento define os requisitos para a Plataforma de Workshop AWS Data Engineer: uma plataforma de treinamento interativa, open source e self-paced voltada para a comunidade AWS brasileira. A plataforma prepara candidatos para a certificação AWS Certified Data Engineer - Associate (DEA-C01) por meio de 10 laboratórios práticos que utilizam recursos reais na AWS. A solução é distribuída via `git clone` e executada localmente com Docker Compose, sem autenticação, sem servidor externo e sem rastreamento de dados do usuário.

## Glossary

- **Plataforma**: A aplicação web local composta por Flask (backend), HTML/CSS/JS estático (frontend) e scripts Python de validação.
- **Workshop**: O conjunto completo de 10 laboratórios de treinamento para a certificação DEA-C01.
- **Lab**: Um laboratório individual contendo cenário, steps, validações e recursos de infraestrutura CloudFormation.
- **Step**: Uma etapa atômica dentro de um lab, com cenário, tarefa e botão de validação.
- **Validador**: O módulo Python com boto3 que verifica o estado real dos recursos AWS para um determinado step.
- **Dashboard**: A tela inicial da plataforma que exibe o progresso consolidado de todos os labs.
- **Progress Store**: O arquivo `progress.json` armazenado em volume local (gitignored) que persiste o estado de progresso do usuário.
- **check_requirements.py**: Script Python de pré-validação que verifica Docker, Docker Compose, AWS CLI, credenciais e porta do host antes da inicialização, usando somente a biblioteca padrão do Python e o AWS CLI.
- **Flask App**: O servidor web Python (Flask) executado em container Docker que serve o frontend estático e expõe a API de validação.
- **CloudFormation Stack**: A stack de infraestrutura AWS provisionada por template CloudFormation para cada lab.
- **Domínio DEA-C01**: Um dos quatro domínios de conhecimento do exame AWS Certified Data Engineer - Associate (D1, D2, D3, D4).
- **Dica Detalhada**: Conteúdo de ajuda contextual exibido ao usuário após falhas consecutivas na validação de um step.
- **Gateway**: Container que publica a interface em 127.0.0.1 e atua como egress proxy com allowlist de domínios AWS.
- **Allowlist**: Arquivo versionado com os domínios de saída permitidos.
- **start.py**: Script de inicialização no host (somente biblioteca padrão do Python) que obtém credenciais temporárias do profile escolhido, sobe os containers, aguarda o health check e abre o browser.
- **Credenciais temporárias**: Credenciais AWS com `SessionToken` e `Expiration`, exportadas pelo AWS CLI no host (`aws configure export-credentials --format process`) e entregues ao container `workshop` somente por variáveis de ambiente.
- **Sessão**: Período de validade das credenciais temporárias em uso pelo container `workshop`, que termina em `Expiration`.
- **Cabeçalho de requisição própria**: Cabeçalho `X-Workshop-Request: 1`, enviado pelo frontend em requisições que alteram estado.
- **Trilha**: Modo de execução das tarefas de um step.
- **Trilha Console**: Instruções passo a passo pelo AWS Management Console, com navegação entre telas, menus e opções do serviço.
- **Trilha CLI**: Instruções com comandos do AWS CLI v2.

## Requirements

### Requirement 1: Distribuição e Inicialização

**User Story:** Como desenvolvedor interessado na certificação DEA-C01, quero clonar o repositório e iniciar a plataforma com um único comando, para que eu possa começar a praticar sem configuração complexa.

#### Acceptance Criteria

1. THE Plataforma SHALL ser distribuída exclusivamente via repositório Git público, sem dependência de registro de pacotes externo.
2. WHEN o usuário executa `python check_requirements.py`, THE check_requirements.py SHALL usar somente a biblioteca padrão do Python e o AWS CLI, sem exigir instalação de pacotes no host, e SHALL verificar: Docker versão 20 ou superior com daemon em execução, Docker Compose v2, AWS CLI versão 2 ou superior, credenciais temporárias válidas para o profile em uso (via `aws sts get-caller-identity` e `aws configure export-credentials`) e porta do host (`WORKSHOP_PORT`) livre.
3. IF o check_requirements.py detectar qualquer pré-requisito ausente ou inválido, THEN THE check_requirements.py SHALL exibir mensagem de erro descritiva identificando o pré-requisito faltante e os passos para corrigi-lo, interrompendo a execução.
4. WHEN o usuário executa `python start.py`, THE start.py SHALL iniciar os containers em segundo plano e consultar o endpoint `/health` até obter resposta de sucesso por no máximo 60 segundos.
5. WHEN o usuário executa `python start.py`, THE start.py SHALL obter credenciais temporárias somente do profile definido em `AWS_PROFILE`, por meio de `aws configure export-credentials --profile "$AWS_PROFILE" --format process`, e SHALL entregá-las ao container `workshop` exclusivamente pelas variáveis de ambiente `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` e `WORKSHOP_CREDENTIALS_EXPIRATION`, sem gravar credenciais em disco (inclusive em arquivo `.env` temporário), sem imprimi-las e sem copiá-las para a imagem Docker.
6. THE Flask App SHALL montar um volume local para o arquivo `progress.json`, preservando o progresso entre reinicializações do container.
7. THE Plataforma SHALL licenciar o código e os arquivos de configuração sob a Apache License 2.0 (arquivos `LICENSE` e `NOTICE`) e o conteúdo didático (arquivos Markdown e `labs/**/assets/`) sob a Creative Commons Attribution-ShareAlike 4.0 International (arquivo `LICENSE-CONTENT`).
8. IF o endpoint `/health` não responder com sucesso em 60 segundos, THEN THE start.py SHALL exibir diagnóstico com o estado dos containers, as últimas 50 linhas de log, o resultado da verificação de porta em uso e as causas comuns conhecidas, e encerrar com código de saída diferente de zero, mantendo os containers para inspeção e informando o comando para encerrá-los.
9. THE Plataforma SHALL permitir configurar a porta do host pela variável de ambiente `WORKSHOP_PORT`, com valor padrão 5000.
10. IF o container da aplicação falhar repetidamente, THEN THE Plataforma SHALL limitar as reinicializações automáticas a 3 tentativas, evitando loop infinito de restart.
11. WHEN o endpoint `/health` responder com sucesso, THE start.py SHALL exibir a URL de acesso e abrir o browser padrão do usuário.
12. THE Plataforma SHALL usar o profile AWS definido pela variável `AWS_PROFILE` (padrão `default`) no check_requirements.py e no start.py, no host, e SHALL NOT repassar `AWS_PROFILE` nem montar `~/.aws` no container `workshop`, que usa somente as credenciais temporárias recebidas por variáveis de ambiente e a região de `AWS_DEFAULT_REGION`.
13. THE Plataforma SHALL exigir a assinatura DCO (`Signed-off-by`) em todos os commits de contribuições.
14. IF a exportação de credenciais do profile não retornar `SessionToken` e `Expiration` (credenciais de longa duração), THEN THE start.py e THE check_requirements.py SHALL recusar as credenciais, interromper a execução com código de saída diferente de zero e exibir mensagem pedindo o uso de AWS IAM Identity Center (SSO) ou `aws login`.
15. WHEN o usuário executa `python start.py --refresh`, THE start.py SHALL exportar novamente as credenciais temporárias do profile e recriar somente o serviço `workshop` com `docker compose up -d --force-recreate --no-deps workshop`, preservando o volume de progresso e o serviço `gateway`.
16. THE Plataforma SHALL documentar que a renovação do login (SSO ou `aws login`) é sempre manual e feita pelo usuário no host, e que o container `workshop` não acessa `portal.sso.*` nem qualquer outro endpoint de login.

---

### Requirement 2: Dashboard de Progresso

**User Story:** Como usuário da plataforma, quero visualizar meu progresso consolidado ao acessar a tela inicial, para que eu saiba quais labs já completei e onde posso retomar meu aprendizado.

#### Acceptance Criteria

1. WHEN o usuário acessa `http://localhost:${WORKSHOP_PORT}` (padrão 5000), THE Dashboard SHALL exibir todos os 10 labs com seus respectivos títulos, domínios DEA-C01 e níveis de complexidade.
2. THE Dashboard SHALL exibir, para cada lab, o número de steps concluídos sobre o total de steps disponíveis.
3. THE Dashboard SHALL identificar visualmente o ponto de retomada de cada lab iniciado mas não concluído.
4. WHEN o usuário clica em um lab no Dashboard, THE Plataforma SHALL navegar para o step mais recente não concluído daquele lab, ou para o primeiro step caso o lab ainda não tenha sido iniciado.
5. THE Progress Store SHALL persistir o estado de progresso localmente no arquivo `progress.json` em volume Docker, sem transmitir dados do usuário para servidores externos.
6. WHEN o usuário avança de um step que não é do tipo tarefa, THE Plataforma SHALL registrar esse step como concluído no Progress Store, sem contar tentativa de validação, de modo que o ponto de retomada do lab avance para o próximo step não concluído.

---

### Requirement 3: Navegação por Wizard

**User Story:** Como usuário da plataforma, quero navegar livremente entre os steps de um lab, para que eu possa revisitar etapas anteriores ou pular para steps que já visitei.

#### Acceptance Criteria

1. THE Plataforma SHALL apresentar os steps de cada lab em formato wizard com navegação sequencial e lateral.
2. WHEN o usuário já visitou um step anteriormente, conforme o status registrado no Progress Store, THE Plataforma SHALL permitir navegação direta para aquele step a partir do indicador de progresso do wizard.
3. WHILE o usuário estiver no primeiro step de um lab, THE Plataforma SHALL desabilitar o botão de navegação para o step anterior.
4. WHILE o usuário estiver no último step de um lab, THE Plataforma SHALL exibir o botão "Finalizar Lab" em substituição ao botão de avanço.
5. THE Plataforma SHALL refletir em tempo real no indicador de progresso do wizard o status (concluído, em andamento, não visitado) de cada step.
6. WHILE o usuário estiver em um step intermediário de um lab, THE Plataforma SHALL exibir o botão "Avançar" e ocultar o botão "Finalizar Lab", de modo que exatamente uma ação de navegação de avanço esteja visível e ativa.

---

### Requirement 4: Exibição de Laboratório

**User Story:** Como usuário da plataforma, quero ler o cenário e as instruções de cada step com clareza, para que eu saiba exatamente o que precisa ser feito na minha conta AWS.

#### Acceptance Criteria

1. THE Plataforma SHALL exibir, para cada step, um cenário narrativo contextualizado, as tarefas a serem executadas na AWS, apresentadas nas duas Trilhas conforme o Requirement 11, e os critérios de aceitação esperados.
2. THE Plataforma SHALL exibir um disclaimer de custos AWS obrigatório no início de cada lab, antes de qualquer step de provisionamento de recursos.
3. THE Plataforma SHALL exibir a estimativa de custo (calculada via AWS Pricing Calculator) para cada lab antes de o usuário iniciar o provisionamento de infraestrutura.
4. THE Plataforma SHALL exibir os domínios DEA-C01 cobertos por cada lab (D1, D2, D3, D4) com as respectivas tasks do exame.
5. THE Plataforma SHALL preservar os termos técnicos em inglês na documentação redigida em português.

---

### Requirement 5: Validação Automatizada de Steps

**User Story:** Como usuário da plataforma, quero validar se executei corretamente as tarefas na AWS clicando em um botão, para que eu receba feedback imediato sobre minha solução.

#### Acceptance Criteria

1. WHEN o usuário clica no botão "Validar" de um step, THE Validador SHALL executar verificações via boto3 contra o estado real dos recursos na conta AWS do usuário.
2. WHEN a validação de um step for bem-sucedida, THE Validador SHALL retornar o status "passou" com mensagem de confirmação e marcar o step como concluído no Progress Store.
3. WHEN a validação de um step falhar, THE Validador SHALL retornar o status "falhou" com mensagem descritiva identificando qual critério não foi atendido.
4. THE Plataforma SHALL permitir retry ilimitado de validação sem penalidade para o usuário.
5. WHEN o usuário falhar na validação de um step por X vezes consecutivas (configurável por lab), THE Plataforma SHALL exibir o botão "Ver Dica Detalhada" com orientações contextuais para aquele step específico.
6. IF uma chamada AWS do Validador falhar por erro de credenciais (credenciais ausentes, inválidas ou expiradas), THEN THE Validador SHALL retornar o código e a mensagem de erro originais da chamada AWS, sem alteração, acompanhados da sugestão de verificar as credenciais AWS do profile em uso e de renovar o login no host e executar `python start.py --refresh`, sem incluir valores de credenciais na mensagem.
7. WHEN a validação de todos os steps de um lab for concluída com sucesso, THE Plataforma SHALL exibir tela de conclusão do lab com resumo dos serviços utilizados e domínios DEA-C01 cobertos.

---

### Requirement 6: Infraestrutura via CloudFormation

**User Story:** Como usuário da plataforma, quero que a infraestrutura de cada lab seja provisionada automaticamente via CloudFormation, para que eu possa focar no aprendizado sem configurar manualmente os recursos de suporte.

#### Acceptance Criteria

1. THE Plataforma SHALL fornecer um template CloudFormation para cada um dos 10 labs, contendo os recursos de infraestrutura necessários para a realização dos exercícios.
2. WHEN o usuário inicia um lab, THE Plataforma SHALL apresentar as instruções para implantação da CloudFormation Stack do lab antes do primeiro step de tarefa.
3. WHILE a CloudFormation Stack de um lab estiver sendo provisionada, THE Plataforma SHALL exibir o status de provisionamento com atualização periódica.
4. IF a implantação da CloudFormation Stack falhar, THEN THE Plataforma SHALL exibir o motivo da falha obtido via API CloudFormation e orientar o usuário sobre as próximas ações.
5. WHEN o usuário clica no botão "Finalizar Lab", THE Plataforma SHALL solicitar confirmação explícita do usuário antes de iniciar a exclusão da CloudFormation Stack.
6. WHEN o usuário confirma a finalização, THE Plataforma SHALL executar a exclusão da CloudFormation Stack do lab e exibir tela de aviso listando recursos residuais que podem gerar custos adicionais e requerem verificação manual.
7. THE Plataforma SHALL permitir a exibição da tela de aviso de recursos residuais independentemente do estado real da exclusão da CloudFormation Stack (não confirmada, não executada, em andamento, concluída ou com falha).

---

### Requirement 7: Catálogo de Laboratórios

**User Story:** Como candidato à certificação DEA-C01, quero acessar 10 laboratórios progressivos cobrindo todos os domínios do exame, para que eu possa praticar as habilidades avaliadas na prova.

#### Acceptance Criteria

1. THE Workshop SHALL disponibilizar os seguintes 10 labs na ordem listada: Lab 01 - Fundamentos de S3 e Data Lake (D2, iniciante), Lab 02 - Catalogação e descoberta de dados (D2), Lab 03 - Transformação ETL com AWS Glue (D1), Lab 04 - Consultas analíticas com Athena (D3), Lab 05 - Qualidade de dados com DataBrew (D3), Lab 06 - Ingestão de streaming com Kinesis (D1), Lab 07 - Data Warehouse com Redshift (D2), Lab 08 - Orquestração de pipelines (D3), Lab 09 - Segurança e Governança (D4), Lab 10 - Pipeline end-to-end (D1, D2, D3, D4).
2. THE Workshop SHALL garantir que cada lab seja independente e possa ser executado sem dependência de outros labs, exceto o Lab 10.
3. THE Workshop SHALL garantir que o Lab 10 documente explicitamente sua dependência dos Labs 01 a 09 como pré-requisito recomendado.
4. THE Workshop SHALL cobrir os domínios do exame DEA-C01 nas seguintes proporções: D1 (Ingestão e Transformação, 34%), D2 (Gerenciamento de Armazenamento, 26%), D3 (Operações e Suporte, 22%) e D4 (Segurança e Governança, 18%).
5. THE Plataforma SHALL exibir, para o Lab 01, os seguintes pré-requisitos ao usuário: conta AWS ativa com acesso administrativo, conhecimento básico de SQL, familiaridade com linha de comando, Docker instalado e Git básico.

---

### Requirement 8: Estilo Visual e Experiência

**User Story:** Como usuário da plataforma, quero que a interface visual seja familiar ao padrão dos workshops oficiais da AWS, para que eu tenha uma experiência de aprendizado consistente e profissional.

#### Acceptance Criteria

1. THE Plataforma SHALL adotar estilo visual consistente com o padrão workshops.aws, incluindo paleta de cores, tipografia e componentes de navegação.
2. THE Flask App SHALL servir todos os arquivos estáticos (HTML, CSS, JavaScript) diretamente, sem dependência de CDN externo em tempo de execução.
3. THE Plataforma SHALL ser responsiva e funcional em navegadores modernos (Chrome, Firefox, Safari, Edge) nas versões lançadas nos últimos 24 meses.
4. WHEN a validação de um step retornar resultado, THE Plataforma SHALL exibir o feedback (passou/falhou) com indicador visual distinto (cor e ícone) sem recarregar a página completa.

---

### Requirement 9: Segurança e Privacidade

**User Story:** Como usuário da plataforma, quero ter garantia de que minhas credenciais AWS e dados de progresso não são transmitidos para servidores externos, para que eu possa usar a plataforma com confiança.

#### Acceptance Criteria

1. THE Plataforma SHALL publicar a porta da interface somente na interface de loopback do host (127.0.0.1), sem expor portas para redes externas.
2. THE Plataforma SHALL armazenar o Progress Store exclusivamente em volume local no host do usuário, sem sincronização com serviços externos.
3. THE Flask App SHALL acessar as credenciais AWS exclusivamente pelas variáveis de ambiente de Credenciais temporárias recebidas do start.py, com `AWS_SHARED_CREDENTIALS_FILE=/dev/null`, `AWS_CONFIG_FILE=/dev/null` e `AWS_EC2_METADATA_DISABLED=true` no container, sem armazenar, logar ou transmitir valores de credenciais e sem incluí-los em nenhuma resposta da API.
4. THE Plataforma SHALL incluir o arquivo `progress.json` no `.gitignore` do repositório, impedindo commit acidental de dados de progresso do usuário.
5. THE Plataforma SHALL bloquear em tempo de execução toda conexão de saída do container da aplicação, exceto conexões HTTPS (porta 443) para domínios da AWS listados em uma Allowlist versionada (padrão: `.amazonaws.com` e `.api.aws`).
6. IF o container da aplicação tentar conectar a um destino fora da Allowlist, THEN THE Plataforma SHALL recusar a conexão e registrar no log do Gateway o domínio de destino e o horário, sem registrar credenciais ou cabeçalhos de autenticação.
7. THE Plataforma SHALL documentar que downloads feitos no build (imagem base, pacotes pip) ocorrem fora da restrição de runtime.
8. THE Plataforma SHALL documentar no README o risco residual de que a Allowlist por domínio não impede o envio de dados a um bucket S3 de terceiros em `*.amazonaws.com`, e que a mitigação é o uso de conta AWS isolada e de privilégio mínimo.
9. THE Plataforma SHALL recomendar no README, seguindo as práticas de segurança da AWS, o uso de uma conta AWS dedicada (sandbox) separada de contas com dados reais, de um alerta no AWS Budgets, de um permission set com o mínimo necessário em vez de `AdministratorAccess` e de sessão curta com renovação manual.

---

### Requirement 10: Cobertura dos Domínios DEA-C01

**User Story:** Como candidato à certificação DEA-C01, quero que cada laboratório esteja mapeado explicitamente aos domínios e tasks do exame, para que eu possa identificar quais competências estou desenvolvendo.

#### Acceptance Criteria

1. THE Plataforma SHALL exibir, em cada lab, o mapeamento explícito para os domínios DEA-C01 (D1, D2, D3, D4) e as tasks específicas do exame cobertas.
2. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D1 (Ingestão e Transformação de Dados): tasks 1.1, 1.2, 1.3 e 1.4.
3. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D2 (Gerenciamento de Armazenamento de Dados): tasks 2.1, 2.2, 2.3 e 2.4.
4. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D3 (Operações e Suporte de Dados): tasks 3.1, 3.2, 3.3 e 3.4.
5. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D4 (Segurança e Governança de Dados): tasks 4.1, 4.2, 4.3, 4.4 e 4.5.

---

### Requirement 11: Trilhas de Execução (Console e CLI)

**User Story:** Como usuário da plataforma, quero escolher entre executar as tarefas pelo Console ou pelo CLI, para seguir o caminho de aprendizado mais adequado a mim.

#### Acceptance Criteria

1. THE Plataforma SHALL oferecer, para cada step do tipo tarefa, instruções na Trilha Console e na Trilha CLI.
2. THE Plataforma SHALL exibir as duas Trilhas do step como opções selecionáveis na mesma tela, permitindo alternar entre elas sem perder o estado de validação do step.
3. THE Plataforma SHALL persistir no Progress Store a última Trilha escolhida pelo usuário e aplicá-la como padrão nos steps seguintes.
4. WHEN o usuário clicar em "Validar", THE Validador SHALL verificar o mesmo estado final dos recursos AWS independentemente da Trilha usada.
5. THE Plataforma SHALL exibir a Dica Detalhada correspondente à Trilha selecionada.
6. IF uma tarefa não puder ser executada em uma das Trilhas, THEN THE Plataforma SHALL indicar que essa Trilha não está disponível para o step e exibir o motivo.
7. THE Plataforma SHALL apresentar, na Trilha CLI, comandos que usem o profile e a região do usuário por meio de variáveis ou placeholders, sem conter credenciais.
8. THE Plataforma SHALL apresentar, na Trilha Console, as opções e configurações relevantes da tela do serviço que o usuário deve explorar, além do caminho mínimo para concluir a tarefa.

---

### Requirement 12: Sessão e Credenciais Temporárias

**User Story:** Como usuário da plataforma, quero ver quanto tempo resta da minha sessão AWS e ser impedido de usar credenciais expiradas, para que eu renove o login antes de perder o trabalho e evite chamadas que vão falhar.

#### Acceptance Criteria

1. THE Flask App SHALL expor `GET /api/session` retornando `expires_at`, `seconds_remaining` (calculado no servidor a partir de `WORKSHOP_CREDENTIALS_EXPIRATION`) e `status`, sem retornar valores de credenciais.
2. THE Flask App SHALL calcular `status` como `valid` quando `seconds_remaining` for maior que 600, `expiring` quando for de 1 a 600 e `expired` quando for 0 ou menor.
3. IF a variável `WORKSHOP_CREDENTIALS_EXPIRATION` estiver ausente ou não for um instante ISO 8601 válido, THEN THE Flask App SHALL tratar a sessão como `expired`.
4. THE Plataforma SHALL exibir o cronômetro da sessão no cabeçalho, sincronizá-lo com `GET /api/session` a cada 60 segundos e exibir aviso visível quando `status` for `expiring`.
5. WHILE `status` for `expired`, THE Plataforma SHALL bloquear as ações Validar, Deploy e Teardown no frontend, exibindo a explicação e o comando `python start.py --refresh` com botão de copiar.
6. WHILE `status` for `expired`, THE Flask App SHALL recusar as rotas que chamam a AWS (`POST /api/validate/<lab_id>/<step_id>`, `POST /api/deploy/<lab_id>`, `POST /api/teardown/<lab_id>` e `GET /api/stack-status/<lab_id>`) com o código `SESSION_EXPIRED` e HTTP 401, sem depender do frontend e sem chamar a AWS.

---

### Requirement 13: Proteção da API Local

**User Story:** Como usuário da plataforma, quero que a API local rejeite requisições de outras origens e de páginas maliciosas abertas no meu browser, para que um site externo não consiga acionar a minha conta AWS.

#### Acceptance Criteria

1. THE Flask App SHALL validar o cabeçalho `Host` de toda requisição contra uma allowlist formada por `127.0.0.1:<porta>` e `localhost:<porta>`, em que `<porta>` é o valor de `WORKSHOP_PORT` recebido pelo container, e SHALL responder 400 ou 421 quando o valor não constar da allowlist, exceto em `GET /health`, que não retorna dados e é usado pelo healthcheck interno do container.
2. WHEN uma requisição `POST`, `PUT` ou `DELETE` chegar à API, THE Flask App SHALL exigir o cabeçalho `Origin` presente e igual a `http://127.0.0.1:<porta>` ou `http://localhost:<porta>`, o cabeçalho `Content-Type: application/json` e o Cabeçalho de requisição própria, e SHALL recusar a requisição que não cumprir qualquer uma das três condições.
3. THE Plataforma SHALL enviar o Cabeçalho de requisição própria em toda requisição `POST`, `PUT` ou `DELETE` feita pelo frontend.
4. THE Flask App SHALL incluir em todas as respostas os cabeçalhos `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` e `Cross-Origin-Resource-Policy: same-origin`.
5. THE Plataforma SHALL entregar a porta publicada ao container `workshop` pela variável `WORKSHOP_PORT`, de modo que a allowlist de `Host` e `Origin` use a porta que o browser enxerga, pois o Gateway repassa o `Host` enviado pelo browser.

---

### Requirement 14: Endurecimento do Container e da Cadeia de Suprimentos

**User Story:** Como usuário da plataforma, quero que os containers rodem com o mínimo de privilégios e que as imagens e dependências sejam verificáveis, para que um componente comprometido cause o menor dano possível.

#### Acceptance Criteria

1. THE Plataforma SHALL executar o container `workshop` com usuário não root definido no Dockerfile, com `read_only: true`, `tmpfs` em `/tmp`, `cap_drop: [ALL]` e `security_opt: [no-new-privileges:true]`.
2. THE Plataforma SHALL manter o volume de progresso gravável pelo usuário do container `workshop` e nenhum outro caminho gravável além de `/tmp`.
3. THE Plataforma SHALL definir `mem_limit` e `pids_limit` nos serviços `workshop` e `gateway`, e SHALL aplicar ao `gateway` o máximo de restrição compatível com o funcionamento do Squid.
4. THE Plataforma SHALL fixar por digest as imagens base `python:3.15-slim` e `ubuntu/squid`.
5. THE Plataforma SHALL instalar as dependências com `pip install --require-hashes` a partir de um `requirements.txt` com hashes, gerado de forma reproduzível e com o procedimento de regeneração documentado.
6. THE Plataforma SHALL NOT montar no container nenhum caminho de credenciais do host (`~/.aws`, `~/.ssh`, `~/.config`, `~/.docker`) nem o socket do Docker, e o serviço `workshop` SHALL receber somente as variáveis de ambiente previstas.

---

### Requirement 15: CI e Governança do Repositório

**User Story:** Como mantenedor, quero que todo código aceito passe por verificações automáticas e por revisão, seguindo as recomendações de segurança do GitHub, para reduzir o risco de código malicioso ou de vazamento de segredos no repositório.

#### Acceptance Criteria

1. THE Plataforma SHALL incluir o workflow `.github/workflows/ci.yml` acionado por `pull_request` e por `push` em `main`, SHALL NOT usar `pull_request_target`, SHALL declarar `permissions: contents: read` no nível do workflow e SHALL NOT usar secrets.
2. THE Plataforma SHALL fixar por SHA completo de commit todas as actions de terceiros usadas nos workflows.
3. THE CI SHALL executar os testes Python e JavaScript, a verificação de DCO (`Signed-off-by` em todos os commits do pull request, sem app de terceiros), a varredura de segredos, `pip-audit`, `hadolint` no Dockerfile, e `cfn-lint` e `cfn-guard` nos templates de `labs/` e do fixture.
4. THE Plataforma SHALL incluir o workflow `.github/workflows/codeql.yml` para Python e JavaScript, com permissões mínimas e `security-events: write` somente no job.
5. THE Plataforma SHALL incluir `.github/dependabot.yml` com atualização semanal para `pip`, `docker` e `github-actions`.
6. THE Plataforma SHALL incluir `.github/CODEOWNERS` atribuindo `@CaeirOps` a `docker-compose.yml`, `Dockerfile`, `start.py`, `check_requirements.py`, `gateway/`, `app/server.py`, ao módulo de credenciais e sessão, a `requirements*.txt`, `.github/`, `tests/security/`, `LICENSE*` e `NOTICE`.
7. THE Plataforma SHALL incluir `.github/pull_request_template.md` com checklist de segurança.
8. THE Plataforma SHALL manter os testes de segurança em `tests/security/`, cobrindo as regras dos Requirements 9, 12, 13 e 14 e dos workflows.
9. WHEN o CI tiver executado ao menos uma vez em `main`, THE mantenedor SHALL aplicar ao repositório um ruleset em `main` com pull request obrigatório (aprovação 0 e revisão de code owners obrigatória), resolução de conversas, os 8 status checks `tests`, `dco`, `secrets`, `dependencies`, `dockerfile`, `cloudformation`, `analyze (python)` e `analyze (javascript)` com política estrita, bloqueio de force push e de exclusão, histórico linear e bypass restrito ao papel de administrador no modo `pull_request`, e SHALL habilitar secret scanning, push protection, Dependabot alerts e security updates, Private Vulnerability Reporting e as restrições de Actions (permissão padrão de leitura, sem aprovação de PR por Actions, aprovação obrigatória para workflows de fork de todos os colaboradores externos, somente actions do GitHub e `sha_pinning_required: true`).
10. THE Plataforma SHALL usar Python 3.15 na imagem base do Dockerfile, no `python-version` dos três jobs do `ci.yml`, no cabeçalho do `requirements.txt`, na imagem de `scripts/compile-requirements.sh`, nos comentários do Dockerfile e do compose, no `CONTRIBUTING.md` e no design.
11. IF a imagem com Python 3.15 não construir, ou as dependências não instalarem com `--require-hashes`, ou a suíte de testes falhar dentro da imagem, THEN THE mantenedor SHALL reverter a versão do Python para 3.11 e registrar o motivo no relatório da execução.
12. THE `.github/dependabot.yml` SHALL ignorar, para a imagem `python` do ecossistema `docker`, as atualizações `version-update:semver-major` e `version-update:semver-minor`, e SHALL continuar recebendo atualizações de patch e de digest.
13. WHEN um commit tiver autor exatamente `dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>` e trailer exatamente `Signed-off-by: dependabot[bot] <support@github.com>`, THE `scripts/check_dco.py` SHALL aceitar o commit.
14. IF um commit tiver sign-off cujo e-mail difere do e-mail do autor e o par autor e trailer não constar da allowlist de bots do script, THEN THE `scripts/check_dco.py` SHALL listar o commit como inválido e sair com código 1.
15. THE Plataforma SHALL adotar o fluxo "GitFlow simplificado com branches de release", com `main` como única branch permanente, `release/vX.Y.Z` criada a partir de `main`, branches de trabalho `feat/<descricao>`, `fix/<descricao>`, `docs/<descricao>`, `chore/<descricao>` e `lab/NN-<descricao>` criadas a partir da release ativa, e `hotfix/vX.Y.Z` criada a partir de `main`.
16. WHEN uma release for integrada a `main`, THE mantenedor SHALL abrir um PR de `release/vX.Y.Z` para `main`, integrá-lo por rebase and merge, criar a tag anotada `vX.Y.Z` (SemVer), publicar o GitHub Release com notas e apagar a branch da release.
17. THE Plataforma SHALL aceitar um único método de merge, rebase and merge, com squash e merge commit desabilitados, para preservar cada commit com seu `Signed-off-by` e manter o histórico linear.
18. THE mantenedor SHALL aplicar um segundo ruleset a `release/**` e `hotfix/**` com pull request obrigatório e os mesmos 8 status checks, sem regra de non-fast-forward (para permitir atualizar por rebase) e sem regra de exclusão (para apagar a branch após o merge), e SHALL configurar o repositório com `allow_rebase_merge: true`, `allow_squash_merge: false`, `allow_merge_commit: false`, `delete_branch_on_merge: true`, wiki e projects desligados.
19. THE Plataforma SHALL exigir que as mensagens de commit sigam Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `test:`, `refactor:`) e contenham `Signed-off-by` (`git commit -s`).

---

### Requirement 16: Documentação Pública de Segurança e Contribuição

**User Story:** Como contribuidor ou pesquisador de segurança, quero instruções claras para reportar vulnerabilidades e contribuir, para que o processo seja seguro e previsível.

#### Acceptance Criteria

1. THE Plataforma SHALL incluir `SECURITY.md` com as versões suportadas, o modo de reportar vulnerabilidade de forma privada (GitHub Private Vulnerability Reporting), o prazo de resposta indicativo e o que está fora de escopo.
2. THE Plataforma SHALL incluir `CONTRIBUTING.md` com o uso de DCO (`git commit -s`), como rodar os testes, a exigência de que o CI passe, a exigência de revisão do mantenedor para arquivos sensíveis e as diretrizes de dados fictícios, ausência de credenciais e preservação de termos técnicos em inglês.
3. THE README SHALL NOT conter instruções de configuração administrativa do repositório no GitHub.
4. THE README SHALL conter a seção "Fluxo de trabalho (gitflow)" com as branches, a branch base de cada tipo de branch de trabalho, o método de merge e as mensagens de commit, e o `CONTRIBUTING.md` e o `.github/pull_request_template.md` SHALL referenciá-la e indicar a branch base correta do PR.
