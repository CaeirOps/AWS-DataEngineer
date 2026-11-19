# Batch, streaming, estado e replayability

## Batch e streaming

- **Batch:** processa um conjunto de dados acumulado, em intervalos. Exemplo: às 2h, um job lê o CSV de estoque do dia anterior e atualiza as tabelas de análise.
- **Streaming:** processa cada evento, ou pequenos grupos de eventos, logo que chegam. Exemplo: atualizar a cada segundo o painel de produtos mais vistos no site.

A escolha depende de quanto tempo o negócio aceita esperar pelo dado (latência), não da tecnologia que o time prefere. Muitos pipelines usam os dois: streaming para o painel ao vivo e batch para o fechamento contábil do dia.

## Stateless e stateful

Uma transformação **stateless** (sem estado) trata cada registro de forma independente. Para processar um evento, ela não precisa saber nada dos eventos anteriores.

- Exemplos: descartar eventos de robôs, converter o fuso horário de `ts`, mascarar o e-mail do cliente.
- Escala com facilidade: qualquer worker processa qualquer registro.

Uma transformação **stateful** (com estado) depende de informação acumulada de registros anteriores.

- Exemplos: somar as vendas de cada loja nos últimos 5 minutos (janela), remover eventos duplicados, juntar o evento de pagamento com o de pedido.
- Precisa guardar o estado em algum lugar e recuperá-lo depois de uma falha. O Amazon Managed Service for Apache Flink, por exemplo, salva o estado da aplicação em checkpoints.

> [!EXAM] Quando o enunciado fala em agregação por janela de tempo, deduplicação ou junção entre fluxos, o processamento é stateful. Filtros e conversões registro a registro são stateless.

O termo também aparece em transações e protocolos. Uma API stateless recebe em cada requisição tudo o que precisa. Uma conexão stateful, como uma sessão de banco de dados, guarda contexto entre as requisições.

## Replayability

*Replayability* é a capacidade de processar de novo os dados de um período, a partir da fonte, e chegar ao resultado correto. Na prática, você precisa disso quando:

- um bug na transformação gravou valores errados e é preciso recalcular;
- uma nova regra de negócio precisa ser aplicada aos dados históricos;
- um consumidor ficou fora do ar e precisa recuperar o que perdeu.

Três condições tornam um pipeline reprocessável:

1. **A fonte guarda os dados.** O Amazon Kinesis Data Streams retém os registros por 24 horas por padrão, com retenção configurável até 365 dias, e permite ler a partir de um horário. No Apache Kafka (e no Amazon MSK), a retenção é configurável por tópico e o consumidor pode voltar o offset. Em batch, a camada bruta (*raw*) no Amazon S3 guarda os arquivos originais sem alteração.
2. **O processamento é idempotente.** Processar o mesmo dado duas vezes deixa o mesmo resultado. Exemplo: reprocessar 10/03 sobrescreve a partição `dt=2026-03-10` em vez de somar as vendas de novo.
3. **A saída permite substituir um período.** Gravar por partição de data facilita trocar só os dias afetados.

> [!TIP] Mantenha os dados brutos imutáveis e separados dos dados tratados. Se a transformação errar, você sempre pode recomeçar a partir deles.

> [!WARNING] Um job que só acrescenta linhas (*append*), sem chave nem partição para substituir, não é idempotente. Rodar o reprocessamento duplica os dados.
