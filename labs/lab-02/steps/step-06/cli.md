## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04.

**1. Descreva o crawler em um arquivo:**

```bash
cat > crawler-fontes.json <<JSON
{
  "Name": "workshop-lab-02-fontes",
  "Role": "${ROLE}",
  "DatabaseName": "${DB}",
  "TablePrefix": "raw_",
  "Targets": {"S3Targets": [
    {"Path": "s3://${BUCKET}/pedidos/"},
    {"Path": "s3://${BUCKET}/clientes/"},
    {"Path": "s3://${BUCKET}/fornecedores/"}
  ]},
  "Schedule": "cron(0 6 * * ? *)",
  "SchemaChangePolicy": {"UpdateBehavior": "LOG", "DeleteBehavior": "LOG"}
}
JSON
```

**2. Crie o crawler e confira a agenda e a política:**

```bash
aws glue create-crawler --cli-input-json file://crawler-fontes.json
aws glue get-crawler --name workshop-lab-02-fontes \
  --query 'Crawler.{Agenda: Schedule, Politica: SchemaChangePolicy, Prefixo: TablePrefix}'
```

A agenda aparece com o estado `SCHEDULED`.

**3. Execute agora, sem esperar a agenda:**

```bash
aws glue start-crawler --name workshop-lab-02-fontes
while [ "$(aws glue get-crawler --name workshop-lab-02-fontes --query Crawler.State --output text)" != "READY" ]; do
  sleep 10
done
aws glue get-crawler --name workshop-lab-02-fontes --query 'Crawler.LastCrawl.Status' --output text
aws glue get-tables --database-name "$DB" \
  --query 'TableList[].[Name, Parameters.classification, PartitionKeys[0].Name]' --output table
```

Clique em **Validar**.

> [!TIP] Com três fontes, a execução leva cerca de 2 minutos e o estado passa por `RUNNING` e `STOPPING` antes de voltar a `READY`.
