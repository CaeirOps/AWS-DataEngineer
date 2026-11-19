# Agendar jobs e crawlers

Manter o catálogo atualizado é uma tarefa recorrente. Existem três maneiras de disparar um crawler ou um job, e a escolha depende do que **desencadeia** o trabalho.

## Por tempo

- **Agenda do próprio crawler:** no crawler, você escolhe a frequência (de hora em hora, diária, semanal, mensal ou uma expressão cron). A expressão cron do Glue segue a forma `cron(minuto hora dia-do-mês mês dia-da-semana ano)`, em UTC, e a precisão mínima de uma agenda é de 5 minutos. Exemplo: `cron(0 6 * * ? *)` roda todo dia às 06:00 UTC, que é 03:00 em São Paulo.
- **Amazon EventBridge Scheduler (ou uma regra com agenda):** dispara qualquer destino, como um job do Glue, uma Step Function ou uma função Lambda, por expressão `rate` ou `cron`, com fuso horário configurável.
- **Apache Airflow (Amazon MWAA):** orquestra um fluxo com várias tarefas e dependências entre elas, e uma delas pode ser o crawler (Módulo 12).

## Por evento

Quando o dado chega em horários imprevisíveis, esperar a agenda atrasa o catálogo. Opções:

- **Crawler com eventos do S3** (*crawl based on events*): o S3 envia os eventos para uma fila do Amazon SQS e o crawler, depois da primeira varredura completa, lista **só as pastas citadas nos eventos**, em vez do alvo inteiro. Isso acelera a execução e reduz o custo, mas **o evento não inicia o crawler**: você ainda o executa manualmente ou por agenda.
- **Evento do S3 para uma Lambda ou EventBridge:** o evento dispara uma função que registra a partição com `BatchCreatePartition` ou inicia o crawler (Módulo 01, step 09).

## Qual escolher

| Situação | Opção |
|---|---|
| Dados chegam todo dia, perto de um horário fixo, e o crawler basta | Agenda do crawler |
| Um job depende do outro, ou há vários passos | Step Functions ou Airflow, que chamam o crawler como uma etapa |
| Chegada imprevisível e baixa latência | Evento do S3 chamando uma Lambda ou o EventBridge, que registra a partição ou inicia o crawler |
| Outros jobs e serviços precisam da mesma agenda | EventBridge Scheduler |

> [!EXAM] "Executar um crawler todos os dias às 2h" pede a agenda do crawler. "Disparar o crawler quando um arquivo chegar" pede um evento (S3 e EventBridge ou Lambda). "Várias etapas com dependências entre elas" pede orquestração (Step Functions ou Airflow).

> [!COST] Cada execução do crawler cobra no mínimo 10 minutos de DPU. Um crawler agendado de hora em hora para dados que chegam uma vez por dia desperdiça 23 execuções por dia.

> [!WARNING] Expressões cron do Glue e do EventBridge usam **UTC** por padrão. Confira o fuso antes de combinar um horário com o time.
