"""
=============================================================================
Lab 01 — Fundamentos de Apache Spark e PySpark
=============================================================================
Objetivo:
    Explorar os conceitos fundamentais do Apache Spark usando PySpark:
    SparkSession, DataFrame, transformações lazy e ações.

Dataset:
    datasets/lab-01/vendas.csv — dados fictícios de vendas de produtos

Pré-requisitos:
    - .venv ativado: source .venv/bin/activate
    - JAVA_HOME configurado para Java 17

Execução:
    python labs/lab-01-spark-fundamentals/src/lab01.py
=============================================================================
"""

import os

# Aponta para o Java 17 instalado via Homebrew
os.environ["JAVA_HOME"] = (
    "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
)

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

# =============================================================================
# PARTE 1 — SparkSession
# =============================================================================
# A SparkSession é o ponto de entrada de qualquer aplicação Spark.
# No modo local, master("local[*]") usa todos os cores da máquina.
# Em produção (ex.: AWS Glue), o cluster gerencia isso automaticamente.

spark = (
    SparkSession.builder
    .appName("Lab01 - Fundamentos Spark")
    .master("local[*]")
    .config("spark.ui.enabled", "false")   # desativa a UI web em ambiente local
    .config("spark.sql.shuffle.partitions", "4")  # reduz partições para ambiente local
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")

print("=" * 60)
print(f"Spark versão : {spark.version}")
print(f"App name     : {spark.sparkContext.appName}")
print(f"Master       : {spark.sparkContext.master}")
print("=" * 60)

# =============================================================================
# PARTE 2 — Leitura de dados (CSV → DataFrame)
# =============================================================================
# O Spark infere o schema automaticamente com inferSchema=True.
# Em produção, defina o schema manualmente para garantir tipos corretos
# e evitar um segundo scan dos dados.

DATASET_PATH = "datasets/lab-01/vendas.csv"

print("\n[PARTE 2] Lendo o dataset...")

# Leitura com inferência automática de schema
df_raw = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(DATASET_PATH)
)

print("\nSchema inferido automaticamente:")
df_raw.printSchema()

# Leitura com schema explícito — prática recomendada em produção
schema = StructType([
    StructField("id_venda",       IntegerType(), nullable=False),
    StructField("data",           StringType(),  nullable=False),
    StructField("produto",        StringType(),  nullable=False),
    StructField("categoria",      StringType(),  nullable=False),
    StructField("quantidade",     IntegerType(), nullable=False),
    StructField("preco_unitario", DoubleType(),  nullable=False),
    StructField("regiao",         StringType(),  nullable=False),
    StructField("vendedor",       StringType(),  nullable=False),
])

df = (
    spark.read
    .option("header", "true")
    .schema(schema)
    .csv(DATASET_PATH)
)

print("\nSchema explícito (produção):")
df.printSchema()

print(f"\nTotal de registros: {df.count()}")
print("\nPrimeiras 5 linhas:")
df.show(5, truncate=False)

# =============================================================================
# PARTE 3 — Lazy Evaluation (avaliação preguiçosa)
# =============================================================================
# Transformações (select, filter, withColumn) NÃO executam imediatamente.
# Elas constroem um plano de execução (DAG). Só quando uma AÇÃO é chamada
# (show, count, write, collect) o Spark executa o plano otimizado.

print("\n[PARTE 3] Lazy evaluation — construindo transformações...")

# Estas linhas não executam nada ainda — apenas definem o plano
df_transformado = (
    df
    # Transformação 1: nova coluna com o valor total da venda
    .withColumn("valor_total", F.col("quantidade") * F.col("preco_unitario"))
    # Transformação 2: converter data de string para tipo DateType
    .withColumn("data", F.to_date(F.col("data"), "yyyy-MM-dd"))
    # Transformação 3: extrair mês
    .withColumn("mes", F.month(F.col("data")))
    # Transformação 4: filtrar apenas vendas com valor_total > 1000
    .filter(F.col("valor_total") > 1000)
    # Transformação 5: selecionar apenas as colunas relevantes
    .select("id_venda", "data", "mes", "produto", "categoria",
            "regiao", "vendedor", "quantidade", "preco_unitario", "valor_total")
)

