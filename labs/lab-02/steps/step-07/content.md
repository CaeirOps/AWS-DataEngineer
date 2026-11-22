# Partições no catálogo

No Módulo 00, você viu que particionar os dados no S3 faz a consulta ler só as pastas necessárias. Para isso funcionar, o **catálogo** precisa conhecer cada partição. Uma pasta `dt=2026-03-11/` que existe no S3, mas não está no catálogo, é invisível para o Athena.

## Como uma partição entra no catálogo

| Jeito | Quando usar | Observação |
|---|---|---|
| **Crawler** | Descoberta inicial e fontes variadas | Cobra por DPU-hora e leva alguns minutos |
| **Crawler incremental** (*crawl new sub-folders only*) | Pastas novas chegando com esquema estável | Na primeira vez faz uma varredura completa, depois só adiciona as partições novas. Exige a política de mudança de esquema em `LOG` para atualização e exclusão |
| **`ALTER TABLE ... ADD PARTITION`** (Athena) | Poucas partições, conhecidas | Você informa o valor e a localização |
| **`MSCK REPAIR TABLE`** (Athena) | Pastas no formato `chave=valor` | Procura as pastas e adiciona as partições que faltam. Em tabelas muito grandes, é lento |
| **API `BatchCreatePartition`** (Glue) | Um job ou uma função Lambda registra a partição ao gravar | Sem custo de crawler e sem espera |
| **Partition projection** (Athena) | Partições previsíveis, como datas | O Athena **calcula** as partições a partir de propriedades da tabela e não consulta o catálogo |

![Formas de manter as partições do catálogo sincronizadas](assets/particoes-sincronizar.svg)

## Partition projection

Com milhares de partições, a consulta ao catálogo vira o gargalo. Na partition projection, você descreve na tabela como as partições são formadas (por exemplo, `dt` é uma data entre `2026-01-01` e `NOW`, no formato `yyyy-MM-dd`), e o Athena calcula as localizações em memória:

```
projection.enabled          = true
projection.dt.type          = date
projection.dt.range         = 2026-01-01,NOW
projection.dt.format        = yyyy-MM-dd
storage.location.template   = s3://bucket/pedidos/dt=${dt}
```

- Não é preciso cadastrar partições nem rodar crawler: uma pasta nova já é consultável.
- Só vale para o **Athena**. Outros motores, como o Glue ETL e o Redshift Spectrum, continuam dependendo das partições registradas no catálogo.

> [!EXAM] Muitas partições e consultas lentas no Athena por causa do tempo de leitura do catálogo apontam para **partition projection**. Poucas partições novas por dia, a serem registradas sem custo de crawler, apontam para `BatchCreatePartition` ou `ALTER TABLE ADD PARTITION`.

## Índices de partição

Quando uma tabela tem muitas partições, o Glue pode manter **índices de partição** para localizar rapidamente as partições que um filtro pede, sem listá-las todas. Os crawlers criam esses índices por padrão para alvos S3.

> [!WARNING] Não repita dentro do arquivo a coluna que já é chave de partição. Um CSV de pedidos com a coluna `dt` em uma pasta `dt=2026-03-10/` gera, no catálogo, uma coluna `dt` e uma partição `dt` com o mesmo nome, e o Athena recusa a tabela com um erro de metadados. A data fica só no nome da pasta.

> [!TIP] Registre a partição no momento em que o dado chega. Um job que grava `dt=2026-03-11/` pode chamar `BatchCreatePartition` em seguida, e a consulta já enxerga a pasta.

> [!WARNING] O crawler incremental não detecta alteração nem exclusão de partições que já existem, e não serve quando o esquema muda. Para uma mudança de esquema, faça uma varredura completa uma vez e volte ao modo incremental.
