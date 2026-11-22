## Passos na CLI

Defina as variáveis no terminal. Use o seu profile e a mesma Region do workshop. Elas são usadas em todas as práticas do módulo.

```bash
export AWS_PROFILE=<seu-profile>
export AWS_REGION=<region-do-workshop>    # por padrão, us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="workshop-lab-02-dados-${ACCOUNT}-${AWS_REGION}"
DB="workshop-lab-02-anycompany"
ROLE="arn:aws:iam::${ACCOUNT}:role/workshop-lab-02-crawler-${AWS_REGION}"
aws s3 ls "s3://${BUCKET}/" --recursive
```

**1. Crie o crawler** apontando para o prefixo `pedidos/`:

```bash
aws glue create-crawler \
  --name workshop-lab-02-pedidos \
  --role "$ROLE" \
  --database-name "$DB" \
  --targets "{\"S3Targets\": [{\"Path\": \"s3://${BUCKET}/pedidos/\"}]}"
```

**2. Execute e espere terminar:**

```bash
aws glue start-crawler --name workshop-lab-02-pedidos
while [ "$(aws glue get-crawler --name workshop-lab-02-pedidos --query Crawler.State --output text)" != "READY" ]; do
  sleep 10
done
aws glue get-crawler --name workshop-lab-02-pedidos --query 'Crawler.LastCrawl.[Status,ErrorMessage]' --output text
```

A saída esperada é `SUCCEEDED None`.

**3. Veja o que foi catalogado:**

```bash
aws glue get-table --database-name "$DB" --name pedidos \
  --query 'Table.{Colunas: StorageDescriptor.Columns[].[Name,Type], Particao: PartitionKeys[].Name, Formato: Parameters.classification}'
aws glue get-partitions --database-name "$DB" --table-name pedidos --query 'Partitions[].Values[]' --output text
```

Clique em **Validar**.

> [!TIP] A API devolve no campo `Role` só o nome da role, mesmo quando você cria o crawler com o ARN. Os dois jeitos funcionam.
