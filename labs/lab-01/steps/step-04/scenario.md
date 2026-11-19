# Organizar as camadas e as partições

Os arquivos da AnyCompany estão todos em `entrada/`, no bucket `raw`. Organize a camada raw assim:

```
pedidos/dt=2026-03-08/pedidos-2026-03-08.csv
pedidos/dt=2026-03-09/pedidos-2026-03-09.csv
pedidos/dt=2026-03-10/pedidos-2026-03-10.csv
clientes/cliente-0041.json
clientes/cliente-0042.json
clientes/cliente-0043.json
```

No fim, o prefixo `entrada/` precisa ficar vazio.

**Critério de validação:** cada data tem um CSV em `pedidos/dt=<data>/`, os três cadastros estão em `clientes/` e não sobrou nenhum objeto em `entrada/`.
