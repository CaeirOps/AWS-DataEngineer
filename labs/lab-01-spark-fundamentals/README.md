# Lab 01 — Fundamentos de Apache Spark e PySpark

## Objetivo

Compreender os conceitos fundamentais do Apache Spark e desenvolver fluência
com a API PySpark, base para todos os laboratórios seguintes e para o uso de
**AWS Glue**, que executa jobs Spark gerenciados na AWS.

## Conceitos abordados

| Conceito | Descrição |
|---|---|
| **SparkSession** | Ponto de entrada de toda aplicação Spark |
| **DataFrame** | Abstração principal para dados estruturados |
| **Lazy evaluation** | Transformações constroem um plano; ações executam |
| **DAG** | Grafo dirigido acíclico — o plano de execução do Spark |
| **Transformações** | `select`, `filter`, `withColumn` — não executam imediatamente |
| **Ações** | `show`, `count`, `write` — disparam a execução do plano |
| **Particionamento** | Como o Spark divide dados para processamento paralelo |
| **Parquet** | Formato colunar padrão em pipelines de dados modernos |
| **Spark SQL** | SQL padrão sobre DataFrames via views temporárias |

## Conexão com o exame DEA-C01

O **AWS Glue** executa jobs Spark gerenciados. Entender como o Spark funciona
localmente é pré-requisito direto para:

- Domínio 1 — *Ingestão e transformação de dados* (34%)
  - Escrever Glue Jobs em PySpark
  - Entender `DynamicFrame` vs `DataFrame`
  - Otimizar transformações e evitar UDFs desnecessárias

## Estrutura do laboratório

```
lab-01-spark-fundamentals/
├── README.md           # Este arquivo
├── data/
│   └── output/         # Parquet gerado ao executar o lab (ignorado pelo git)
├── notebooks/
│   └── lab01.ipynb     # Notebook interativo (mesmo conteúdo do script)
└── src/
    └── lab01.py        # Script principal — execute este arquivo
```

## Dataset

Arquivo: `datasets/lab-01/vendas.csv`

Dados fictícios de vendas de produtos de tecnologia, com 30 registros e
as colunas: `id_venda`, `data`, `produto`, `categoria`, `quantidade`,
`preco_unitario`, `regiao`, `vendedor`.

## Pré-requisitos

1. Ambiente configurado conforme o [README principal](../../README.md)
2. Virtual environment ativado:

```bash
source .venv/bin/activate
```

3. `JAVA_HOME` configurado no `~/.zshrc`:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
export PYSPARK_PYTHON=$(which python3)
```

## Como executar

### Opção 1 — Script Python (recomendado para começar)

Execute a partir da **raiz do repositório**:

```bash
python labs/lab-01-spark-fundamentals/src/lab01.py
```

### Opção 2 — Notebook Jupyter (recomendado para exploração)

```bash
jupyter lab
```

Abra o arquivo `labs/lab-01-spark-fundamentals/notebooks/lab01.ipynb`.

## O que o lab executa

1. **Cria uma SparkSession** em modo local usando todos os cores disponíveis
2. **Lê o CSV** com schema inferido e depois com schema explícito
3. **Demonstra lazy evaluation** mostrando o plano de execução antes de executar
4. **Aplica transformações**: calcula `valor_total`, converte datas, filtra e seleciona
5. **Faz agregações**: receita por categoria, top vendedores, evolução mensal
6. **Escreve em Parquet** particionado por `categoria`
7. **Executa Spark SQL** sobre uma view temporária

## Resultados esperados

Ao final da execução você verá:

- Schema do DataFrame e primeiros registros
- Plano de execução lógico (`explain`)
- Tabelas de análise: por categoria, por vendedor, por mês, por região
- Confirmação de escrita e leitura do Parquet

## Conceito-chave: Lazy Evaluation

```
df.filter(...)     ← transformação: só define o plano
  .withColumn(...) ← transformação: adiciona ao plano
  .select(...)     ← transformação: adiciona ao plano
  .show()          ← AÇÃO: Spark executa tudo agora
```

O Spark acumula as transformações e as otimiza (via *Catalyst Optimizer*)
antes de executar. Isso é fundamentalmente diferente do pandas, que executa
cada operação imediatamente.

## Próximo laboratório

**Lab 02 — AWS Glue: ETL com DynamicFrames**
Levaremos o mesmo pipeline para a AWS usando Glue Jobs, S3 e o Glue Data Catalog.
