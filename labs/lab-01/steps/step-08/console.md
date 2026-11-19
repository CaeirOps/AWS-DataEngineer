## Passos no console

1. No bucket `raw`, abra a aba **Management** e clique em **Create lifecycle rule**.
2. Em **Lifecycle rule name**, use `pedidos-retencao`.
3. Em **Choose a rule scope**, escolha **Limit the scope of this rule using one or more filters** e, em **Prefix**, digite `pedidos/`.
4. Em **Lifecycle rule actions**, marque:
   - **Transition current versions of objects between storage classes**
   - **Expire current versions of objects**
   - **Permanently delete noncurrent versions of objects**
5. Em **Transition current versions**, adicione duas transições: **Standard-IA** com **30** dias e **Glacier Instant Retrieval** com **90** dias. Marque a caixa que confirma o custo das transições.
6. Em **Expire current versions of objects**, informe **365** dias.
7. Em **Permanently delete noncurrent versions of objects**, informe **30** dias em **Days after objects become noncurrent** e deixe vazio o número de versões a manter.
8. Revise a linha do tempo no fim da página, clique em **Create rule** e depois em **Validar**.

## O que explorar nesta tela

- Em **Object size**, veja o filtro por tamanho mínimo e máximo. Ele é útil para não transicionar objetos pequenos.
- Em **Filter type**, veja que a regra também pode ser limitada por tags dos objetos.
- Repare na ação **Delete expired object delete markers or incomplete multipart uploads**. Apagar uploads multipart incompletos é uma boa prática em todo bucket.
- A linha do tempo mostra a ordem das ações das versões atuais e das versões antigas.
