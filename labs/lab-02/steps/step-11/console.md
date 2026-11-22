## Passos no console

1. No seu computador, crie o arquivo `estoque-2026-03-10.csv` com o conteúdo do cenário. No console do S3, entre em `fornecedores/` no bucket de dados e faça o upload dele.
2. No console do Glue, execute o crawler `workshop-lab-02-fontes` (**Run crawler**) e espere o estado **Ready**.
3. Abra a tabela `raw_fornecedores`: o esquema continua com 4 colunas. Em **Crawler runs**, abra os logs da execução e procure a mensagem sobre a mudança de esquema.
4. Abra o crawler, clique em **Edit** e vá até **Set output and scheduling > Advanced options**:
   - Em mudanças de esquema, escolha **Update the table definition in the data catalog**.
   - Em objetos excluídos, mantenha **Ignore the change and don't update the table in the data catalog**.
   - Marque **Update all new and existing partitions with metadata from the table**, se aparecer.
5. Clique em **Next** e em **Update**. Execute o crawler de novo e espere o estado **Ready**.
6. Abra a tabela `raw_fornecedores`, confira a coluna `categoria` no fim e clique em **Validar**.

## O que explorar nesta tela

- Na tabela, veja a aba **Table versions** (ou **Versions**): o Glue guarda as versões anteriores da definição da tabela, e você pode comparar o esquema antigo com o novo.
- Veja as outras opções para objetos excluídos: marcar a tabela como obsoleta ou apagá-la do catálogo. Nenhuma delas apaga os dados do S3.
