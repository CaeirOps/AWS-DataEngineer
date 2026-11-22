# ADR-0005: Licenças e DCO

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.1.0)

## Contexto
O projeto tem código e conteúdo didático, que têm necessidades diferentes de reuso.

## Decisão
- Código: Apache License 2.0 (`LICENSE`).
- Conteúdo didático: CC BY-SA 4.0 (`LICENSE-CONTENT`).
- Todo commit precisa da assinatura do DCO (`git commit -s`), conferida no CI.

## Alternativas rejeitadas
- Uma única licença para tudo: licenças de software não tratam bem textos e imagens, e licenças de conteúdo não tratam patentes de código.
- CLA: mais burocrático para contribuidores ocasionais do que o DCO.

## Consequências
- Quem adapta o conteúdo precisa dar crédito e manter a mesma licença.
- Commits sem sign-off são recusados pelo CI.
