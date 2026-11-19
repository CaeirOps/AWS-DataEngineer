# Finalizar o módulo

Clique em **Finalizar Lab** para excluir a stack `workshop-lab-01`. A exclusão leva de 1 a 3 minutos.

## O que é removido

- Os buckets `raw` e `curated`, com todos os objetos, versões e delete markers. A função de preparação esvazia os dois antes da exclusão.
- Os Access Points dos dois buckets, inclusive o `analytics`.
- As funções Lambda, as roles do IAM e os grupos de logs criados pela stack.
- A notificação de eventos, a regra de Lifecycle e a configuração de replicação, que somem com o bucket.

## O que você precisa remover

Se fez a prática opcional de replicação, remova o bucket de destino e a role de replicação. Pela CLI:

```bash
DR_BUCKET="workshop-lab-01-dr-${ACCOUNT}-${DR_REGION}"
aws s3api list-object-versions --bucket "$DR_BUCKET" --region "$DR_REGION" \
  --query '{Objects: [Versions, DeleteMarkers][][].{Key: Key, VersionId: VersionId}}' \
  --output json > dr-versoes.json
aws s3api delete-objects --bucket "$DR_BUCKET" --region "$DR_REGION" --delete file://dr-versoes.json
aws s3api delete-bucket --bucket "$DR_BUCKET" --region "$DR_REGION"
aws iam delete-role-policy --role-name workshop-lab-01-replicacao --policy-name replicacao
aws iam delete-role --role-name workshop-lab-01-replicacao
```

Se o bucket estiver vazio, o `delete-objects` falha. Nesse caso, siga direto para o `delete-bucket`. No console, esvazie o bucket com a opção **Empty**, apague-o com **Delete** e remova no IAM a role `s3crr_role_for_...` criada pelo console.

Apague também os arquivos JSON que você criou no seu computador na trilha CLI.

> [!WARNING] Se a exclusão da stack falhar, abra a stack no console do CloudFormation, veja o evento com status `DELETE_FAILED` e tente de novo. O motivo mais comum é um objeto gravado nos buckets durante a exclusão.
