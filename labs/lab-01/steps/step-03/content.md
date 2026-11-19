# O S3 como base do data lake

O Amazon S3 é um armazenamento de **objetos**. Cada objeto tem uma chave (o "nome" completo, como `pedidos/dt=2026-03-10/pedidos.csv`), os dados e metadados. Não existem pastas de verdade: o console mostra os prefixos separados por `/` como se fossem pastas.

## Por que o data lake fica no S3

- **Durabilidade:** o S3 Standard foi projetado para 99,999999999% (11 noves) de durabilidade, guardando os dados em várias zonas de disponibilidade.
- **Escala e custo:** você paga pelo que guarda e pelas requisições, sem provisionar capacidade.
- **Consistência forte:** depois de gravar ou sobrescrever um objeto, toda leitura seguinte já vê a versão nova.
- **Separação entre armazenamento e processamento:** o mesmo dado é lido pelo Athena, pelo Glue, pelo EMR e pelo Redshift Spectrum, cada um quando precisar.

![Camadas raw e curated e o fluxo do evento até a Lambda](assets/camadas-e-eventos.svg)

## Camadas

| Camada | Conteúdo | Regra |
|---|---|---|
| **raw** | Os arquivos como chegaram da fonte | Imutável: nunca altere, só acrescente |
| **curated** | Dados limpos, convertidos e organizados para consulta | Pode ser reconstruída a partir da raw |

Muitas empresas usam também uma camada intermediária (às vezes chamada *trusted* ou *silver*). O nome importa menos que a regra: a raw é a fonte para reprocessar tudo, como você viu no Módulo 00.

> [!TIP] Organize os dados por prefixos de partição, como `pedidos/dt=2026-03-10/`. O formato `coluna=valor` é reconhecido pelo AWS Glue e pelo Athena, que você usa nos Módulos 02 e 03.

## Classes de armazenamento

| Classe | Acesso | Duração mínima cobrada | Observação |
|---|---|---|---|
| S3 Standard | Frequente | Nenhuma | Padrão, várias zonas |
| S3 Intelligent-Tiering | Variável ou desconhecido | Nenhuma | Move entre camadas sozinho, com taxa de monitoramento por objeto |
| S3 Standard-IA | Pouco frequente, leitura imediata | 30 dias | Cobra por GB lido |
| S3 One Zone-IA | Pouco frequente, dado que pode ser recriado | 30 dias | Uma única zona de disponibilidade |
| S3 Glacier Instant Retrieval | Raro, leitura em milissegundos | 90 dias | Bom para arquivos consultados poucas vezes por ano |
| S3 Glacier Flexible Retrieval | Arquivo, leitura em minutos ou horas | 90 dias | Precisa restaurar antes de ler |
| S3 Glacier Deep Archive | Arquivo de longo prazo, leitura em até 12 horas ou mais | 180 dias | Menor preço por GB |
| S3 Express One Zone | Latência de um dígito de milissegundo | Nenhuma | Directory buckets, uma zona |

> [!EXAM] Associe a classe ao padrão de acesso descrito: "acesso imprevisível" leva ao Intelligent-Tiering, "raramente acessado, mas precisa estar disponível na hora" leva ao Glacier Instant Retrieval, "pode ser recriado" permite One Zone-IA, e "retenção de anos para auditoria" leva ao Deep Archive.

> [!COST] As classes IA e Glacier cobram uma duração mínima e, em geral, uma taxa por GB lido. Mover para elas um dado que é lido todo dia, ou apagá-lo antes da duração mínima, sai mais caro que deixá-lo no Standard.

## S3 ou outro armazenamento?

| Necessidade | Escolha típica |
|---|---|
| Arquivos de qualquer formato, em qualquer volume, lidos por vários motores | Amazon S3 |
| Disco de baixa latência para uma instância EC2 | Amazon EBS |
| Sistema de arquivos compartilhado por várias instâncias | Amazon EFS |
| Leitura e gravação de itens por chave, em milissegundos | Amazon DynamoDB (Módulo 08) |
| SQL analítico com alto desempenho sobre dados estruturados | Amazon Redshift (Módulo 10) |

## O S3 como fonte batch

Quase todo pipeline batch começa lendo do S3: um job do Glue lê os CSVs do dia, o Athena consulta uma partição, o Redshift carrega com `COPY`. Nos próximos steps, uma Lambda vai ler cada arquivo novo assim que ele chegar.
