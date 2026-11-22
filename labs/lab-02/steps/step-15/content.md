# Finalizar o módulo

Clique em **Finalizar Lab** para excluir a stack `workshop-lab-02`. A exclusão leva de 1 a 3 minutos.

## O que é removido

- Os **crawlers** `workshop-lab-02-*` que você criou e as **tabelas e partições** do database. Eles não pertencem à stack, mas a função de preparação apaga todos antes de a stack remover o database.
- Os logs dos crawlers `workshop-lab-02-*` no grupo `/aws-glue/crawlers`. O grupo em si fica: ele é o padrão do Glue e pode servir a outros crawlers da sua conta. Vazio, ele não gera custo.
- O bucket de dados, com todo o conteúdo.
- O database, a role do crawler, a função Lambda e o grupo de logs criados pela stack.

## O que você precisa remover

Apague os arquivos JSON e CSV criados no seu computador na trilha CLI.

> [!WARNING] Se a exclusão da stack falhar, abra a stack no console do CloudFormation, veja o evento `DELETE_FAILED` e tente de novo. O motivo mais comum é um crawler ainda em execução: espere terminar ou pare-o. Depois de corrigir a causa, clique de novo em **Finalizar Lab**: o CloudFormation chama outra vez a limpeza.
