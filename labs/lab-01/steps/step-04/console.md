## Passos no console

1. Abra o [console do Amazon S3](https://console.aws.amazon.com/s3/) e confira, no canto superior direito, se a Region é a do workshop.
2. Abra o bucket `workshop-lab-01-raw-<conta>-<region>` e entre em `entrada/`.
3. Volte para a raiz do bucket e use **Create folder** para criar `pedidos/`. Dentro dela, crie `dt=2026-03-08/`, `dt=2026-03-09/` e `dt=2026-03-10/`. Crie também `clientes/` na raiz.
4. Em `entrada/`, marque `pedidos-2026-03-08.csv`, escolha **Actions > Move**, clique em **Browse S3**, selecione `pedidos/dt=2026-03-08/` e confirme com **Move**. Repita para as outras duas datas.
5. Marque os três arquivos `cliente-*.json`, escolha **Actions > Move** e mova-os para `clientes/`.
6. Confira que `entrada/` ficou vazio e clique em **Validar**.

## O que explorar nesta tela

- Abra um dos CSVs e veja a aba **Properties**: classe de armazenamento, criptografia SSE-S3, tamanho e *ETag*.
- Na aba **Permissions** do bucket, confira o **Block public access**, o **Object Ownership** (*Bucket owner enforced*) e a bucket policy que recusa acesso sem TLS.
- Na aba **Properties** do bucket, veja a seção **Default encryption** e a seção **Bucket Versioning**, que você vai mudar no step 06.

> [!TIP] As "pastas" do console são só prefixos. Ao criar uma pasta, o console grava um objeto vazio com a chave terminando em `/`, para a pasta aparecer mesmo sem arquivos.
