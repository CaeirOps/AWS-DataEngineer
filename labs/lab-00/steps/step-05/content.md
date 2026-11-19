# Formatos, compressão e particionamento

Para o mesmo dado, o formato e a organização dos arquivos mudam quanto você paga e quanto a consulta demora. Este é um dos temas que mais aparecem na prova.

## Orientado a linha e orientado a coluna

![Armazenamento por linha, por coluna e com partições](assets/linha-coluna-particao.svg)

- **Por linha:** cada registro é gravado inteiro, um depois do outro. É bom para gravar e ler registros completos. CSV, JSON e Apache Avro são orientados a linha.
- **Por coluna:** os valores de cada coluna ficam juntos. Uma consulta que usa 3 de 40 colunas lê só essas 3. Apache Parquet e Apache ORC são colunares.

| Formato | Organização | Esquema | Uso típico |
|---|---|---|---|
| CSV | Linha, texto | Não tem; tipos são inferidos | Troca de arquivos com fornecedores |
| JSON | Linha, texto | Flexível, em cada registro | Eventos, APIs, logs |
| Apache Avro | Linha, binário | Junto com os dados, com evolução de esquema | Streaming e mensagens |
| Apache Parquet | Coluna, binário | Junto com os dados, com estatísticas por bloco | Data lake e consultas analíticas |
| Apache ORC | Coluna, binário | Junto com os dados | Data lake, ecossistema Hive |

Parquet guarda também o mínimo e o máximo de cada coluna por bloco (*row group*). Com essas estatísticas, o motor pula blocos que não podem ter o valor procurado (*predicate pushdown*).

## De CSV para Parquet

A conversão é uma das transformações mais comuns de um pipeline. Um exemplo em PySpark, que você vai executar no Módulo 04 com o AWS Glue:

```python
pedidos = spark.read.option("header", True).option("inferSchema", True).csv("s3://anycompany-raw/pedidos/")
(pedidos.write
    .mode("overwrite")
    .partitionBy("dt")
    .option("compression", "snappy")
    .parquet("s3://anycompany-curated/pedidos/"))
```

> [!COST] No Amazon Athena e no Amazon Redshift Spectrum, você paga pelo volume de dados escaneado. Parquet com compressão e partições reduz o volume lido e, com ele, o custo e o tempo da consulta.

## Compressão

| Codec | Taxa de compressão | Velocidade | Observação |
|---|---|---|---|
| Snappy | Menor | Muito rápido | Padrão comum em Parquet |
| gzip | Maior | Mais lento | Um `.csv.gz` não pode ser dividido entre workers |
| zstd | Alta | Rápido | Bom equilíbrio entre taxa e velocidade |
| bzip2 | Alta | Lento | Pode ser dividido, mas é pouco usado em analytics |

Dentro do Parquet, a compressão é aplicada por bloco, então o arquivo continua podendo ser lido em paralelo. Já um arquivo de texto inteiro em gzip precisa ser lido por um único worker.

> [!TIP] Prefira arquivos entre algumas dezenas e algumas centenas de MB. Milhares de arquivos pequenos aumentam o tempo de listagem e de abertura, e um único arquivo gigante limita o paralelismo.

## Particionamento

Particionar é organizar os arquivos em pastas pelo valor de uma coluna, no formato `coluna=valor`:

```
s3://anycompany-curated/pedidos/dt=2026-03-09/part-0000.snappy.parquet
s3://anycompany-curated/pedidos/dt=2026-03-10/part-0000.snappy.parquet
```

Uma consulta com `WHERE dt = '2026-03-10'` lê só a pasta daquele dia. Isso se chama *partition pruning*.

- Escolha colunas que aparecem nos filtros das consultas, como data, Region ou loja.
- Evite colunas com muitos valores distintos, como `id_pedido`: elas geram milhões de partições com arquivos minúsculos.

> [!EXAM] "Reduzir o custo e o tempo das consultas no Athena" quase sempre leva à mesma resposta: converter para Parquet ou ORC, comprimir e particionar pelas colunas usadas nos filtros.

## Indexação

Bancos de dados usam índices para encontrar linhas sem ler a tabela inteira. Um índice em `id_cliente` na tabela de pedidos permite buscar os pedidos de um cliente com poucas leituras. Cada índice, porém, ocupa espaço e deixa as gravações mais lentas, porque também precisa ser atualizado.

Data lakes não têm índices tradicionais. Neles, o mesmo papel é feito por partições, estatísticas dos arquivos e ordenação dos dados. No Amazon Redshift, as *sort keys* cumprem papel parecido (Módulo 10).