# Aqui o plano é exibido SEM executar — mostra a lógica de otimização
print("\nPlano de execução lógico (explain):")
df_transformado.explain(mode="simple")

# AÇÃO — apenas agora o Spark executa tudo
print("\nResultado após transformações (valor_total > 1000):")
df_transformado.show(10, truncate=False)

# =============================================================================
# PARTE 4 — Agregações e análises
# =============================================================================
print("\n[PARTE 4] Agregações...")

# Total de vendas por categoria
print("\n--- Vendas por categoria ---")
(
    df_transformado
    .groupBy("categoria")
    .agg(
        F.count("id_venda").alias("qtd_vendas"),
        F.sum("valor_total").alias("receita_total"),
        F.avg("valor_total").alias("ticket_medio"),
    )
    .withColumn("receita_total", F.round("receita_total", 2))
    .withColumn("ticket_medio",  F.round("ticket_medio",  2))
    .orderBy(F.desc("receita_total"))
    .show(truncate=False)
)

# Top 3 vendedores por receita
print("\n--- Top 3 vendedores ---")
(
    df_transformado
    .groupBy("vendedor")
    .agg(F.sum("valor_total").alias("receita_total"))
    .withColumn("receita_total", F.round("receita_total", 2))
    .orderBy(F.desc("receita_total"))
    .limit(3)
    .show(truncate=False)
)

# Evolução mensal de receita
print("\n--- Receita mensal ---")
(
    df_transformado
    .groupBy("mes")
    .agg(F.sum("valor_total").alias("receita_mensal"))
    .withColumn("receita_mensal", F.round("receita_mensal", 2))
    .orderBy("mes")
    .show(truncate=False)
)

# =============================================================================
# PARTE 5 — Escrita de dados (Parquet)
# =============================================================================
# Parquet é o formato padrão em pipelines de dados modernos:
# - Columnar: leitura eficiente de colunas específicas
# - Compressão nativa: reduz custo de armazenamento em S3
# - Suporte nativo no AWS Glue, Athena e Redshift Spectrum

OUTPUT_PATH = "labs/lab-01-spark-fundamentals/data/output"

print(f"\n[PARTE 5] Escrevendo resultado em Parquet: {OUTPUT_PATH}")

(
    df_transformado
    .write
    .mode("overwrite")
    .partitionBy("categoria")          # particionamento por categoria
    .parquet(OUTPUT_PATH)
)

print("Escrita concluída. Partições criadas:")

# Lê de volta para validar
df_parquet = spark.read.parquet(OUTPUT_PATH)
print(f"Registros lidos do Parquet: {df_parquet.count()}")
df_parquet.show(5, truncate=False)

# =============================================================================
# PARTE 6 — Spark SQL
# =============================================================================
# O Spark permite usar SQL padrão sobre DataFrames,
# registrando-os como views temporárias.

print("\n[PARTE 6] Spark SQL...")

df_transformado.createOrReplaceTempView("vendas")

resultado_sql = spark.sql("""
    SELECT
        regiao,
        COUNT(id_venda)         AS qtd_vendas,
        ROUND(SUM(valor_total), 2) AS receita_total
    FROM vendas
    GROUP BY regiao
    ORDER BY receita_total DESC
""")

print("\n--- Receita por região (via SQL) ---")
resultado_sql.show(truncate=False)

# =============================================================================
# Encerramento
# =============================================================================
spark.stop()
print("\n✅ Lab 01 concluído com sucesso!")
print("   Conceitos praticados:")
print("   - SparkSession e configuração local")
print("   - Leitura de CSV com schema explícito")
print("   - Lazy evaluation e DAG de execução")
print("   - Transformações: withColumn, filter, select")
print("   - Agregações: groupBy, agg, sum, avg, count")
print("   - Escrita em Parquet com particionamento")
print("   - Spark SQL sobre views temporárias")
