# ADR-0008: Aviso de custo sem valores em USD

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.2.0)

## Contexto
As práticas criam recursos reais na conta de quem estuda. Um valor estimado em USD daria uma falsa precisão, porque depende de Region, de uso e de premissas, e a AWS Pricing Calculator pública não tem API para gerar estimativas nem links.

## Decisão
- Antes do deploy, o módulo mostra o **Aviso de custo**, com os serviços cobrados e o link da página oficial de preços de cada um (só endereços `https://aws.amazon.com/`).
- Nenhum valor em USD é exibido.
- A prática padrão usa a opção de menor custo que cumpre o objetivo. Serviços de custo alto ficam em **práticas opcionais**, com aviso reforçado, que não bloqueiam a conclusão do módulo.

## Alternativas rejeitadas
- Calcular a partir de preços unitários: dependeria de premissas de uso inventadas.
- Links da Pricing Calculator criados à mão: não é possível manter para todos os módulos.

## Consequências
- A estimativa em USD fica em "Melhorias futuras" no README: script com o AWS Price List API, premissas versionadas e revisadas.
