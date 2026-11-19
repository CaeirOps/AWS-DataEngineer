## Passos na CLI

Defina as variáveis no terminal. Use o seu profile e a mesma Region do workshop. Elas são usadas em todas as práticas do módulo.

```bash
export AWS_PROFILE=<seu-profile>
export AWS_REGION=<region-do-workshop>    # por padrão, us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
RAW="workshop-lab-01-raw-${ACCOUNT}-${AWS_REGION}"
CURATED="workshop-lab-01-curated-${ACCOUNT}-${AWS_REGION}"
echo "$RAW"
```

Veja o que chegou em `entrada/`:

```bash
aws s3 ls "s3://${RAW}/entrada/"
```

Mova cada arquivo de pedidos para a partição da data dele:

```bash
for d in 2026-03-08 2026-03-09 2026-03-10; do
  aws s3 mv "s3://${RAW}/entrada/pedidos-${d}.csv" "s3://${RAW}/pedidos/dt=${d}/pedidos-${d}.csv"
done
```

Mova os cadastros de clientes:

```bash
aws s3 mv "s3://${RAW}/entrada/" "s3://${RAW}/clientes/" --recursive --exclude "*" --include "cliente-*.json"
```

Confira o resultado e clique em **Validar**:

```bash
aws s3 ls "s3://${RAW}/" --recursive
```

> [!TIP] O `aws s3 mv` copia o objeto para a chave nova e apaga o original. No S3 não existe "renomear": toda mudança de chave é uma cópia seguida de exclusão.
