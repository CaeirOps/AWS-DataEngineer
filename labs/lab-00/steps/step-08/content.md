# Linguagens e frameworks

Um engenheiro de dados usa várias linguagens, cada uma no seu lugar. O exame espera que você saiba qual usar em cada caso.

| Linguagem ou framework | Onde aparece | Bom para |
|---|---|---|
| **SQL** | Amazon Athena, Amazon Redshift, Amazon RDS, Spark SQL | Consultar, agregar e transformar dados tabulares |
| **Python** | AWS Glue (Python shell e PySpark), AWS Lambda, scripts com boto3 | Automação, integrações com APIs e transformações |
| **PySpark** | AWS Glue, Amazon EMR | Transformações distribuídas em grande volume |
| **Scala e Java** | Spark, Apache Flink, Apache Kafka | Aplicações de streaming e jobs de alto desempenho |
| **Bash e PowerShell** | Scripts locais, AWS CLI, passos de CI/CD | Automação de operações e chamadas ao AWS CLI |
| **R** | Análises estatísticas | Exploração e modelos estatísticos |

## A mesma pergunta em três linguagens

"Quanto cada loja vendeu em 10/03/2026?"

```sql
SELECT id_loja, SUM(valor) AS total
FROM pedidos
WHERE dt = '2026-03-10' AND status = 'pago'
GROUP BY id_loja;
```

```python
from pyspark.sql import functions as F

total = (spark.read.parquet("s3://anycompany-curated/pedidos/")
    .where((F.col("dt") == "2026-03-10") & (F.col("status") == "pago"))
    .groupBy("id_loja")
    .agg(F.sum("valor").alias("total")))
```

```bash
aws athena start-query-execution \
  --work-group primary \
  --query-string "SELECT id_loja, SUM(valor) FROM pedidos WHERE dt = '2026-03-10' GROUP BY id_loja"
```

O SQL descreve o resultado e deixa o motor decidir como executar. O PySpark dá mais controle e permite combinar lógica de programação. O Bash com AWS CLI automatiza a chamada ao serviço, mas a consulta continua em SQL.

> [!TIP] Comece pelo SQL quando a transformação couber nele. É a linguagem que mais pessoas do time conseguem ler e revisar.

> [!EXAM] Quando a questão pede a solução "com menor esforço operacional" para transformar dados que já estão catalogados, uma consulta SQL no Athena ou no Redshift costuma vencer um código PySpark ou uma função Lambda.

## Boas práticas de código

- Versione o código de pipelines no Git e revise as mudanças por Pull Request (Módulo 17).
- Separe a configuração (nomes de buckets, datas) do código, usando parâmetros.
- Escreva testes para as transformações, com dados fictícios pequenos.
- Nunca grave credenciais no código: use roles do IAM e o AWS Secrets Manager (Módulo 14).
