## Passos no console

1. No menu lateral do console do S3, abra **Access Points** e clique em **Create access point**.
2. Preencha:
   - **Access point name:** `analytics`
   - **Bucket name:** clique em **Browse S3** e escolha `workshop-lab-01-curated-<conta>-<region>`
   - **Network origin:** **Internet**
   - **Block Public Access settings for this Access Point:** deixe as quatro opções marcadas
3. Em **Access point policy**, cole a política abaixo trocando `<conta>` pelo id da sua conta e `<region>` pela Region do workshop. O ARN da role também aparece nos outputs da stack.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AnalistaLeResumos",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::<conta>:role/workshop-lab-01-analista-<region>"},
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:<region>:<conta>:accesspoint/analytics/object/resumos/*"
    }
  ]
}
```

4. Clique em **Create access point** e depois em **Validar**.

## O que explorar nesta tela

- Abra o Access Point e veja o **Access point alias**. Ele pode ser usado no lugar do nome do bucket em ferramentas que não aceitam ARN.
- Na criação, veja a opção **Virtual private cloud (VPC)** em **Network origin**: com ela, o Access Point só aceita requisições daquela VPC.
- No bucket `curated`, aba **Permissions**, leia a bucket policy: a instrução `DelegarLeituraAosAccessPointsDaConta` usa a condição `s3:DataAccessPointAccount` para deixar os Access Points decidirem o acesso de leitura.
