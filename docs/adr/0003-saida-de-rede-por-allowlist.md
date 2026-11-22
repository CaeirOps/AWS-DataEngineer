# ADR-0003: Saída de rede restrita por allowlist

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.1.0)

## Contexto
O container recebe credenciais AWS. Se uma dependência ou um código malicioso rodasse nele, poderia enviar essas credenciais para fora.

## Decisão
O container da aplicação não tem rota para a internet. Toda saída passa por um gateway Squid que só permite domínios da AWS, definidos em `gateway/allowlist.txt`. O log do gateway registra horário e destino, sem cabeçalhos de autenticação. O container roda sem root, com sistema de arquivos somente leitura e sem capabilities extras.

## Alternativas rejeitadas
- Saída livre: não limita uma exfiltração.
- Allowlist por endereço IP: os endereços da AWS mudam e a lista ficaria desatualizada.

## Consequências
- A allowlist não impede o envio de dados para um recurso AWS de outra conta, porque esse destino também está em domínios da AWS. A mitigação é conta dedicada, privilégio mínimo e sessão curta, como recomenda o README.
- Mudanças em `gateway/` exigem revisão do mantenedor.
