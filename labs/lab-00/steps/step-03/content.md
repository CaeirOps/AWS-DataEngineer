# Os 3 Vs e os tipos de dados

Antes de escolher um serviço, o engenheiro de dados descreve os dados. A forma clássica de fazer isso são os **3 Vs**.

## Volume, velocidade e variedade

| V | Pergunta | Exemplo na AnyCompany |
|---|---|---|
| **Volume** | Quanto dado existe e quanto cresce? | Milhões de linhas de pedidos por mês e terabytes de fotos de produtos |
| **Velocidade** | Com que frequência o dado chega e em quanto tempo precisa ser usado? | Eventos do site a cada segundo; CSV de estoque uma vez por dia |
| **Variedade** | Quantos formatos e estruturas diferentes existem? | Tabelas, JSON, CSV, imagens e PDF |

Alguns materiais acrescentam **veracidade** (qualidade e confiabilidade do dado) e **valor** (o que o dado entrega ao negócio). Qualidade de dados é o tema do Módulo 06.

## Estruturado, semiestruturado e não estruturado

![Fontes de dados da AnyCompany classificadas por tipo](assets/tipos-de-dados.svg)

- **Estruturado:** esquema fixo, em linhas e colunas. Exemplo: a tabela `pedidos`, com `id_pedido`, `id_loja`, `valor` e `data`. Fica bem em bancos relacionais e data warehouses, e é consultado com SQL.
- **Semiestruturado:** tem estrutura, mas ela é flexível e vem junto com o dado. Exemplos: eventos JSON do site, logs e arquivos XML. Um evento pode ter campos que outro não tem.
- **Não estruturado:** sem modelo de dados definido. Exemplos: fotos de produtos, PDFs e áudio. Normalmente fica em armazenamento de objetos, como o Amazon S3, e passa por outro processamento para extrair informação.

```json
{"evento": "add_to_cart", "id_sessao": "s-1029", "sku": "CAM-042", "ts": "2026-03-10T14:03:22Z"}
{"evento": "search", "id_sessao": "s-1029", "termo": "camiseta azul", "ts": "2026-03-10T14:02:51Z"}
```

Os dois eventos acima vêm da mesma fonte e têm campos diferentes (`sku` e `termo`). Essa é a marca do dado semiestruturado.

> [!EXAM] Questões de cenário costumam descrever os dados pelos 3 Vs sem usar o termo. "Milhares de eventos por segundo, que precisam estar disponíveis em segundos" indica alta velocidade e aponta para streaming. "Arquivos diários de vários GB" indica batch.

## Por que isso importa

As características dos dados guiam as escolhas do resto do workshop:

- **Alta velocidade** pede ingestão em streaming, como Amazon Kinesis Data Streams ou Amazon MSK (Módulo 07).
- **Grande volume em arquivos** pede um data lake no Amazon S3 com formatos colunares (Módulos 01 e 03).
- **Muita variedade** pede um catálogo de dados para descobrir e descrever cada fonte (Módulo 02).
