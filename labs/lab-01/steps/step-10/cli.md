## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04.

**1. Permita que o S3 chame a função.** A condição de bucket e de conta impede que outro bucket use esta permissão (problema do *confused deputy*):

```bash
aws lambda add-permission \
  --function-name workshop-lab-01-indexador \
  --statement-id s3-raw-pedidos \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn "arn:aws:s3:::${RAW}" \
  --source-account "$ACCOUNT"
```

**2. Crie a notificação:**

```bash
FN_ARN=$(aws lambda get-function --function-name workshop-lab-01-indexador \
  --query Configuration.FunctionArn --output text)

cat > notificacao.json <<JSON
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "pedidos-csv",
      "LambdaFunctionArn": "${FN_ARN}",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {"Key": {"FilterRules": [
        {"Name": "prefix", "Value": "pedidos/"},
        {"Name": "suffix", "Value": ".csv"}
      ]}}
    }
  ]
}
JSON

aws s3api put-bucket-notification-configuration --bucket "$RAW" \
  --notification-configuration file://notificacao.json
```

**3. Teste com um arquivo novo:**

```bash
aws s3 cp "s3://${RAW}/pedidos/dt=2026-03-10/pedidos-2026-03-10.csv" \
          "s3://${RAW}/pedidos/dt=2026-03-11/pedidos-2026-03-11.csv"
sleep 10
aws s3 ls "s3://${CURATED}/resumos/" --recursive
aws s3 cp "s3://${CURATED}/resumos/pedidos/dt=2026-03-11/pedidos-2026-03-11.json" -
aws logs tail /aws/lambda/workshop-lab-01-indexador --since 15m
```

Clique em **Validar**.

> [!WARNING] O `put-bucket-notification-configuration` substitui todas as notificações do bucket. Se o bucket já tiver outras, inclua todas no mesmo arquivo.
