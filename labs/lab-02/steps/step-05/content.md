# Como o crawler funciona

Um **crawler** é um processo gerenciado do AWS Glue que se conecta a uma fonte, descobre o esquema e grava as tabelas no Data Catalog.

## O que ele faz em uma execução

1. Lê a fonte, por exemplo o prefixo `pedidos/` no S3, e amostra os arquivos.
2. Passa os arquivos por uma lista de **classificadores**, em ordem. O primeiro que reconhece o formato define o esquema. Os classificadores internos entendem CSV, JSON, Parquet, ORC, Avro e outros. Você pode criar classificadores próprios (por exemplo, um CSV com delimitador incomum).
3. Agrupa os arquivos em **tabelas**: arquivos com esquema parecido sob o mesmo prefixo viram uma tabela. Pastas no formato `chave=valor` viram **partições**.
4. Cria ou atualiza as tabelas e as partições no Data Catalog.

## O que o crawler enxerga

| Fonte | Observação |
|---|---|
| Amazon S3 | O alvo mais comum. O crawler percorre o prefixo informado |
| Bancos JDBC (Amazon RDS, Aurora, Redshift e outros) | Precisa de uma **conexão** (step 12) |
| Amazon DynamoDB | Amostra os itens para inferir o esquema |
| Tabelas já catalogadas, Delta Lake, Iceberg, Hudi, MongoDB | Outros alvos aceitos |

## Opções que mudam o resultado

- **Prefixo de tabela:** texto colocado no início do nome das tabelas criadas (por exemplo `raw_`), para identificar a origem.
- **Exclusões:** padrões de arquivos que o crawler ignora (por exemplo `**/_temporary/**`).
- **Política de mudança de esquema:** o que fazer quando o esquema muda ou um objeto some (step 10).
- **Execuções seguintes:** varrer tudo de novo ou só as pastas novas (**crawl new sub-folders only**, o modo incremental, step 07).
- **Agenda:** sob demanda ou por expressão cron (step 09).

![Do S3 ao catálogo, passando pelo crawler](assets/crawler-fluxo.svg)

## A role do crawler

O crawler assume uma role do IAM. Ela precisa de:

- leitura no S3 (`s3:GetObject` e `s3:ListBucket`) dos prefixos que ele varre;
- permissões do Glue para criar e atualizar tabelas e partições do database;
- gravação de logs no CloudWatch Logs.

A stack deste módulo já criou uma role assim, com privilégio mínimo. A política gerenciada `AWSGlueServiceRole` existe, mas é ampla (cobre vários recursos e buckets com o prefixo `aws-glue-`), e vale usá-la só quando isso for aceitável.

## Custo

> [!COST] O crawler cobra por **DPU-hora**, por segundo, com **mínimo de 10 minutos por execução**. Um crawler que roda por 1 minuto é cobrado como 10. Por isso, execuções muito frequentes de crawlers pequenos custam mais do que parece, e vale usar o modo incremental ou outro jeito de registrar partições (step 07).

## Limites do crawler

- Ele **infere** o esquema a partir de uma amostra. Em arquivos com muita variação, pode inferir tipos que não são os que você quer (por exemplo, `string` onde seria `date`).
- Ele não entende o significado dos dados nem apaga dados.
- Em CSV, o cabeçalho é detectado quando a primeira linha tem só texto e as demais têm outros tipos. Quando todas as colunas são texto, o crawler pode tratar o cabeçalho como dado e nomear as colunas `col0`, `col1`...

> [!EXAM] "Descobrir o esquema automaticamente e manter o catálogo atualizado, com o menor esforço operacional" é a pista para o crawler do AWS Glue com agenda, em vez de criar as tabelas à mão ou escrever código de inferência.
