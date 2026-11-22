# ADR-0012: Prática opcional de crawler JDBC retirada do Módulo 02

- **Status:** Aceito
- **Data:** 2026-11-22

## Contexto
A proposta do Módulo 02 previa uma prática opcional: catalogar um banco relacional com um crawler JDBC do AWS Glue. No teste na conta, com Amazon Aurora PostgreSQL Serverless v2, secret gerenciado pelo RDS e conexão do Glue na VPC:
- o crawler exigiu primeiro um gateway endpoint do S3 na subnet, o que foi corrigido;
- depois falhou com `Test connection failed`, e com driver JDBC próprio falhou com `JDBC connection not found`.

A rede foi conferida pela configuração (security group com regra de autorreferência, NACLs, DNS e mesma VPC), mas a chegada do tráfego à porta do banco não foi provada (sem Reachability Analyzer nem Flow Logs). Uma hipótese não confirmada é que o driver nativo do crawler não suporta a autenticação `scram-sha-256`, padrão do PostgreSQL a partir da versão 14.

## Decisão
Retirar a prática opcional do Módulo 02. As skills 2.2.5 e 1.2.2 seguem cobertas pela teoria e pela Verificação de conhecimento, e voltam com prática no Módulo 09.

## Alternativas rejeitadas
- Publicar a prática sem ela funcionar: contraria o ADR-0011.
- Continuar tentando sem causa confirmada: o banco cobra por hora.

## Consequências
- Um novo teste, com diagnóstico de rede e as hipóteses de autenticação e driver, está registrado como issue. Se funcionar, a prática volta com um ADR que substitui este.
