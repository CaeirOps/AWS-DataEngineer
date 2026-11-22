# Descobrir o esquema dos pedidos

Os analistas da AnyCompany não sabem quais colunas o arquivo de pedidos tem. Crie e execute um crawler do AWS Glue que descubra o esquema e as partições de `pedidos/`:

| Campo | Valor |
|---|---|
| Nome do crawler | `workshop-lab-02-pedidos` |
| Fonte | `s3://workshop-lab-02-dados-<conta>-<region>/pedidos/` |
| Role do IAM | `workshop-lab-02-crawler-<region>` (criada pela stack) |
| Database de destino | `workshop-lab-02-anycompany` |
| Agenda | Sob demanda |

**Critério de validação:** o crawler terminou uma execução com sucesso, e a tabela `pedidos` existe no database com a chave de partição `dt` e as partições das três datas.

> [!COST] Cada execução do crawler cobra no mínimo 10 minutos de DPU. Execute só depois de conferir a configuração.
