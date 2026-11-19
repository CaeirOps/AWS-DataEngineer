# Processar cada arquivo novo

O time quer um resumo de cada arquivo de pedidos assim que ele chegar ao data lake. A função `workshop-lab-01-indexador` já existe. Ligue o bucket `raw` a ela:

- **Eventos:** criação de objetos (*All object create events*).
- **Filtro:** prefixo `pedidos/` e sufixo `.csv`.
- **Destino:** a função Lambda `workshop-lab-01-indexador`.

Depois, copie `pedidos/dt=2026-03-10/pedidos-2026-03-10.csv` para `pedidos/dt=2026-03-11/pedidos-2026-03-11.csv` e confira o resumo gerado em `curated/resumos/`.

**Critério de validação:** a notificação existe com esses eventos e filtros, e há pelo menos um resumo em `resumos/pedidos/` no bucket `curated`.
