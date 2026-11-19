# S3 Lifecycle

Uma regra de **Lifecycle** diz ao S3 o que fazer com os objetos conforme eles envelhecem, sem nenhum código. Ela tem dois tipos de ação:

- **Transição:** muda a classe de armazenamento depois de um número de dias.
- **Expiração:** apaga o objeto depois de um número de dias.

![Linha do tempo da regra de Lifecycle de pedidos](assets/lifecycle-pedidos.svg)

## A regra da AnyCompany

Os pedidos são muito consultados no primeiro mês, de vez em quando até o terceiro e quase nunca depois. A política de retenção da empresa é de um ano.

| Idade do objeto | Ação | Por quê |
|---|---|---|
| 0 a 30 dias | S3 Standard | Acesso frequente |
| 30 dias | Transição para Standard-IA | Acesso pouco frequente, leitura imediata |
| 90 dias | Transição para Glacier Instant Retrieval | Acesso raro, ainda em milissegundos |
| 365 dias | Expiração da versão atual | Fim da retenção |
| 30 dias depois de virar versão antiga | Exclusão definitiva da versão antiga | Não pagar por versões esquecidas |

## Regras importantes

- **Filtro:** a regra vale para um prefixo (`pedidos/`), para tags ou para uma faixa de tamanho. Sem filtro, vale para o bucket inteiro.
- **Dias mínimos:** a transição para Standard-IA ou One Zone-IA só pode acontecer depois de 30 dias no S3 Standard.
- **Tamanho mínimo:** por padrão, as regras de Lifecycle não fazem transição de objetos menores que 128 KB, porque a taxa por objeto da transição seria maior que a economia. Os arquivos de exemplo deste módulo são menores que isso.
- **Execução assíncrona:** as ações do Lifecycle entram numa fila e podem acontecer algum tempo depois da data prevista. A cobrança da classe nova e o fim da cobrança de um objeto expirado já seguem a data da regra.
- **Bucket versionado:** a expiração da versão atual cria um delete marker, e a versão com os dados vira *noncurrent*. Para apagar de fato, a regra precisa também expirar as versões antigas (`NoncurrentVersionExpiration`). Existe ainda a ação de apagar delete markers que ficaram sozinhos (*expired object delete markers*).

> [!TIP] Quando o padrão de acesso não é conhecido, o S3 Intelligent-Tiering pode ser melhor que uma regra fixa: ele move cada objeto pela camada de acesso conforme o uso real.

> [!EXAM] "Apagar automaticamente os logs depois de 90 dias" pede uma regra de expiração do Lifecycle, não uma Lambda agendada. A solução com menos esforço operacional é a que o próprio serviço faz.

> [!COST] Cada transição cobra uma taxa por requisição. Transicionar milhões de objetos pequenos pode custar mais que guardá-los no Standard.
