# Controle de acesso e S3 Access Points

## Quem decide o acesso a um objeto

| Mecanismo | Onde fica | Exemplo |
|---|---|---|
| **Política de identidade do IAM** | Na role ou no usuário | "Esta role pode ler `s3://raw/pedidos/*`" |
| **Bucket policy** | No bucket | "Ninguém acessa sem TLS" |
| **Política de Access Point** | No Access Point | "A role analista lê só `resumos/*` por este Access Point" |
| **Block Public Access** | Na conta e no bucket | Bloqueia qualquer política ou ACL pública |
| **ACLs** | Nos objetos | Desligadas com *Bucket owner enforced*, como recomenda a AWS |

Um `Deny` explícito em qualquer política sempre vence. Na mesma conta, basta um `Allow` na política de identidade ou na política do recurso. Entre contas diferentes, os dois lados precisam permitir.

## S3 Access Points

Um bucket compartilhado por muitos times acaba com uma bucket policy enorme e difícil de revisar. Um **Access Point** é uma porta de acesso ao bucket com nome e política próprios. Cada time ou aplicação recebe o seu.

- Cada Access Point tem um ARN (`arn:aws:s3:<region>:<conta>:accesspoint/<nome>`) e um alias, que pode ser usado no lugar do nome do bucket.
- A política do Access Point limita o acesso a prefixos, ações e principais.
- A **origem de rede** pode ser a internet ou só uma VPC. No modo VPC, o Access Point não aceita requisições de fora daquela VPC.
- A bucket policy precisa **delegar** o acesso aos Access Points. A stack fez isso no bucket `curated`, com a condição `s3:DataAccessPointAccount`, e só para leitura.

> [!EXAM] Muitos times com permissões diferentes no mesmo bucket pedem S3 Access Points. "Acessar o S3 apenas de dentro da VPC" pede Access Point com origem VPC ou uma condição `aws:SourceVpce` na bucket policy.

## Acesso privado: gateway endpoint e PrivateLink

Por padrão, uma instância em uma subnet privada precisa de um NAT gateway para chegar ao S3. Há dois jeitos de evitar a saída para a internet:

| | Gateway endpoint | Interface endpoint (AWS PrivateLink) |
|---|---|---|
| Serviços | S3 e DynamoDB | Muitos serviços, inclusive o S3 |
| Como funciona | Rota na route table da subnet | Interface de rede com IP privado na subnet |
| Acesso a partir da rede local (VPN ou Direct Connect) | Não | Sim |
| Custo | Sem cobrança | Cobrança por hora e por GB |

Os dois aceitam uma **endpoint policy**, que limita quais buckets podem ser acessados por eles. Combinada com `aws:SourceVpce` na bucket policy, ela garante que os dados só saem pelo caminho previsto. A rede e a segurança voltam no Módulo 14.

> [!COST] Para tráfego do S3 dentro da mesma Region, o gateway endpoint é gratuito e evita a cobrança por GB do NAT gateway.

> [!TIP] Sempre que possível, dê acesso a roles, não a usuários, e limite cada permissão ao prefixo e às ações necessárias.
