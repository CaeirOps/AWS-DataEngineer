## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04. Escolha uma Region de destino diferente da do workshop.

```bash
export DR_REGION=<region-de-destino>    # por exemplo sa-east-1
DR_BUCKET="workshop-lab-01-dr-${ACCOUNT}-${DR_REGION}"
```

**1. Crie o bucket de destino com versionamento e Block Public Access:**

```bash
aws s3api create-bucket --bucket "$DR_BUCKET" --region "$DR_REGION" \
  --create-bucket-configuration LocationConstraint="$DR_REGION"
aws s3api put-public-access-block --bucket "$DR_BUCKET" --region "$DR_REGION" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket "$DR_BUCKET" --region "$DR_REGION" \
  --versioning-configuration Status=Enabled
```

Se a Region de destino for `us-east-1`, omita o `--create-bucket-configuration`.

**2. Crie a role de replicação:**

```bash
cat > confianca-replicacao.json <<'JSON'
{"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
  "Principal": {"Service": "s3.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
JSON

cat > politica-replicacao.json <<JSON
{"Version": "2012-10-17", "Statement": [
  {"Effect": "Allow", "Action": ["s3:GetReplicationConfiguration", "s3:ListBucket"],
   "Resource": "arn:aws:s3:::${RAW}"},
  {"Effect": "Allow", "Action": ["s3:GetObjectVersionForReplication", "s3:GetObjectVersionAcl", "s3:GetObjectVersionTagging"],
   "Resource": "arn:aws:s3:::${RAW}/*"},
  {"Effect": "Allow", "Action": ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ReplicateTags"],
   "Resource": "arn:aws:s3:::${DR_BUCKET}/*"}
]}
JSON

aws iam create-role --role-name workshop-lab-01-replicacao \
  --assume-role-policy-document file://confianca-replicacao.json
aws iam put-role-policy --role-name workshop-lab-01-replicacao --policy-name replicacao \
  --policy-document file://politica-replicacao.json
```

**3. Crie a regra no bucket `raw`:**

```bash
cat > replicacao.json <<JSON
{"Role": "arn:aws:iam::${ACCOUNT}:role/workshop-lab-01-replicacao",
 "Rules": [{"ID": "dr", "Status": "Enabled", "Priority": 1, "Filter": {},
            "DeleteMarkerReplication": {"Status": "Disabled"},
            "Destination": {"Bucket": "arn:aws:s3:::${DR_BUCKET}"}}]}
JSON

aws s3api put-bucket-replication --bucket "$RAW" --replication-configuration file://replicacao.json
```

Se aparecer um erro sobre a role, espere alguns segundos (a role recém-criada pode demorar a ficar disponível) e rode de novo.

**4. Teste com um objeto novo:**

```bash
aws s3 cp "s3://${RAW}/pedidos/dt=2026-03-10/pedidos-2026-03-10.csv" \
          "s3://${RAW}/pedidos/dt=2026-03-12/pedidos-2026-03-12.csv"
sleep 30
aws s3api head-object --bucket "$RAW" --key pedidos/dt=2026-03-12/pedidos-2026-03-12.csv \
  --query ReplicationStatus
aws s3 ls "s3://${DR_BUCKET}/pedidos/" --recursive --region "$DR_REGION"
```

Clique em **Validar**. Os comandos de limpeza estão no step 17.
