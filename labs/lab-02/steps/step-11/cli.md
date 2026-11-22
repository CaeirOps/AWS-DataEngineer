## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04.

**1. Envie o arquivo novo:**

```bash
cat > estoque-2026-03-10.csv <<'CSV'
sku,descricao,quantidade,preco,categoria
CAM-050,Meia esportiva,60,9.90,moda
CAL-009,Bermuda,25,79.90,moda
TEN-014,Tenis corrida,18,299.90,calcados
CSV
aws s3 cp estoque-2026-03-10.csv "s3://${BUCKET}/fornecedores/estoque-2026-03-10.csv"
```

**2. Execute o crawler com a política atual e confira a tabela:**

```bash
rodar() {
  aws glue start-crawler --name workshop-lab-02-fontes
  while [ "$(aws glue get-crawler --name workshop-lab-02-fontes --query Crawler.State --output text)" != "READY" ]; do
    sleep 10
  done
  aws glue get-crawler --name workshop-lab-02-fontes --query 'Crawler.LastCrawl.Status' --output text
}
rodar
aws glue get-table --database-name "$DB" --name raw_fornecedores \
  --query 'Table.StorageDescriptor.Columns[].Name' --output text
```

A tabela continua com 4 colunas, porque a política é `LOG`.

**3. Mude a política e execute de novo:**

```bash
aws glue update-crawler --name workshop-lab-02-fontes \
  --schema-change-policy UpdateBehavior=UPDATE_IN_DATABASE,DeleteBehavior=LOG
rodar
aws glue get-table --database-name "$DB" --name raw_fornecedores \
  --query 'Table.StorageDescriptor.Columns[].[Name,Type]' --output text
```

Agora a coluna `categoria` aparece no fim. Clique em **Validar**.

**4. (Opcional) Veja as versões da tabela:**

```bash
aws glue get-table-versions --database-name "$DB" --table-name raw_fornecedores \
  --query 'TableVersions[].[VersionId, length(Table.StorageDescriptor.Columns)]' --output text
```
