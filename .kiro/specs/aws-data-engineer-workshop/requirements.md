# Requirements Document

## Introduction

Este documento define os requisitos para a Plataforma de Workshop AWS Data Engineer — uma plataforma de treinamento interativa, open source e self-paced voltada para a comunidade AWS brasileira. A plataforma prepara candidatos para a certificação AWS Certified Data Engineer - Associate (DEA-C01) por meio de 10 laboratórios práticos que utilizam recursos reais na AWS. A solução é distribuída via `git clone` e executada localmente com Docker Compose, sem autenticação, sem servidor externo e sem rastreamento de dados do usuário.

## Glossary

- **Plataforma**: A aplicação web local composta por Flask (backend), HTML/CSS/JS estático (frontend) e scripts Python de validação.
- **Workshop**: O conjunto completo de 10 laboratórios de treinamento para a certificação DEA-C01.
- **Lab**: Um laboratório individual contendo cenário, steps, validações e recursos de infraestrutura CloudFormation.
- **Step**: Uma etapa atômica dentro de um lab, com cenário, tarefa e botão de validação.
- **Validador**: O módulo Python com boto3 que verifica o estado real dos recursos AWS para um determinado step.
- **Dashboard**: A tela inicial da plataforma que exibe o progresso consolidado de todos os labs.
- **Progress Store**: O arquivo `progress.json` armazenado em volume local (gitignored) que persiste o estado de progresso do usuário.
- **check_requirements.py**: Script Python de pré-validação que verifica Docker, AWS CLI, credenciais e permissões antes da inicialização.
- **Flask App**: O servidor web Python (Flask) executado em container Docker que serve o frontend estático e expõe a API de validação.
- **CloudFormation Stack**: A stack de infraestrutura AWS provisionada por template CloudFormation para cada lab.
- **Domínio DEA-C01**: Um dos quatro domínios de conhecimento do exame AWS Certified Data Engineer - Associate (D1, D2, D3, D4).
- **Dica Detalhada**: Conteúdo de ajuda contextual exibido ao usuário após falhas consecutivas na validação de um step.

## Requirements

### Requirement 1: Distribuição e Inicialização

**User Story:** Como desenvolvedor interessado na certificação DEA-C01, quero clonar o repositório e iniciar a plataforma com um único comando, para que eu possa começar a praticar sem configuração complexa.

#### Acceptance Criteria

1. THE Plataforma SHALL ser distribuída exclusivamente via repositório Git público, sem dependência de registro de pacotes externo.
2. WHEN o usuário executa `python check_requirements.py`, THE check_requirements.py SHALL verificar a presença do Docker versão 20 ou superior, AWS CLI versão 2 ou superior, credenciais AWS válidas e permissões mínimas requeridas pelo lab selecionado.
3. IF o check_requirements.py detectar qualquer pré-requisito ausente ou inválido, THEN THE check_requirements.py SHALL exibir mensagem de erro descritiva identificando o pré-requisito faltante e os passos para corrigi-lo, interrompendo a execução.
4. WHEN o usuário executa `docker compose up`, THE Flask App SHALL iniciar e estar acessível em `http://localhost:5000` em até 60 segundos.
5. THE Flask App SHALL montar o diretório `~/.aws` do host como volume somente-leitura no container, sem copiar credenciais para a imagem Docker.
6. THE Flask App SHALL montar um volume local para o arquivo `progress.json`, preservando o progresso entre reinicializações do container.
7. THE Plataforma SHALL ser licenciada sob MIT License e disponibilizada como open source.
8. IF o Flask App não estiver acessível em `http://localhost:5000` após 60 segundos da execução de `docker compose up`, THEN THE Plataforma SHALL continuar aguardando a inicialização do Flask App sem exibir erro explícito e sem interromper a execução.

---

### Requirement 2: Dashboard de Progresso

**User Story:** Como usuário da plataforma, quero visualizar meu progresso consolidado ao acessar a tela inicial, para que eu saiba quais labs já completei e onde posso retomar meu aprendizado.

#### Acceptance Criteria

