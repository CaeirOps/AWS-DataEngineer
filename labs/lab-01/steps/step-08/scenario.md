# Criar a regra de Lifecycle

O financeiro da AnyCompany quer pagar menos pelos pedidos antigos e cumprir a retenção de um ano. Crie no bucket `raw` uma regra de Lifecycle para o prefixo `pedidos/`:

| Ação | Quando |
|---|---|
| Transição para S3 Standard-IA | 30 dias depois da criação |
| Transição para S3 Glacier Instant Retrieval | 90 dias depois da criação |
| Expiração da versão atual | 365 dias depois da criação |
| Exclusão definitiva das versões antigas | 30 dias depois de deixarem de ser a versão atual |

**Critério de validação:** existe uma regra ativa com o filtro de prefixo `pedidos/` e exatamente esses dias e classes.

> [!COST] A regra não gera cobrança de transição durante o workshop: os objetos são apagados no teardown antes de completarem 30 dias, e os arquivos de exemplo são menores que 128 KB.
