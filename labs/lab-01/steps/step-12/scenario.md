# Atender um pedido de exclusão

O cliente `cliente-0042` pediu a exclusão dos seus dados pessoais. Apague de forma definitiva o arquivo `clientes/cliente-0042.json` do bucket `raw`, incluindo **todas as versões** e qualquer delete marker. Os cadastros dos outros clientes precisam continuar onde estão.

Comece apagando o arquivo do jeito comum e observe o que o versionamento faz. Depois termine a exclusão.

**Critério de validação:** não existe nenhuma versão nem delete marker de `cliente-0042.json` no bucket, e `cliente-0041.json` e `cliente-0043.json` continuam como versões atuais em `clientes/`.
