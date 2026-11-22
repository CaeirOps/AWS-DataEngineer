# Catalogar todas as fontes com agenda

Agora o time quer catalogar as três fontes da AnyCompany em uma execução diária, com as tabelas identificadas pela origem. Crie o crawler:

| Campo | Valor |
|---|---|
| Nome | `workshop-lab-02-fontes` |
| Fontes | `pedidos/`, `clientes/` e `fornecedores/` do bucket de dados, como três fontes S3 |
| Role e database | os mesmos do step 04 |
| Prefixo de tabela | `raw_` |
| Agenda | todo dia às 06:00 UTC: `cron(0 6 * * ? *)` |
| Mudança de esquema | **só registrar no log**, tanto para atualização quanto para exclusão |

Depois, execute o crawler uma vez, sem esperar a agenda.

**Critério de validação:** o crawler tem as três fontes, o prefixo `raw_` e uma agenda diária ativa, terminou uma execução com sucesso, e as tabelas `raw_pedidos`, `raw_clientes` e `raw_fornecedores` existem.

> [!TIP] Começar com "só registrar no log" é a escolha segura: nenhuma tabela muda sem você ver antes o que o crawler encontrou. No step 11 você ajusta isso.
