## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04.

```bash
aws s3api put-bucket-versioning --bucket "$RAW" --versioning-configuration Status=Enabled
aws s3api get-bucket-versioning --bucket "$RAW"
```

A saída esperada é:

```json
{
    "Status": "Enabled"
}
```

Veja as versões dos objetos que já existiam. Eles aparecem com `VersionId` igual a `null`, porque foram gravados antes do versionamento:

```bash
aws s3api list-object-versions --bucket "$RAW" --prefix clientes/ \
  --query 'Versions[].{Chave: Key, Versao: VersionId, Atual: IsLatest}' --output table
```

Clique em **Validar**.
