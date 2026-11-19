# Objetivos e cenário

Neste módulo você constrói o **catálogo técnico** da AnyCompany com o AWS Glue Data Catalog. É o ponto em que os arquivos soltos no Amazon S3 viram tabelas que o Athena, o AWS Glue, o Amazon EMR e o Amazon Redshift conseguem consultar.

## O que você vai aprender

| Skill do exame | Tema | Prática |
|---|---|---|
| 2.2.1 | Usar catálogos para consumir dados na origem | Steps 04 e 06 |
| 2.2.2 | Construir e referenciar um catálogo técnico (Glue Data Catalog, Hive metastore) | Step 04 |
| 2.2.3 | Descobrir esquemas e popular o catálogo com crawlers | Steps 04, 06 e 11 |
| 2.2.4 | Sincronizar partições com o catálogo | Step 08 |
| 1.1.5 | Agendar jobs e crawlers (EventBridge, Apache Airflow, agendas por tempo) | Step 06 |
| 2.4.2 | Tratar mudanças nas características dos dados | Step 11 |
| 2.2.5 | Criar conexões de origem ou destino para catalogação | Step 13 (opcional) |
| 1.2.2 | Conectar a diferentes fontes de dados (JDBC, ODBC) | Step 13 (opcional) |

## O cenário

No Módulo 01, o time organizou os dados da AnyCompany no data lake. O problema agora é outro: **ninguém sabe o que existe lá dentro**. Para saber quais colunas tem o arquivo de pedidos, o analista abre o arquivo. Para saber quais datas já chegaram, ele lista as pastas. Cada ferramenta precisaria repetir esse trabalho.

O time de dados recebeu quatro pedidos:

1. Descobrir o esquema dos pedidos e registrá-lo em um catálogo que todas as ferramentas compartilhem.
2. Catalogar também os clientes e os arquivos de estoque dos fornecedores, e manter tudo atualizado todo dia.
3. Fazer a partição de uma data nova aparecer no catálogo assim que o arquivo chegar.
4. Tratar a mudança de um fornecedor que passou a enviar uma coluna a mais, sem quebrar as consultas.

Todos os dados do módulo são fictícios.

> [!COST] Os crawlers do AWS Glue cobram por DPU-hora, com **mínimo de 10 minutos por execução**. Neste módulo você executa cada crawler poucas vezes. O Data Catalog tem uma camada gratuita mensal de 1 milhão de objetos armazenados e 1 milhão de requisições. A prática opcional do step 13 tem custo próprio e maior.
