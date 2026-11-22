# Tratar uma coluna nova

Um fornecedor da AnyCompany passou a enviar a coluna `categoria` no **fim** do arquivo de estoque. Grave o arquivo novo em `fornecedores/estoque-2026-03-10.csv` com o conteúdo abaixo:

```
sku,descricao,quantidade,preco,categoria
CAM-050,Meia esportiva,60,9.90,moda
CAL-009,Bermuda,25,79.90,moda
TEN-014,Tenis corrida,18,299.90,calcados
```

Depois:

1. Execute o crawler `workshop-lab-02-fontes` como está (só registra no log) e confira que a tabela `raw_fornecedores` **não** mudou.
2. Mude a política de mudança de esquema do crawler para **atualizar a tabela**, mantendo a exclusão em **só registrar**.
3. Execute o crawler de novo e confira a coluna nova.

**Critério de validação:** o crawler atualiza a tabela quando o esquema muda e não apaga tabelas, e `raw_fornecedores` tem as colunas `sku`, `descricao`, `quantidade`, `preco` e `categoria`, nessa ordem.
