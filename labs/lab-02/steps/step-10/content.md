# Evolução de esquema

Os dados mudam. Um fornecedor passa a enviar uma coluna a mais, um sistema troca o tipo de um campo, uma coluna deixa de existir. O catálogo e as consultas precisam sobreviver a isso.

![Uma coluna nova no arquivo e o que cada configuração do crawler faz](assets/evolucao-esquema.svg)

## Tipos de mudança

| Mudança | Exemplo | Risco |
|---|---|---|
| **Coluna nova** (no fim) | `estoque` ganha a coluna `categoria` | Baixo, se o catálogo for atualizado |
| **Coluna removida** | O fornecedor para de enviar `preco` | Consultas que usam a coluna passam a retornar nulo ou falham |
| **Tipo alterado** | `quantidade` passa de `int` para `double` | Alto: dados antigos e novos podem não ser compatíveis |
| **Coluna renomeada** | `sku` vira `codigo` | Para o catálogo é uma coluna removida e outra nova |
| **Ordem alterada** | As colunas trocam de posição | Alto em CSV |

## Como cada formato lê as colunas

- **CSV:** as colunas são lidas **por posição**. Uma coluna nova no fim é segura. Uma coluna nova no meio desloca todas as seguintes e embaralha os dados sem erro.
- **JSON:** as colunas são lidas por nome. Campos novos são aceitos, campos ausentes viram nulo.
- **Parquet, ORC e Avro:** o esquema vai dentro do arquivo, e as colunas são lidas **por nome** (no Parquet e no ORC, o motor pode ser configurado para ler por nome ou por posição). Esses formatos toleram bem a evolução de esquema, e o Avro tem regras de compatibilidade formais.

> [!EXAM] Quando o esquema vai mudar com frequência, prefira formatos que guardam o esquema no arquivo (Avro, Parquet) em vez de CSV. Acrescentar colunas no **fim** é a mudança mais segura.

## A política de mudança de esquema do crawler

O crawler decide o que fazer quando encontra um esquema diferente do que está no catálogo, por duas configurações (`SchemaChangePolicy`):

| Configuração | Valores | Efeito |
|---|---|---|
| **UpdateBehavior** (esquema mudou) | `UPDATE_IN_DATABASE` | Atualiza a tabela com o esquema novo (padrão do console) |
| | `LOG` | Só registra a mudança no log, sem alterar a tabela |
| **DeleteBehavior** (objeto sumiu) | `LOG` | Só registra |
| | `DEPRECATE_IN_DATABASE` | Marca a tabela como obsoleta (`DEPRECATED`) |
| | `DELETE_FROM_DATABASE` | Apaga a tabela ou a partição do catálogo |

Além disso, a opção **Update all new and existing partitions with metadata from the table** faz as partições herdarem as mudanças da tabela. Sem ela, partições antigas continuam com o esquema antigo.

> [!TIP] Em produção, comece com `LOG` para ver o que mudaria, e só use `DELETE_FROM_DATABASE` quando tiver certeza. Apagar uma tabela do catálogo não apaga os dados do S3, mas derruba quem a consulta.

> [!WARNING] Atualizar o esquema da tabela não reescreve os dados antigos. Um arquivo antigo, sem a coluna nova, devolve nulo para ela. Isso é esperado.

## Outras formas de tratar a evolução

- **Tabelas abertas** (Apache Iceberg, Hudi, Delta Lake) guardam o esquema nos próprios metadados e permitem adicionar, renomear e remover colunas com segurança, sem reescrever os dados (Módulo 11).
- **AWS Glue Schema Registry** guarda e valida os esquemas de dados em streaming (Avro, JSON Schema e Protobuf), com regras de compatibilidade (Módulo 07).
- **Contratos de dados:** combinar com o produtor do dado as mudanças permitidas, e testar as consultas contra o esquema novo antes de promovê-lo.
