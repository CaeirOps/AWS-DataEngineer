# Deploy do ambiente

Clique em **Iniciar deploy** para criar a stack `workshop-lab-01` com o AWS CloudFormation. A criação leva de 1 a 2 minutos.

## O que a stack cria

| Recurso | Nome | Para que serve |
|---|---|---|
| Bucket S3 | `workshop-lab-01-raw-<conta>-<region>` | Camada raw, com os arquivos de exemplo em `entrada/` |
| Bucket S3 | `workshop-lab-01-curated-<conta>-<region>` | Camada curated, vazia no início |
| Função Lambda | `workshop-lab-01-indexador` | Resume cada CSV de pedidos (você liga o gatilho no step 10) |
| Role do IAM | `workshop-lab-01-analista-<region>` | Role do time de análise, sem permissões próprias |
| Função Lambda | `workshop-lab-01-preparacao` | Grava os dados de exemplo agora e limpa os buckets no teardown |

Os dois buckets já nascem com as configurações seguras que todo bucket deveria ter:

- **Block Public Access** ligado nas quatro opções.
- **Criptografia padrão** SSE-S3.
- **Object Ownership** em *Bucket owner enforced*, o que desliga as ACLs.
- **Bucket policy** que recusa qualquer acesso sem TLS (`aws:SecureTransport`).

> [!WARNING] O workshop usa a Region definida em `AWS_DEFAULT_REGION` quando você rodou o `start.py` (o padrão é `us-east-1`). Use a mesma Region no console e na CLI. Se procurar os buckets em outra Region, eles não vão aparecer.

## Os dados de exemplo

```
entrada/pedidos-2026-03-08.csv
entrada/pedidos-2026-03-09.csv
entrada/pedidos-2026-03-10.csv
entrada/cliente-0041.json
entrada/cliente-0042.json
entrada/cliente-0043.json
```

Cada CSV tem 12 pedidos com as colunas `id_pedido`, `id_loja`, `id_cliente`, `valor`, `status` e `dt`. Cada JSON tem o cadastro fictício de um cliente.

Quando o status ficar `CREATE_COMPLETE`, os outputs da stack mostram os nomes dos buckets, o ARN da Lambda e o ARN da role analista. Avance para o próximo step.
