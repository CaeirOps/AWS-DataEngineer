# Serviços gerenciados e não gerenciados

A mesma tecnologia pode ser usada de formas diferentes na AWS. O Apache Kafka, por exemplo, pode rodar em instâncias EC2 que você administra, no Amazon MSK provisionado ou no Amazon MSK Serverless. A diferença está em quem cuida de cada parte.

## Modelo de responsabilidade compartilhada

A AWS é responsável pela segurança **da** nuvem: data centers, hardware, rede e a infraestrutura dos serviços. Você é responsável pela segurança **na** nuvem: seus dados, acessos e configurações. O que fica de cada lado muda conforme o tipo de serviço.

| Tarefa | Kafka em EC2 (não gerenciado) | Amazon MSK provisionado | Amazon MSK Serverless |
|---|---|---|---|
| Hardware e data center | AWS | AWS | AWS |
| Sistema operacional e patches | Você | AWS | AWS |
| Instalar e atualizar o Kafka | Você | AWS, na versão que você escolhe | AWS |
| Substituir brokers com falha | Você | AWS | AWS |
| Dimensionar brokers e disco | Você | Você | AWS |
| Acesso, criptografia e rede | Você | Você | Você |
| Dados e tópicos | Você | Você | Você |

O mesmo vale para o Spark:

- **Spark em EC2:** você instala, configura e mantém tudo.
- **Amazon EMR on EC2:** a AWS provisiona o cluster e instala as aplicações. Você escolhe as instâncias, o tamanho e quando ligar e desligar.
- **Amazon EMR Serverless e AWS Glue:** você envia o job e o serviço provisiona e libera a capacidade.

## Impacto na segurança

Com um serviço gerenciado, você não cuida de patches do sistema operacional nem de autenticação no nível do servidor. Continua sendo seu papel:

- dar acesso com IAM e privilégio mínimo;
- ativar a criptografia em repouso e em trânsito;
- colocar os recursos nas subnets e security groups certos;
- registrar e monitorar o uso.

Em um serviço não gerenciado, você soma a isso as contas de usuário do sistema operacional, o acesso SSH, as atualizações de segurança e a autenticação da própria aplicação.

> [!EXAM] "Menor esforço operacional" ou "sem gerenciar servidores" apontam para serviços gerenciados ou sem servidor. Escolha o não gerenciado só quando o enunciado exigir algo que o gerenciado não oferece, como uma versão ou configuração específica.

> [!COST] Gerenciado não quer dizer mais barato nem mais caro. Um cluster provisionado ligado o dia todo cobra mesmo ocioso. Um serviço sem servidor cobra pelo uso, o que é bom para cargas intermitentes. Para cargas constantes e altas, capacidade provisionada pode sair mais barata.

> [!WARNING] Sem servidor não quer dizer sem configuração de segurança. Uma tabela ou um bucket com permissão aberta é um problema seu, qualquer que seja o tipo de serviço.
