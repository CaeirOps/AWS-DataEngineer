## Passos na CLI

Se abriu um terminal novo, defina de novo as variáveis do step 04.

**1. Apague do jeito comum e veja o resultado:**

```bash
KEY=clientes/cliente-0042.json
aws s3 rm "s3://${RAW}/${KEY}"
aws s3 ls "s3://${RAW}/clientes/"
aws s3api list-object-versions --bucket "$RAW" --prefix "$KEY" \
  --query '{Versoes: Versions[].VersionId, Marcadores: DeleteMarkers[].VersionId}'
```

O arquivo sumiu da listagem, mas a versão com os dados continua lá, e há um delete marker por cima dela.

**2. Apague cada versão e cada delete marker pelo `VersionId`:**

```bash
for v in $(aws s3api list-object-versions --bucket "$RAW" --prefix "$KEY" \
             --query '[Versions, DeleteMarkers][][].VersionId' --output text); do
  [ "$v" = "None" ] && continue
  aws s3api delete-object --bucket "$RAW" --key "$KEY" --version-id "$v"
done
```

**3. Confira que não sobrou nada:**

```bash
aws s3api list-object-versions --bucket "$RAW" --prefix "$KEY"
aws s3 ls "s3://${RAW}/clientes/"
```

O primeiro comando não deve listar `Versions` nem `DeleteMarkers`. O segundo ainda mostra os outros dois clientes. Clique em **Validar**.

> [!WARNING] Confira o valor de `KEY` antes de rodar o laço. O `--prefix` pega toda chave que começa com o texto informado.
