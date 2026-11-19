# Versionamento, proteção e resiliência

## Versionamento

Com o versionamento ativado, o S3 guarda todas as versões de cada objeto. Cada gravação na mesma chave cria uma versão nova com um `VersionId` próprio, e a anterior continua guardada.

![Versões e delete markers de um objeto](assets/versoes-delete-markers.svg)

- **Sobrescrita:** a versão antiga vira *noncurrent* e pode ser restaurada.
- **Exclusão sem informar a versão:** o S3 não apaga nada. Ele cria um **delete marker**, que vira a versão atual. O objeto some da listagem, mas as versões com os dados continuam no bucket.
- **Exclusão definitiva:** só acontece quando você informa o `VersionId`.
- Depois de ativado, o versionamento nunca volta a ficar desligado. Ele só pode ser **suspenso**, e as versões que já existem continuam guardadas.

> [!COST] Cada versão é cobrada como um objeto inteiro. Um arquivo de 1 GB sobrescrito 10 vezes ocupa 11 GB. Use uma regra de Lifecycle para apagar as versões antigas, como você vai fazer no step 08.

## Outras proteções

- **MFA Delete:** exige um código MFA para apagar versões ou mudar o estado do versionamento. Só o usuário root configura, pela CLI.
- **S3 Object Lock:** impede apagar ou sobrescrever uma versão até uma data (*retention*) ou enquanto houver um *legal hold*. No modo *governance*, quem tem uma permissão especial pode remover a trava. No modo *compliance*, ninguém pode, nem o usuário root. É o recurso usado para gravar uma vez e ler muitas (WORM), em regras de auditoria.
- **AWS Backup:** faz cópias agendadas dos buckets, com retenção e cópia para outra conta ou Region.

## Resiliência e disponibilidade

| Risco | Proteção |
|---|---|
| Falha de uma zona de disponibilidade | Classes que usam várias zonas, como Standard, Standard-IA e Glacier |
| Exclusão ou sobrescrita acidental | Versionamento e Object Lock |
| Falha de uma Region inteira ou exigência de cópia distante | Replicação entre Regions (CRR) |
| Cópia na mesma Region para outra conta ou para isolar ambientes | Replicação na mesma Region (SRR) |

A replicação exige o versionamento ativado na origem e no destino. Ela copia só os objetos gravados depois de a regra existir. Para copiar os que já estavam no bucket, use o S3 Batch Replication. Com o *S3 Replication Time Control*, a maioria dos objetos é replicada em segundos e 99,9% em até 15 minutos, com SLA.

> [!EXAM] "Proteger contra exclusão acidental" pede versionamento. "Impedir qualquer exclusão por 7 anos, inclusive pelo administrador" pede Object Lock em modo compliance. "Manter uma cópia em outra Region para recuperação de desastre" pede CRR, com versionamento nos dois buckets.
