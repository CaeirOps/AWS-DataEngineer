# Estruturas de dados e algoritmos

O exame não pede para implementar algoritmos, mas espera que você reconheça as estruturas por trás dos serviços.

## Árvores

Uma árvore organiza os dados em níveis, de uma raiz até as folhas. Em uma árvore de busca balanceada, encontrar um valor custa um número de passos proporcional à altura da árvore, não ao total de registros.

- A **B-tree** e suas variantes são a estrutura padrão dos índices de bancos relacionais, como PostgreSQL e MySQL. Com um índice em `id_cliente`, o banco desce alguns níveis da árvore até achar as linhas do cliente, em vez de ler a tabela inteira.
- Árvores também aparecem em dados hierárquicos, como a hierarquia de categorias de produtos da AnyCompany (Moda > Masculino > Camisetas).

## Grafos

Um grafo é um conjunto de nós ligados por arestas.

- **DAG de pipeline:** em um orquestrador como o Apache Airflow (Amazon MWAA), cada tarefa é um nó e cada dependência é uma aresta. O grafo é acíclico: nenhuma tarefa depende, direta ou indiretamente, dela mesma (Módulo 12).
- **DAG de execução:** o Spark monta o plano de um job como um DAG de estágios, como você viu no step anterior.
- **Linhagem de dados (*lineage*):** um grafo que mostra de quais tabelas cada tabela foi derivada (Módulo 15).
- **Banco de grafos:** o Amazon Neptune guarda relacionamentos como nós e arestas. Exemplo: "clientes que compraram este produto também compraram..." é uma consulta natural em grafo.

## Tabelas hash

Uma função hash transforma uma chave em um número. Esse número decide onde o registro fica.

- O Amazon DynamoDB usa o hash da chave de partição para escolher em qual partição física guardar o item (Módulo 08).
- O Amazon Redshift, com distribuição por chave, usa o hash da coluna para escolher o nó de cada linha (Módulo 10).
- O shuffle do Spark usa o hash da chave do `groupBy` para escolher o executor de cada registro.

> [!TIP] Distribuir por hash funciona bem quando a chave tem muitos valores distintos e acessos equilibrados. Uma chave com poucos valores, ou com um valor muito mais acessado que os outros, concentra a carga em uma partição (*hot partition*).

## Filas e logs

- Uma **fila**, como o Amazon SQS, entrega cada mensagem a um consumidor, que a remove depois de processar.
- Um **log** ordenado e com retenção, como o Kinesis Data Streams e o Kafka, guarda os registros em ordem e permite que vários consumidores leiam e releiam o mesmo dado. É isso que viabiliza a replayability.

> [!EXAM] Se vários sistemas precisam ler o mesmo fluxo de eventos, ou se é preciso reprocessar, a estrutura certa é um log com retenção (Kinesis Data Streams ou Amazon MSK), não uma fila.