1. WHEN o usuário acessa `http://localhost:5000`, THE Dashboard SHALL exibir todos os 10 labs com seus respectivos títulos, domínios DEA-C01 e níveis de complexidade.
2. THE Dashboard SHALL exibir, para cada lab, o número de steps concluídos sobre o total de steps disponíveis.
3. THE Dashboard SHALL identificar visualmente o ponto de retomada de cada lab iniciado mas não concluído.
4. WHEN o usuário clica em um lab no Dashboard, THE Plataforma SHALL navegar para o step mais recente não concluído daquele lab, ou para o primeiro step caso o lab ainda não tenha sido iniciado.
5. THE Progress Store SHALL persistir o estado de progresso localmente no arquivo `progress.json` em volume Docker, sem transmitir dados do usuário para servidores externos.

---

### Requirement 3: Navegação por Wizard

**User Story:** Como usuário da plataforma, quero navegar livremente entre os steps de um lab, para que eu possa revisitar etapas anteriores ou pular para steps que já visitei.

#### Acceptance Criteria

1. THE Plataforma SHALL apresentar os steps de cada lab em formato wizard com navegação sequencial e lateral.
2. WHEN o usuário já visitou um step anteriormente, THE Plataforma SHALL permitir navegação direta para aquele step a partir do indicador de progresso do wizard.
3. WHILE o usuário estiver no primeiro step de um lab, THE Plataforma SHALL desabilitar o botão de navegação para o step anterior.
4. WHILE o usuário estiver no último step de um lab, THE Plataforma SHALL exibir o botão "Finalizar Lab" em substituição ao botão de avanço.
5. THE Plataforma SHALL refletir em tempo real no indicador de progresso do wizard o status (concluído, em andamento, não visitado) de cada step.
6. WHILE o usuário estiver em um step intermediário de um lab, THE Plataforma SHALL exibir o botão "Avançar" e ocultar o botão "Finalizar Lab", de modo que exatamente uma ação de navegação de avanço esteja visível e ativa.

---

### Requirement 4: Exibição de Laboratório

**User Story:** Como usuário da plataforma, quero ler o cenário e as instruções de cada step com clareza, para que eu saiba exatamente o que precisa ser feito na minha conta AWS.

#### Acceptance Criteria

1. THE Plataforma SHALL exibir, para cada step, um cenário narrativo contextualizado, as tarefas a serem executadas na AWS e os critérios de aceitação esperados.
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
6. IF o Validador não conseguir se conectar à AWS devido a credenciais expiradas ou ausentes, THEN THE Validador SHALL retornar mensagem de erro indicando o problema de credenciais e orientando o usuário a reconfigurar o volume `~/.aws`.
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

1. THE Flask App SHALL operar exclusivamente em modo local (`localhost`), sem expor portas para redes externas por padrão.
2. THE Plataforma SHALL armazenar o Progress Store exclusivamente em volume local no host do usuário, sem sincronização com serviços externos.
3. THE Flask App SHALL acessar as credenciais AWS exclusivamente por meio do volume `~/.aws` montado como somente-leitura, sem armazenar, logar ou transmitir valores de credenciais.
4. THE Plataforma SHALL incluir o arquivo `progress.json` no `.gitignore` do repositório, impedindo commit acidental de dados de progresso do usuário.
5. IF o container Docker tentar realizar conexão de rede para endereço externo não relacionado aos endpoints AWS necessários para boto3, THEN THE Plataforma SHALL exibir dinamicamente ao usuário, em tempo de execução, um alerta informando o comportamento detectado e sua finalidade.

---

### Requirement 10: Cobertura dos Domínios DEA-C01

**User Story:** Como candidato à certificação DEA-C01, quero que cada laboratório esteja mapeado explicitamente aos domínios e tasks do exame, para que eu possa identificar quais competências estou desenvolvendo.

#### Acceptance Criteria

1. THE Plataforma SHALL exibir, em cada lab, o mapeamento explícito para os domínios DEA-C01 (D1, D2, D3, D4) e as tasks específicas do exame cobertas.
2. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D1 (Ingestão e Transformação de Dados): tasks 1.1, 1.2, 1.3 e 1.4.
3. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D2 (Gerenciamento de Armazenamento de Dados): tasks 2.1, 2.2, 2.3 e 2.4.
4. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D3 (Operações e Suporte de Dados): tasks 3.1, 3.2, 3.3 e 3.4.
5. THE Workshop SHALL incluir labs que cubram as tasks do Domínio D4 (Segurança e Governança de Dados): tasks 4.1, 4.2, 4.3, 4.4 e 4.5.
