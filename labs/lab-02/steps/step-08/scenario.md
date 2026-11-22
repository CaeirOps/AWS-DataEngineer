# Sincronizar uma partição nova

Chegou o arquivo de pedidos de 11/03/2026. Simule a chegada copiando `pedidos/dt=2026-03-10/pedidos-2026-03-10.csv` para `pedidos/dt=2026-03-11/pedidos-2026-03-11.csv` e registre a partição `dt=2026-03-11` na tabela `pedidos`.

- Na **trilha CLI**, registre a partição com a API do Glue (`batch-create-partition`), sem rodar crawler.
- Na **trilha Console**, execute de novo o crawler `workshop-lab-02-pedidos`.

**Critério de validação:** a partição `dt=2026-03-11` existe na tabela `pedidos` e aponta para `s3://workshop-lab-02-dados-<conta>-<region>/pedidos/dt=2026-03-11/`.

> [!COST] O caminho da CLI não tem custo de crawler. O caminho do console executa o crawler outra vez, com o mínimo de 10 minutos de DPU. Em produção, registrar a partição pela API, no momento em que o arquivo chega, é mais barato e mais rápido.
