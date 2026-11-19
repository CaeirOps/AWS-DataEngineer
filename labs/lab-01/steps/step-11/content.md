# Exclusão de dados

Leis de proteção de dados, como a LGPD no Brasil e o GDPR na Europa, dão ao titular o direito de pedir a exclusão dos seus dados pessoais. Regras de negócio também exigem apagar dados depois de um prazo. O engenheiro de dados precisa saber apagar de verdade, sem deixar cópias esquecidas.

## Apagar em um bucket versionado

| Ação | Resultado |
|---|---|
| `DELETE` sem `VersionId` | Cria um delete marker. Os dados continuam nas versões antigas. |
| `DELETE` com o `VersionId` de cada versão | Apaga cada versão de forma definitiva |
| `DELETE` do delete marker (pelo `VersionId` dele) | Remove o marcador. Se sobrou versão antiga, ela volta a ser a atual. |

Para atender um pedido de exclusão em um bucket versionado, apague **todas as versões** do objeto e o delete marker, se houver.

> [!WARNING] Um objeto que sumiu da listagem não foi necessariamente apagado. No console, ligue **Show versions** para ver as versões e os delete markers.

## Onde mais o dado pode estar

- Em **outros prefixos ou camadas**: a mesma informação pode estar na raw e na curated.
- Em **réplicas**: a replicação não repete a exclusão de versões específicas no destino. Apague também lá.
- Em **backups**: as cópias do AWS Backup seguem a própria retenção.
- Em **tabelas derivadas**: arquivos Parquet que juntam vários clientes precisam ser reescritos sem as linhas do titular. Os formatos de tabela abertos, como Apache Iceberg, facilitam isso com `DELETE` em SQL (Módulo 11).

## Apagar em escala

- **Regra de Lifecycle:** para apagar por idade, como "pedidos com mais de 1 ano".
- **S3 Batch Operations:** para apagar, copiar ou marcar milhões de objetos a partir de uma lista (*manifest*), com relatório do resultado.
- **Desenho da chave:** guardar os dados de cada cliente sob um prefixo próprio facilita encontrá-los e apagá-los.

> [!EXAM] Se a regra exige que nenhum dado seja apagado por um período, Object Lock em modo compliance é a resposta. Se a regra exige apagar sob demanda, o Object Lock em modo compliance atrapalha: nem o administrador consegue apagar antes do fim da retenção. Leia o enunciado para saber qual exigência vale.

> [!TIP] Registre cada pedido de exclusão (quem pediu, quando, o que foi apagado) sem guardar os dados apagados. O AWS CloudTrail pode registrar as chamadas de exclusão como evidência (Módulo 13).
