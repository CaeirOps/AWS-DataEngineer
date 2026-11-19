# Conexões e fontes JDBC

Nem todo dado está no S3. Muitos ficam em bancos relacionais, como o Amazon RDS, o Amazon Aurora e o Amazon Redshift. Para catalogá-los, ou para o AWS Glue lê-los em um job, é preciso uma **conexão**.

## JDBC e ODBC

| | JDBC | ODBC |
|---|---|---|
| O que é | API padrão para aplicações Java acessarem bancos de dados | API padrão, independente de linguagem, para ferramentas como Excel e BI |
| Onde aparece na AWS | Glue (jobs e crawlers), EMR, Spark | Ferramentas de BI e clientes SQL que se conectam ao Athena ou ao Redshift |
| Informa | URL (`jdbc:postgresql://host:5432/banco`), usuário e senha, driver | Nome da fonte (DSN) e driver |

## Conexão do AWS Glue

Uma **conexão do Glue** guarda como alcançar uma fonte ou um destino:

- **URL JDBC**, ou o endpoint da fonte;
- **Credenciais**: use o **AWS Secrets Manager** e referencie o secret na conexão. Não escreva a senha na conexão nem no código;
- **Rede**: a VPC, a subnet e os security groups usados para chegar ao banco. O Glue cria uma interface de rede nessa subnet.

![Conexão do Glue até um banco em uma subnet privada](assets/conexao-jdbc.svg)

### Regras de rede

- O banco costuma estar em uma **subnet privada**. Os crawlers e jobs rodam na VPC do Glue por meio da interface de rede criada na subnet que você escolheu.
- O security group da conexão precisa permitir **todo o tráfego de entrada dele mesmo** (uma regra que referencia o próprio security group), e o security group do banco precisa permitir a porta do banco a partir do security group do Glue.
- Para o Glue ler do S3 ou chamar o Secrets Manager a partir dessa subnet, é preciso um **gateway endpoint do S3**, um endpoint de interface do Secrets Manager ou uma rota por NAT gateway.

> [!EXAM] Catalogar ou ler um banco em uma subnet privada exige uma conexão do Glue com a VPC, a subnet e o security group corretos. Falhas de conexão costumam ser de rede (security group ou rota), não do crawler.

## Crawler JDBC

Um crawler com alvo JDBC percorre o banco pela conexão, lê o esquema (tabelas, colunas e tipos) e cria as tabelas no Data Catalog. O caminho do alvo segue o padrão `banco/esquema/tabela`, e aceita `%` como curinga.

- A tabela catalogada aponta para o banco: os **dados continuam no banco**, e o catálogo só guarda o esquema.
- Para analisar esses dados com Athena ou Spark em larga escala, o caminho usual é copiá-los para o S3 com um job do Glue ou com o AWS DMS (Módulo 09).

> [!TIP] Antes de rodar o crawler, use **Test connection** na conexão. A maioria dos problemas de rede aparece ali.

> [!WARNING] Um crawler JDBC lê o catálogo do banco (esquema), mas faz uma amostragem leve. Mesmo assim, rode-o fora do horário de pico e com um usuário somente leitura.

## Outras formas de conectar

- **Conectores do AWS Glue** para fontes de terceiros (Snowflake, BigQuery, Salesforce e outras) e conectores do **Amazon AppFlow** para aplicações SaaS.
- **AWS DMS** para replicar bancos para o S3 de forma contínua (Módulo 09).
- **Federated queries** do Athena, que consultam bancos relacionais e outras fontes com conectores em funções Lambda, sem copiar os dados (Módulo 03).
