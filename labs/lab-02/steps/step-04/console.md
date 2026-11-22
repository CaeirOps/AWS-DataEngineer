## Passos no console

1. Abra o [console do AWS Glue](https://console.aws.amazon.com/glue/) e confira a Region no canto superior direito.
2. No menu lateral, em **Data Catalog**, abra **Crawlers** e clique em **Create crawler**.
3. **Set crawler properties:** em **Name**, digite `workshop-lab-02-pedidos` e clique em **Next**.
4. **Choose data sources and classifiers:** em **Is your data already mapped to Glue tables?**, escolha **Not yet**. Clique em **Add a data source**:
   - **Data source:** **S3**
   - **Location of S3 data:** **In this account**
   - **S3 path:** clique em **Browse S3**, escolha o bucket `workshop-lab-02-dados-<conta>-<region>` e a pasta `pedidos/`. O caminho termina em `/pedidos/`.
   - **Subsequent crawler runs:** **Crawl all sub-folders**
   - Clique em **Add an S3 data source** e depois em **Next**.
5. **Configure security settings:** em **Existing IAM role**, escolha `workshop-lab-02-crawler-<region>` e clique em **Next**.
6. **Set output and scheduling:** em **Target database**, escolha `workshop-lab-02-anycompany`. Em **Crawler schedule**, deixe **On demand**. Clique em **Next** e depois em **Create crawler**.
7. Na página do crawler, clique em **Run crawler**. A execução leva de 1 a 2 minutos. Espere o **State** voltar para **Ready** e confira a coluna **Last run** com o status **Succeeded**.
8. Em **Data Catalog > Databases**, abra `workshop-lab-02-anycompany` e a tabela `pedidos`. Clique em **Validar**.

## O que explorar nesta tela

- Na tabela `pedidos`, veja o **Schema**: os tipos que o crawler inferiu (`bigint`, `double`, `string`) e a coluna `dt` marcada como **Partition key**.
- Abra a aba **Partitions** e veja uma linha por data, cada uma com a própria localização no S3.
- Em **Advanced properties**, veja a `classification` (`csv`), o delimitador e a SerDe que o Athena vai usar para ler os arquivos.
- Na página do crawler, abra **Crawler runs** e veja quantas tabelas e partições cada execução criou, e o link para os logs no CloudWatch.
