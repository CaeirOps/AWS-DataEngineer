# Eventos do S3 e AWS Lambda

Em vez de agendar um job que procura arquivos novos, o S3 pode **avisar** quando um objeto é criado ou apagado. Esse aviso dispara o processamento na hora.

## S3 Event Notifications ou Amazon EventBridge

| | S3 Event Notifications | Amazon EventBridge |
|---|---|---|
| Destinos | AWS Lambda, Amazon SQS, Amazon SNS | Mais de 20 tipos de destino |
| Filtros | Prefixo e sufixo da chave | Qualquer campo do evento (tamanho, metadados, nome) |
| Vários destinos para o mesmo evento | Não, sem sobreposição de filtros | Sim, várias regras |
| Recursos extras | | Arquivar e reenviar eventos (*archive and replay*) |

Para ligar o EventBridge, você ativa a opção no bucket e cria as regras no EventBridge. Os eventos de orquestração aparecem no Módulo 12.

> [!EXAM] Um único destino com filtro por prefixo ou sufixo pede S3 Event Notifications. Vários destinos para o mesmo evento, filtros por outros campos ou reprocessamento de eventos pedem o EventBridge.

## Como a entrega funciona

- **Pelo menos uma vez:** o mesmo evento pode chegar duas vezes. O processamento precisa ser **idempotente**.
- **Sem ordem garantida:** dois arquivos gravados quase juntos podem chegar à Lambda em qualquer ordem.
- **Invocação assíncrona:** o S3 chama a Lambda de forma assíncrona. Se a função falhar, a Lambda tenta de novo duas vezes. Configure uma *on-failure destination* ou uma fila de mensagens com falha (DLQ) para não perder eventos.
- **Permissão:** o S3 só consegue chamar a função se a *resource-based policy* da Lambda permitir o principal `s3.amazonaws.com`, de preferência limitado ao bucket (`SourceArn`) e à conta (`SourceAccount`). O console cria essa permissão por você. Na CLI, você mesmo cria.

> [!WARNING] Se a Lambda grava no mesmo bucket e prefixo que disparam o evento, ela chama a si mesma em laço infinito, e cada execução cobra. A função deste módulo grava em outro bucket (`curated`), e o filtro do evento aceita só `pedidos/*.csv`.

## A função indexador

A função já foi criada pela stack. Ela lê o CSV, conta as linhas e soma o valor dos pedidos pagos:

```python
def handler(event, context):
    for registro in event.get("Records", []):
        bucket = registro["s3"]["bucket"]["name"]
        chave = urllib.parse.unquote_plus(registro["s3"]["object"]["key"])
        corpo = s3.get_object(Bucket=bucket, Key=chave)["Body"].read().decode("utf-8")
        linhas = list(csv.DictReader(io.StringIO(corpo)))
        total = sum(float(l["valor"]) for l in linhas if l.get("status") == "pago")
        destino = "resumos/" + chave[: -len(".csv")] + ".json"
        s3.put_object(Bucket=DESTINO, Key=destino, Body=json.dumps({...}))
```

Repare em três detalhes:

1. A chave chega codificada para URL (um espaço vira `+`), por isso o `unquote_plus`.
2. O resumo tem uma chave fixa por arquivo. Se o evento chegar duas vezes, o resumo é sobrescrito com o mesmo conteúdo: o processamento é idempotente.
3. A role da função só pode ler `raw/pedidos/` e gravar em `curated/resumos/` (privilégio mínimo).

## Quando a Lambda não é a melhor escolha

| Limite da Lambda | Valor |
|---|---|
| Tempo máximo de execução | 15 minutos |
| Memória | até 10.240 MB |
| Armazenamento temporário em `/tmp` | até 10.240 MB |

Para arquivos grandes ou transformações pesadas, o evento pode disparar um job do AWS Glue ou uma Step Function em vez de processar dentro da Lambda (Módulos 04 e 12).

> [!TIP] A Lambda é ótima para tarefas curtas por arquivo: validar, resumir, mover ou iniciar outro processo. Para transformar gigabytes, use um motor distribuído.
