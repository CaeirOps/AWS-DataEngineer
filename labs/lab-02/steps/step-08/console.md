## Passos no console

1. No [console do S3](https://console.aws.amazon.com/s3/), abra o bucket `workshop-lab-02-dados-<conta>-<region>` e entre em `pedidos/dt=2026-03-10/`.
2. Marque o CSV, escolha **Actions > Copy** e informe o destino `s3://workshop-lab-02-dados-<conta>-<region>/pedidos/dt=2026-03-11/pedidos-2026-03-11.csv`. Clique em **Copy**.
3. No console do Glue, abra a tabela `pedidos` e a aba **Partitions**: a data nova ainda não aparece.
4. Em **Crawlers**, abra `workshop-lab-02-pedidos` e clique em **Run crawler**. Espere o estado **Ready** com o último status **Succeeded**.
5. Volte à aba **Partitions** da tabela `pedidos`, confira a linha `2026-03-11` e clique em **Validar**.

## O que explorar nesta tela

- No crawler, clique em **Edit** e veja, na fonte S3, a opção **Subsequent crawler runs** com **Crawl new sub-folders only**. É o modo incremental. O console avisa que ele exige que as mudanças de esquema sejam só registradas no log.
- Na aba **Partitions**, clique em uma partição e veja que cada uma guarda a própria localização e o próprio esquema.
- Na tabela, aba **Indexes**, veja os índices de partição que o crawler pode criar.
