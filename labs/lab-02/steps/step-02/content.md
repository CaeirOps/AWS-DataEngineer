# Deploy do ambiente

Clique em **Iniciar deploy** para criar a stack `workshop-lab-02` com o AWS CloudFormation. A criação leva cerca de 1 minuto.

## O que a stack cria

| Recurso | Nome | Para que serve |
|---|---|---|
| Bucket S3 | `workshop-lab-02-dados-<conta>-<region>` | Os dados fictícios da AnyCompany, já organizados |
| Database do Glue | `workshop-lab-02-anycompany` | Database vazio onde os crawlers criam as tabelas |
| Role do IAM | `workshop-lab-02-crawler-<region>` | Role que você informa nos crawlers, com privilégio mínimo |
| Função Lambda | `workshop-lab-02-preparacao` | Grava os dados agora e limpa tudo no teardown |

O bucket já nasce com Block Public Access, criptografia SSE-S3, ACLs desligadas e uma bucket policy que recusa acesso sem TLS, como no Módulo 01.

> [!WARNING] O workshop usa a Region definida em `AWS_DEFAULT_REGION` quando você rodou o `start.py` (o padrão é `us-east-1`). O catálogo do Glue é regional: use a mesma Region no console e na CLI, ou as tabelas parecerão ter sumido.

## Os dados de exemplo

```
pedidos/dt=2026-03-08/pedidos-2026-03-08.csv
pedidos/dt=2026-03-09/pedidos-2026-03-09.csv
pedidos/dt=2026-03-10/pedidos-2026-03-10.csv
clientes/clientes.json
fornecedores/estoque-2026-03-09.csv
```

- **Pedidos:** CSV com cabeçalho e as colunas `id_pedido`, `id_loja`, `id_cliente`, `valor` e `status`, em pastas `dt=`. A data fica só no nome da pasta: ela vira a chave de partição `dt` no catálogo.
- **Clientes:** um registro JSON por linha (JSON Lines).
- **Fornecedores:** CSV de estoque com `sku`, `descricao`, `quantidade` e `preco`.

Quando o status ficar `CREATE_COMPLETE`, os outputs mostram o bucket, o database e o ARN da role do crawler. Avance para o próximo step.
