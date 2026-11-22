## Passos no console

1. Em **Data Catalog > Crawlers**, clique em **Create crawler** e use o nome `workshop-lab-02-fontes`.
2. Em **Choose data sources and classifiers**, escolha **Not yet** e adicione **três** fontes S3, uma de cada vez, com **Add a data source**: `.../pedidos/`, `.../clientes/` e `.../fornecedores/`.
3. Em **Configure security settings**, escolha a role `workshop-lab-02-crawler-<region>`.
4. Em **Set output and scheduling**:
   - **Target database:** `workshop-lab-02-anycompany`
   - **Table name prefix:** `raw_`
   - **Crawler schedule:** **Custom** e a expressão `cron(0 6 * * ? *)`
   - Abra **Advanced options**. Em **When the crawler detects schema changes in the data store, how should AWS Glue handle table updates in the data catalog?**, escolha **Ignore the change and don't update the table in the data catalog**. Em **How should AWS Glue handle deleted objects in the data store?**, escolha **Ignore the change and don't update the table in the data catalog**.
5. Clique em **Next** e em **Create crawler**. Na página do crawler, clique em **Run crawler** e espere o estado **Ready** com o último status **Succeeded**.
6. Confira em **Tables** as tabelas `raw_pedidos`, `raw_clientes` e `raw_fornecedores` e clique em **Validar**.

## O que explorar nesta tela

- Na tabela `raw_clientes`, veja que a `classification` é `json` e que o tipo de `aceita_marketing` é `boolean`: o crawler leu os valores para inferir o tipo.
- Compare `pedidos` (step 04) com `raw_pedidos`: os dois apontam para os mesmos arquivos. O catálogo guarda só metadados, então duas tabelas sobre os mesmos dados não duplicam nada no S3.
- Na tela de agenda, veja as opções prontas (**Hourly**, **Daily**, **Weekly**, **Monthly**) e repare que a expressão personalizada está em UTC.
- Em **Advanced options**, veja também **Create a single schema for each S3 path**, que junta pastas parecidas em uma só tabela.
