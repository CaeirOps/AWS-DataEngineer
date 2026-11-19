# Computação distribuída

Quando o dado não cabe em uma máquina, ou quando uma máquina demora demais, o processamento é dividido entre várias. Isso é **computação distribuída**.

## Escalar para cima e para os lados

- **Vertical (*scale up*):** uma máquina maior, com mais CPU e memória. É simples, mas tem um limite e custa cada vez mais por unidade.
- **Horizontal (*scale out*):** mais máquinas trabalhando juntas. Não tem limite prático, mas exige dividir o trabalho e lidar com falhas de partes do sistema.

Os motores de big data, como Apache Spark, Apache Hadoop e Apache Flink, escalam horizontalmente.

## Como o Apache Spark divide o trabalho

![Driver, executors e o DAG de um job Spark](assets/spark-driver-executors.svg)

- O **driver** recebe o código, monta o plano de execução e distribui as tarefas.
- Os **executors** rodam nas máquinas do cluster e processam as **partições** dos dados. Cada partição vira uma tarefa.
- O plano é um **DAG** (grafo acíclico dirigido) de estágios. Operações como `filter` e `select` rodam dentro do mesmo estágio. Operações como `groupBy` e `join` exigem um **shuffle**: os dados são redistribuídos pela rede para que registros com a mesma chave fiquem no mesmo executor.

Exemplo: somar as vendas de cada loja.

```python
vendas_por_loja = pedidos.filter("status = 'pago'").groupBy("id_loja").sum("valor")
```

1. Cada executor lê e filtra as suas partições de `pedidos`, sem conversar com os outros.
2. O `groupBy` provoca o shuffle: todas as linhas da loja 17 vão para o mesmo executor.
3. Cada executor soma as lojas que recebeu e grava o resultado.

> [!TIP] O shuffle é a parte mais cara de um job distribuído, porque move dados pela rede. Filtre e selecione colunas antes de agrupar ou juntar.

> [!WARNING] Se uma chave concentra boa parte dos dados (por exemplo, uma loja muito maior que as outras), um executor fica sobrecarregado enquanto os outros esperam. Esse problema se chama *data skew*.

## Falhas e tolerância

Em um cluster com muitas máquinas, alguma vai falhar. Os motores distribuídos repetem só as tarefas perdidas, em outra máquina, em vez de reiniciar o job inteiro. Isso funciona porque cada tarefa lê uma partição conhecida da fonte e não depende do estado de outras tarefas.

## Na AWS

- **AWS Glue:** Spark sem servidor para ETL (Módulo 04).
- **Amazon EMR:** clusters ou aplicações sem servidor com Spark, Hive, Presto e outros (Módulo 05).
- **Amazon Athena:** SQL distribuído sobre os dados do S3, sem gerenciar cluster (Módulo 03).
- **Amazon Redshift:** data warehouse com processamento paralelo massivo, o MPP (Módulo 10).

> [!EXAM] Termos como "escalar horizontalmente", "processar em paralelo" e "milhões de registros que não cabem em memória" indicam um motor distribuído, como Glue, EMR, Athena ou Redshift, e não um script em uma única instância ou função Lambda.
