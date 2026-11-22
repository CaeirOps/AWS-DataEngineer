# ADR-0001: Plataforma local em containers

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão tomada na v0.1.0)

## Contexto
O workshop é open source e *self-paced*, no estilo dos workshops oficiais da AWS: a pessoa recebe um cenário pronto, constrói a solução na própria conta e uma validação automática confere o resultado. O projeto não tem orçamento para hospedar um serviço, e um serviço central teria de guardar credenciais de terceiros.

## Decisão
A plataforma roda na máquina de quem estuda, com Docker Compose: uma aplicação Flask (API e interface web) e um gateway de saída. A interface fica publicada só em `127.0.0.1`. Não há servidor externo, login nem coleta de dados. O `start.py` sobe o ambiente e o `check_requirements.py` confere os pré-requisitos.

## Alternativas rejeitadas
- Serviço hospedado: exigiria guardar credenciais AWS de terceiros e ter custo fixo.
- Scripts soltos sem interface: sem validação automática, progresso nem trilhas Console e CLI.

## Consequências
- Cada pessoa precisa de Docker e do AWS CLI.
- Os dados de progresso ficam só no computador da pessoa (`progress/`).
- A segurança do ambiente local passa a ser parte do projeto (ADRs 0002 a 0004).
