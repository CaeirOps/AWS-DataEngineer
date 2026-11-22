# ADR-0006: GitFlow simplificado com merge por rebase

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.1.0)

## Contexto
O projeto precisa de uma `main` sempre estável, versões numeradas e um histórico em que cada commit mantenha o próprio sign-off do DCO.

## Decisão
- A `main` é a única branch permanente. Cada versão é integrada em `release/vX.Y.Z`, e o trabalho chega a ela por Pull Request de branches `feat/`, `fix/`, `docs/`, `chore/` ou `lab/NN-`.
- Correções urgentes da `main` usam `hotfix/vX.Y.Z` e são levadas também para a release ativa.
- O único método de integração é *rebase and merge*.
- A release nasce no mesmo commit da `main`, sem commits próprios, e as mudanças chegam a ela por Pull Request.
- Commits seguem Conventional Commits em português.

## Alternativas rejeitadas
- Squash: cria um commit novo com o e-mail padrão do GitHub do autor, que pode divergir do sign-off e quebrar o DCO.
- Commits de merge: quebram o histórico linear.

## Consequências
- Quem contribui atualiza a branch com rebase e `git push --force-with-lease`.
- O passo a passo está no README, na seção "Fluxo de trabalho (gitflow)".
