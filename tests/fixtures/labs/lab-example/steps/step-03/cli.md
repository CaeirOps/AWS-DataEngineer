## Trilha CLI

Cria o bucket S3 (substitua `<SUFIXO>` por um valor único):

```bash
aws s3api create-bucket --bucket workshop-example-<SUFIXO> --profile "$AWS_PROFILE" --region "$AWS_REGION"
```

Confirma que o bucket existe:

```bash
aws s3api head-bucket --bucket workshop-example-<SUFIXO> --profile "$AWS_PROFILE" --region "$AWS_REGION"
```
