# Finalizar o módulo

Clique em **Finalizar Lab** para excluir a stack `workshop-lab-02`. A exclusão leva de 1 a 3 minutos.

## O que é removido

- Os **crawlers** `workshop-lab-02-*` que você criou, as **tabelas e partições** do database e as **conexões** `workshop-lab-02-*`. Eles não pertencem à stack, mas a função de preparação apaga todos antes de a stack remover o database.
- O bucket de dados, com todo o conteúdo.
- O database, a role do crawler, a função Lambda e o grupo de logs criados pela stack.

## O que você precisa remover

Se fez a prática opcional do banco relacional, remova **tudo** o que criou fora da stack, pois o banco cobra por hora enquanto existir. Pela CLI:

```bash
aws rds delete-db-instance --db-instance-identifier workshop-lab-02-banco \
  --skip-final-snapshot --delete-automated-backups
aws rds wait db-instance-deleted --db-instance-identifier workshop-lab-02-banco
aws rds delete-db-subnet-group --db-subnet-group-name workshop-lab-02-subnets
aws secretsmanager delete-secret --secret-id workshop-lab-02-banco \
  --force-delete-without-recovery
aws ec2 delete-security-group --group-id "$SG_BANCO"
```

No console, exclua a instância em **RDS > Databases > Actions > Delete** (desmarque a criação do snapshot final e confirme), depois o secret em **Secrets Manager** com exclusão imediata, e por fim o grupo de sub-redes e o security group.

> [!WARNING] Um banco RDS parado por você é religado automaticamente depois de 7 dias e volta a cobrar. Exclua, não apenas pare.

Apague também os arquivos JSON criados no seu computador na trilha CLI.

> [!WARNING] Se a exclusão da stack falhar, abra a stack no console do CloudFormation, veja o evento `DELETE_FAILED` e tente de novo. O motivo mais comum é um crawler ainda em execução: espere terminar ou pare-o.
