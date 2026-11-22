## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04.

**1. Simule a chegada do arquivo:**

```bash
aws s3 cp "s3://${BUCKET}/pedidos/dt=2026-03-10/pedidos-2026-03-10.csv" \
          "s3://${BUCKET}/pedidos/dt=2026-03-11/pedidos-2026-03-11.csv"
aws glue get-partitions --database-name "$DB" --table-name pedidos --query 'Partitions[].Values[]' --output text
```

A data nova ainda não aparece no catálogo.

**2. Monte a partição nova a partir de uma existente.** A partição repete o formato da tabela (colunas, SerDe e formato de entrada) e muda só a localização:

```bash
aws glue get-partition --database-name "$DB" --table-name pedidos --partition-values 2026-03-10 \
  --query Partition.StorageDescriptor --output json > sd-base.json
sed 's#dt=2026-03-10#dt=2026-03-11#g' sd-base.json > sd-nova.json
grep '"Location"' sd-nova.json

cat > particao.json <<JSON
[{"Values": ["2026-03-11"], "StorageDescriptor": $(cat sd-nova.json)}]
JSON
```

**3. Registre a partição:**

```bash
aws glue batch-create-partition --database-name "$DB" --table-name pedidos \
  --partition-input-list file://particao.json
aws glue get-partitions --database-name "$DB" --table-name pedidos --query 'Partitions[].Values[]' --output text
```

A resposta do `batch-create-partition` é `{"Errors": []}`. Clique em **Validar**.

> [!TIP] No Athena, o mesmo registro seria `ALTER TABLE pedidos ADD PARTITION (dt = '2026-03-11') LOCATION 's3://.../pedidos/dt=2026-03-11/'`, ou `MSCK REPAIR TABLE pedidos`, que procura todas as pastas `dt=` que faltam. Você usa o Athena no Módulo 03.
