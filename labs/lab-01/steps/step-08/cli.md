## Passos na CLI

Crie o arquivo da regra:

```bash
cat > lifecycle-pedidos.json <<'JSON'
{
  "Rules": [
    {
      "ID": "pedidos-retencao",
      "Status": "Enabled",
      "Filter": {"Prefix": "pedidos/"},
      "Transitions": [
        {"Days": 30, "StorageClass": "STANDARD_IA"},
        {"Days": 90, "StorageClass": "GLACIER_IR"}
      ],
      "Expiration": {"Days": 365},
      "NoncurrentVersionExpiration": {"NoncurrentDays": 30}
    }
  ]
}
JSON
```

Aplique e confira:

```bash
aws s3api put-bucket-lifecycle-configuration --bucket "$RAW" --lifecycle-configuration file://lifecycle-pedidos.json
aws s3api get-bucket-lifecycle-configuration --bucket "$RAW"
```

A resposta do `get` mostra também `TransitionDefaultMinimumObjectSize` igual a `all_storage_classes_128K`: é o comportamento padrão que não transiciona objetos menores que 128 KB.

Clique em **Validar**.

> [!WARNING] O `put-bucket-lifecycle-configuration` substitui a configuração inteira do bucket. Para acrescentar uma regra a um bucket que já tem outras, leia a configuração atual, junte a regra nova e envie tudo.
