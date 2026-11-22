# ADR-0010: Destaques e imagens locais no conteúdo

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.2.0)

## Contexto
O conteúdo precisa destacar o que cai na prova e mostrar diagramas, mas o Markdown vem de contribuições e não pode virar um vetor de script ou de rastreamento.

## Decisão
- Destaques com a sintaxe `> [!EXAM]`, `> [!COST]`, `> [!TIP]` e `> [!WARNING]`. O texto é sempre escapado.
- Imagens só de `assets/<nome>.svg|png` do próprio módulo, com texto alternativo obrigatório. Imagens externas, `data:` e caminhos com `..` aparecem só como texto.
- A rota de imagens valida o nome, monta o caminho a partir da listagem de `assets/`, recusa links simbólicos e responde com `nosniff` e CSP `sandbox`.

## Alternativas rejeitadas
- HTML livre no Markdown: abriria espaço para script.
- Imagens externas: permitiriam rastrear quem estuda e mudar o conteúdo sem revisão.

## Consequências
- SVGs não podem ter script nem referências externas. A revisão do módulo confere isso.
