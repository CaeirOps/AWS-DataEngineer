# Resumo e próximos passos

## O que você fez

- Criou um crawler que descobriu o esquema e as partições dos pedidos e o transformou em uma tabela do Data Catalog.
- Catalogou pedidos, clientes e fornecedores com um único crawler agendado, com prefixo de tabela.
- Registrou uma partição nova no catálogo sem varrer tudo de novo.
- Tratou a coluna nova de um fornecedor ajustando a política de mudança de esquema do crawler.
- Viu como uma conexão do Glue e um crawler JDBC levam o catálogo a um banco relacional.

## Pontos para a prova

- O **Glue Data Catalog** guarda metadados, não dados, e serve ao Athena, ao Glue, ao EMR e ao Redshift Spectrum. É compatível com o Hive metastore.
- O **crawler** descobre o esquema e as partições. Cobra por DPU-hora, com mínimo de 10 minutos por execução.
- Para registrar partições: crawler (incremental), `MSCK REPAIR TABLE`, `ALTER TABLE ADD PARTITION`, `BatchCreatePartition` ou **partition projection** (só Athena).
- **Agendas** do crawler, do EventBridge ou do Airflow para tempo. **Eventos** do S3 para chegada imprevisível.
- Na **evolução de esquema**, o CSV lê por posição: acrescente colunas só no fim. A política de mudança define `UpdateBehavior` e `DeleteBehavior`.
- **Conexões** do Glue guardam rede e credenciais (Secrets Manager). Falhas de conexão costumam ser de security group ou de rota.

## Documentação oficial

- [AWS Glue Data Catalog](https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html)
- [Usar crawlers para popular o Data Catalog](https://docs.aws.amazon.com/glue/latest/dg/add-crawler.html)
- [Personalizar o comportamento do crawler](https://docs.aws.amazon.com/glue/latest/dg/crawler-configuration.html)
- [Crawls incrementais para novas partições](https://docs.aws.amazon.com/glue/latest/dg/incremental-crawls.html)
- [Agendar um crawler](https://docs.aws.amazon.com/glue/latest/dg/schedule-crawler.html)
- [Partition projection no Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/partition-projection.html)
- [Conexões do AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/glue-connections.html)
- [Preços do AWS Glue](https://aws.amazon.com/glue/pricing/)

## Próximo módulo

No **Módulo 03, Athena e SQL analítico**, você consulta as tabelas do catálogo com SQL, usa partition pruning, cria tabelas com `CTAS` e vê como o custo muda com o formato dos dados.
