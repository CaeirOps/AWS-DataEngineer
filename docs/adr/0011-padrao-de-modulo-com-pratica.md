# ADR-0011: Padrão de módulo com prática

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisões dos Módulos 01 e 02)

## Contexto
Os testes simulados não pegaram problemas que só aparecem na conta: uma fábrica de sessão que falhava no container, permissões do IAM, atrasos de propagação e diferenças entre a documentação e a API. Recursos criados pela pessoa fora da stack também impediam o teardown.

## Decisão
- **Stack CloudFormation** com os padrões seguros: Block Public Access, criptografia, ACLs desligadas, negação de acesso sem TLS e roles com privilégio mínimo. O template passa no `cfn-lint` e no `cfn-guard` do CI.
- **Função de preparação** (custom resource) que grava os dados fictícios na criação e, no delete, remove o que a pessoa criou fora da stack: objetos e versões, Access Points, crawlers, tabelas e logs dos próprios recursos. Recursos compartilhados da conta não são apagados.
- **Validadores só de leitura** em `app/validators/labNN.py`, com testes que usam boto3 simulado.
- **Teste na conta antes da revisão**: deploy, cada prática pela trilha CLI com falha antes e acerto depois, erros de propósito, teardown e conferência de que nada sobrou. Recursos fora da stack entram em `residual_resources` e nas instruções de limpeza.
- Um passo que não funcionou no teste não é publicado.

## Alternativas rejeitadas
- Publicar só com testes simulados: deixaria passar falhas reais.
- Deixar a limpeza manual para a pessoa: o teardown falharia e geraria custo.

## Consequências
- O teste na conta gera custo para quem desenvolve o módulo e exige autorização explícita do mantenedor.
- A trilha Console ainda não tem teste automatizado. Isso está registrado como pendência.
