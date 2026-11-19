# Resumo e próximos passos

## O que você fez

- Organizou a camada raw em partições `dt=` e separou os clientes, deixando o data lake pronto para os motores de consulta.
- Ativou o versionamento e viu como sobrescritas e exclusões criam versões e delete markers.
- Criou uma regra de Lifecycle que muda a classe dos pedidos com a idade, expira os antigos e apaga as versões esquecidas.
- Ligou o S3 à Lambda com uma notificação filtrada e gerou resumos de forma automática e idempotente.
- Atendeu um pedido de exclusão apagando todas as versões dos dados do cliente.
- Deu ao time de análise acesso só de leitura, por um Access Point com política própria.

## Pontos para a prova

- Classe de armazenamento se escolhe pelo padrão de acesso, pela duração mínima e pelo custo de leitura.
- Versionamento protege contra erro, Object Lock protege contra qualquer exclusão, e replicação protege contra a perda de uma Region.
- Lifecycle é a forma sem código de mudar de classe e de expirar dados.
- Eventos do S3 são entregues pelo menos uma vez e sem ordem: o processamento precisa ser idempotente.
- Excluir em um bucket versionado exige apagar as versões, não só criar um delete marker.
- Access Points e endpoints da VPC limitam quem acessa e por onde.

## Documentação oficial

- [Classes de armazenamento do Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)
- [Versionamento no S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [Gerenciar o ciclo de vida dos objetos](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [S3 Event Notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html)
- [Usar o AWS Lambda com o Amazon S3](https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html)
- [Apagar objetos de um bucket versionado](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjectVersions.html)
- [S3 Access Points](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points.html)
- [Replicação de objetos](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)
- [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [Gateway endpoints para o S3](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)

## Próximo módulo

No **Módulo 02, Catálogo de dados**, você usa o AWS Glue Data Catalog e um crawler para descobrir o esquema e as partições dos dados que organizou aqui.
