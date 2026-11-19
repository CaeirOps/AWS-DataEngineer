# Objetivos e cenário da AnyCompany

Este módulo apresenta os conceitos que aparecem em todo o exame AWS Certified Data Engineer - Associate (DEA-C01). Ele é só teoria: não cria recursos na sua conta AWS e não gera custo.

## O que você vai aprender

| Skill do exame | Tema |
|---|---|
| 1.2.9 | Volume, velocidade e variedade, e os tipos de dados |
| 1.1.11 | *Replayability* de pipelines de ingestão |
| 1.1.12 | Transações *stateful* e *stateless* |
| 1.2.6 | Conversão entre formatos, como de CSV para Apache Parquet |
| 2.4.5 | Indexação, particionamento, compressão e outras otimizações |
| 1.4.10 | Computação distribuída |
| 1.4.11 | Estruturas de dados e algoritmos, como grafos e árvores |
| 1.4.3 | Linguagens e frameworks de engenharia de dados |
| 4.1.6 | Diferenças entre serviços gerenciados e não gerenciados |

## O cenário

A **AnyCompany** é uma empresa fictícia de varejo, com lojas físicas e um e-commerce. Ela é o cenário de todos os módulos do workshop. Os dados dela vêm de quatro fontes:

- **Pedidos:** tabelas no banco de dados transacional do e-commerce e dos caixas das lojas.
- **Navegação do site:** eventos JSON gerados a cada clique, busca ou item adicionado ao carrinho (*clickstream*).
- **Estoque:** arquivos CSV que os fornecedores enviam uma vez por dia.
- **Catálogo:** fotos de produtos e manuais em PDF.

O time de dados da AnyCompany precisa juntar tudo isso para responder perguntas como "quanto cada loja vendeu ontem?" e "quais produtos são vistos e não comprados?". Ao longo do workshop, você vai construir esse pipeline na AWS. Neste módulo, você aprende o vocabulário para tomar as decisões certas.

## Como o workshop cobre o exame

O exame tem quatro domínios. Cada módulo cobre um conjunto de skills, e o Simulado final sorteia questões com o mesmo peso da prova.

| Domínio | Peso na prova | Módulos principais |
|---|---|---|
| D1 Data Ingestion and Transformation | 34% | 04, 05, 07, 09, 12 |
| D2 Data Store Management | 26% | 01, 02, 08, 10, 11 |
| D3 Data Operations and Support | 22% | 03, 06, 13 |
| D4 Data Security and Governance | 18% | 14, 15 |

Os módulos 16, 17 e 18 combinam vários domínios.

> [!TIP] Leia cada step com calma e use a Verificação de conhecimento no fim para conferir o que ficou. As tentativas são ilimitadas e as explicações aparecem depois de cada envio.
