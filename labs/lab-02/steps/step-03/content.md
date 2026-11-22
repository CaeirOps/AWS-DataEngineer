# O catálogo de dados

Um **catálogo de dados** é um índice dos dados da organização: onde cada conjunto de dados está, qual é o seu esquema e como ele é lido. Ele guarda **metadados**, não os dados.

## Metadados técnicos e de negócio

| Tipo | Responde | Exemplo |
|---|---|---|
| **Técnico** | Onde está e como se lê? | Tabela `pedidos`, em `s3://.../pedidos/`, formato CSV, colunas `id_pedido` (bigint) e `valor` (double), partição `dt` |
| **De negócio** | O que significa e quem cuida? | "`valor` é o valor líquido do pedido, em reais"; responsável: time de vendas |

O **AWS Glue Data Catalog** é o catálogo técnico da AWS. Neste módulo, "catálogo" quer dizer ele. O catálogo de negócio, com glossário e proprietários, aparece no Módulo 15 (governança).

## Como o Glue Data Catalog se organiza

![Estrutura do Data Catalog e quem consome o catálogo](assets/estrutura-do-catalogo.svg)

- **Database:** agrupa tabelas, como um esquema (schema) de banco relacional.
- **Tabela:** nome, colunas e tipos, localização dos dados, formato (a *SerDe*, que sabe ler e gravar os bytes) e partições. A tabela **não contém dados**: ela aponta para o S3.
- **Partição:** cada valor de uma chave de partição (por exemplo `dt=2026-03-10`) é um registro do catálogo com a própria localização.
- **Conexão:** guarda como chegar a uma fonte que precisa de rede ou senha, como um banco JDBC.

## Quem consome o catálogo

O mesmo catálogo serve vários motores, por isso você define o esquema uma vez:

| Serviço | Como usa o catálogo |
|---|---|
| Amazon Athena | Consulta as tabelas com SQL (Módulo 03) |
| AWS Glue ETL | Lê e grava tabelas pelo nome (Módulo 04) |
| Amazon EMR | Usa o catálogo como metastore do Hive e do Spark (Módulo 05) |
| Amazon Redshift Spectrum | Consulta tabelas externas do catálogo (Módulo 10) |
| AWS Lake Formation | Controla o acesso a databases, tabelas e colunas (Módulo 15) |

> [!EXAM] "Usar o catálogo para consumir dados na origem" significa consultar o dado onde ele está (no S3, por exemplo), por meio do esquema do catálogo, sem copiá-lo para outro lugar.

## Hive metastore

O **Apache Hive metastore** é o catálogo técnico do ecossistema Hadoop e Spark: guarda tabelas, colunas e partições em um banco relacional. O Glue Data Catalog é **compatível com o Hive metastore**:

- Um cluster Amazon EMR pode usar o Glue Data Catalog como metastore do Hive e do Spark, e as tabelas ficam compartilhadas com o Athena.
- Quem já tem um metastore Hive próprio pode manter essa opção, mas passa a cuidar do banco, dos backups e da disponibilidade. O Glue Data Catalog é gerenciado e sem servidores.

> [!EXAM] Para compartilhar o mesmo esquema entre o Athena, o EMR e o Redshift Spectrum com o menor esforço operacional, use o Glue Data Catalog. Um metastore Hive próprio só se justifica por uma exigência específica.

## Como o catálogo é preenchido

Há três jeitos, e você usa os três neste módulo:

1. **Crawler:** varre a fonte, descobre o esquema e cria ou atualiza as tabelas (steps 04, 06 e 11).
2. **DDL ou API:** você cria a tabela com `CREATE EXTERNAL TABLE` no Athena ou com a API do Glue (`CreateTable`), e as partições com `ALTER TABLE ADD PARTITION` ou `BatchCreatePartition` (step 08).
3. **Job ETL:** um job do AWS Glue pode criar ou atualizar a tabela ao gravar o resultado (Módulo 04).

> [!COST] No Data Catalog, você paga pelos objetos armazenados e pelas requisições acima da camada gratuita mensal (1 milhão de cada). Para o workshop, o custo é praticamente zero.
