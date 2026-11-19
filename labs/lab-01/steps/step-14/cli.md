## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04.

**1. Crie o Access Point:**

```bash
aws s3control create-access-point --account-id "$ACCOUNT" --name analytics --bucket "$CURATED"
```

**2. Crie a política e aplique:**

```bash
ANALISTA="arn:aws:iam::${ACCOUNT}:role/workshop-lab-01-analista-${AWS_REGION}"
AP_ARN="arn:aws:s3:${AWS_REGION}:${ACCOUNT}:accesspoint/analytics"

cat > politica-analytics.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AnalistaLeResumos",
      "Effect": "Allow",
      "Principal": {"AWS": "${ANALISTA}"},
      "Action": "s3:GetObject",
      "Resource": "${AP_ARN}/object/resumos/*"
    }
  ]
}
JSON

aws s3control put-access-point-policy --account-id "$ACCOUNT" --name analytics \
  --policy file://politica-analytics.json
aws s3control get-access-point-policy --account-id "$ACCOUNT" --name analytics --query Policy --output text
```

**3. Veja o Access Point e o alias:**

```bash
aws s3control get-access-point --account-id "$ACCOUNT" --name analytics
```

Clique em **Validar**.

> [!TIP] Para ler um objeto pelo Access Point, use o ARN dele no lugar do bucket: `aws s3api get-object --bucket "$AP_ARN" --key <chave> saida.json`. A requisição precisa vir de um principal autorizado na política, como a role analista.
