## Passos no console

1. No bucket `raw`, abra a aba **Properties** e vá até **Event notifications**. Clique em **Create event notification**.
2. Preencha:
   - **Event name:** `pedidos-csv`
   - **Prefix:** `pedidos/`
   - **Suffix:** `.csv`
   - **Event types:** marque **All object create events**
3. Em **Destination**, escolha **Lambda function** e selecione `workshop-lab-01-indexador`. Clique em **Save changes**.
4. Abra `pedidos/dt=2026-03-10/`, marque o CSV e escolha **Actions > Copy**. Em **Destination**, digite `s3://workshop-lab-01-raw-<conta>-<region>/pedidos/dt=2026-03-11/pedidos-2026-03-11.csv` e clique em **Copy**.
5. Abra o bucket `curated` e entre em `resumos/pedidos/dt=2026-03-11/`. Abra o JSON e veja as linhas e o total pago.
6. Clique em **Validar**.

## O que explorar nesta tela

- No [console do Lambda](https://console.aws.amazon.com/lambda/), abra a função `workshop-lab-01-indexador`. O diagrama mostra o S3 como gatilho.
- Em **Configuration > Permissions > Resource-based policy statements**, veja a permissão que o console criou para o `s3.amazonaws.com`, com a condição do bucket e da conta.
- Em **Monitor > View CloudWatch logs**, veja a linha `resumo_gravado` de cada execução.
- Na tela do evento do S3, veja que o destino também pode ser uma fila SQS ou um tópico SNS, e que a opção **Amazon EventBridge** fica numa seção separada da aba Properties.
