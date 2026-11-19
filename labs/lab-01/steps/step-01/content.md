# Objetivos e cenário

Neste módulo você monta o data lake da AnyCompany no Amazon S3. É o primeiro módulo com prática: os recursos são criados na sua conta AWS e removidos no fim.

## O que você vai aprender

| Skill do exame | Tema | Prática |
|---|---|---|
| 2.1.1 | Escolher o armazenamento pelo custo e pelo desempenho | Step 04 |
| 1.1.2 | Ler dados de fontes batch, como o S3 | Steps 04 e 10 |
| 2.3.4 | Versionamento do S3 | Step 06 |
| 2.3.6 | Resiliência e disponibilidade dos dados | Step 15 (opcional) |
| 2.3.2 | Lifecycle para mudar a classe de armazenamento | Step 08 |
| 2.3.3 | Expirar dados por idade | Step 08 |
| 1.1.6 | Gatilhos de eventos, como S3 Event Notifications | Step 10 |
| 3.1.8 | Automatizar o processamento com AWS Lambda | Step 10 |
| 2.3.5 | Apagar dados por exigência legal ou de negócio | Step 12 |
| 4.1.5 | Políticas do IAM em roles, endpoints e serviços, como S3 Access Points | Step 14 |

## O cenário

Os sistemas da AnyCompany jogam tudo no mesmo lugar: os arquivos diários de pedidos e os cadastros de clientes chegam misturados no prefixo `entrada/` de um bucket. O time de dados recebeu seis pedidos:

1. Organizar os arquivos em camadas e partições, para as consultas lerem só o necessário.
2. Proteger os dados brutos contra exclusão ou sobrescrita acidental.
3. Reduzir o custo dos pedidos antigos, que quase ninguém consulta depois de um mês.
4. Gerar um resumo de cada arquivo de pedidos assim que ele chegar, sem ninguém rodar nada.
5. Atender a solicitação de um cliente que pediu a exclusão dos seus dados pessoais.
6. Dar ao time de análise acesso só de leitura aos resumos.

Todos os dados do módulo são fictícios.

## Como o módulo funciona

O step 02 cria o ponto de partida na sua conta: os buckets `raw` e `curated`, os dados de exemplo, uma função Lambda pronta e uma role para o time de análise. Cada prática tem as trilhas Console e CLI, e o botão **Validar** confere o resultado na sua conta.

> [!COST] Os recursos deste módulo são pequenos: alguns KB no S3, poucas execuções da Lambda e alguns logs. A prática de replicação entre Regions (step 15) é opcional e tem custo próprio. Ao terminar, finalize o módulo no step 17.
