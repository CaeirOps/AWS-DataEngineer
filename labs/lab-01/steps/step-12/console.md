## Passos no console

1. No bucket `raw`, abra `clientes/`, marque `cliente-0042.json` e clique em **Delete**. Confirme digitando `delete`.
2. Volte para `clientes/`. O arquivo sumiu da lista. Agora ligue a chave **Show versions**: aparecem a versão com os dados (*Version ID* `null`) e um **Delete marker**, que é a versão atual.
3. Com **Show versions** ligado, marque a linha do delete marker e a linha da versão `null` de `cliente-0042.json` e clique em **Delete**.
4. O console avisa que a exclusão de versões é definitiva. Digite `permanently delete` e confirme.
5. Confira, ainda com **Show versions**, que não sobrou nenhuma linha de `cliente-0042.json`. Clique em **Validar**.

## O que explorar nesta tela

- Com **Show versions** ligado, compare as colunas **Version ID**, **Type** e **Last modified**.
- Para "desfazer" uma exclusão comum, basta apagar o delete marker: a versão anterior volta a ser a atual. Teste isso, se quiser, com um arquivo seu.
- Na aba **Management**, veja a sua regra de Lifecycle: as versões antigas de `pedidos/` seriam apagadas sozinhas, mas a exclusão de um titular não pode esperar 30 dias.
