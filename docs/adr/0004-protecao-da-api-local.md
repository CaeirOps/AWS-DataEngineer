# ADR-0004: Proteção da API local

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.1.0)

## Contexto
A API local executa ações com as credenciais da pessoa. Uma página maliciosa aberta no mesmo browser poderia tentar chamá-la (CSRF) ou usar DNS rebinding para alcançar `127.0.0.1`.

## Decisão
- Toda requisição precisa de um `Host` da allowlist local.
- Requisições que alteram estado exigem `Origin` local, `Content-Type: application/json` e o cabeçalho próprio `X-Workshop-Request`.
- As respostas usam uma Content Security Policy restrita, `nosniff`, `Referrer-Policy: no-referrer` e isolamento de origem. As imagens do conteúdo recebem uma CSP com `sandbox` (ADR-0010).
- Mensagens de erro não repetem valores recebidos, e valores de credencial são mascarados nas respostas.

## Alternativas rejeitadas
- Token de sessão no browser: aumentaria a superfície (armazenamento no browser) sem ganho real para um serviço só local.
- CORS liberado: abriria a API para qualquer site.

## Consequências
- Clientes que não sejam a própria interface precisam enviar os cabeçalhos exigidos.
- Mudanças em `app/server.py`, `app/session.py` e `app/http_security.py` exigem revisão do mantenedor.
