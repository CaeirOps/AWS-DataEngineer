Lista os buckets para conferir o prefixo do nome:

```bash
aws s3api list-buckets --query "Buckets[].Name" --profile "$AWS_PROFILE" --region "$AWS_REGION"
```
