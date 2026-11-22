# ADR-0007: 19 módulos com teoria e prática

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.2.0)

## Contexto
A primeira proposta, com 10 labs, deixava lacunas em relação ao guia oficial do exame DEA-C01, e as pessoas pediram um treinamento completo, com teoria e prática ao mesmo tempo.

## Decisão
- O workshop tem 19 módulos (`lab-00` a `lab-18`) e um Simulado final. A Matriz de cobertura (`docs/exam-coverage.json`) relaciona as 120 skills do guia oficial aos módulos, com o texto das skills em inglês, igual ao guia.
- Cada módulo segue a sequência: objetivos com as skills, conceitos intercalados com práticas, Verificação de conhecimento e resumo com links oficiais.
- Toda prática tem trilha Console e trilha CLI.
- O cenário de todos os módulos é a **AnyCompany**, empresa fictícia de varejo, sempre com dados fictícios.
- Documentação em português, preservando os termos técnicos em inglês.
- Os identificadores técnicos `lab_id`, `labs/` e `/api/labs` foram mantidos, para não quebrar a API, os testes e o progresso salvo.

## Alternativas rejeitadas
- Renomear tudo para "módulo" no código: quebraria a compatibilidade sem ganho para quem estuda.

## Consequências
- Cada módulo passa por proposta e por revisão do mantenedor (ADR-0011).
- O catálogo recusa um módulo cujas skills não existam na Matriz.
