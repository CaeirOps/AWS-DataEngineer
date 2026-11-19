# Resumo e próximos passos

## O que você viu

- **Os 3 Vs** (volume, velocidade e variedade) descrevem os dados e guiam a escolha da arquitetura. Os dados podem ser estruturados, semiestruturados ou não estruturados.
- **Batch e streaming** se escolhem pela latência aceita pelo negócio. Transformações stateless tratam cada registro sozinho. As stateful, como janelas, deduplicação e junções, dependem de estado guardado.
- **Replayability** exige uma fonte com retenção, processamento idempotente e saída que permite substituir um período.
- **Formatos colunares** (Parquet e ORC), **compressão** e **particionamento** reduzem o volume lido, o tempo e o custo das consultas.
- **Computação distribuída** divide o dado em partições processadas em paralelo. O shuffle é a etapa mais cara.
- **Árvores, grafos e hash** estão por trás de índices, DAGs de pipelines, linhagem e da distribuição de dados entre partições.
- **SQL, Python, PySpark, Scala e Bash** têm usos diferentes. Comece pelo mais simples que resolve.
- **Serviços gerenciados** transferem para a AWS parte das tarefas de operação e segurança, mas acesso, criptografia e dados continuam sendo sua responsabilidade.

## Documentação oficial

- [Guia do exame AWS Certified Data Engineer - Associate](https://docs.aws.amazon.com/aws-certification/latest/data-engineer-associate-01/data-engineer-associate-01.html)
- [Modelo de responsabilidade compartilhada](https://aws.amazon.com/compliance/shared-responsibility-model/)
- [Formatos colunares no Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/columnar-storage.html)
- [Particionamento de dados no Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/partitions.html)
- [Compressão no Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/compression-formats.html)
- [Retenção de dados no Amazon Kinesis Data Streams](https://docs.aws.amazon.com/streams/latest/dev/kinesis-extended-retention.html)
- [O que é o Amazon MSK](https://docs.aws.amazon.com/msk/latest/developerguide/what-is-msk.html)
- [O que é o Amazon EMR Serverless](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/emr-serverless.html)
- [Partições e distribuição de dados no Amazon DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.Partitions.html)

## Próximo módulo

No **Módulo 01, S3 e data lake**, você cria o data lake da AnyCompany no Amazon S3, organiza as camadas *raw* e *curated* e aplica o particionamento que viu aqui.
