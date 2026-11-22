# Registros de decisão (ADR)

Este diretório guarda as decisões de arquitetura e de produto do workshop, no formato ADR (*Architecture Decision Record*). Cada registro explica o contexto, a decisão, as alternativas rejeitadas e as consequências, para que quem chega ao projeto entenda o porquê sem depender de conversas antigas.

## Como usar

- **Antes de propor uma mudança**, procure aqui se o tema já foi decidido.
- **Para mudar uma decisão**, abra um Pull Request com um ADR novo, que cita o anterior em **Substitui**. O ADR antigo continua no repositório, com o status **Substituído por ADR-NNNN**. Não reescreva a história de um ADR aceito.
- **Para uma decisão nova**, copie o modelo abaixo para `NNNN-titulo-curto.md`, com o próximo número livre, e acrescente a linha na tabela.
- ADRs passam por revisão do mantenedor, como os demais arquivos do projeto.
- Não inclua credenciais, IDs de conta, nomes de profile, e-mails nem dados do seu ambiente. Use dados fictícios em exemplos.

## Modelo

```markdown
# ADR-NNNN: Título curto

- **Status:** Proposto | Aceito | Substituído por ADR-NNNN
- **Data:** AAAA-MM-DD
- **Substitui:** ADR-NNNN (se houver)

## Contexto
O problema e as restrições que levaram à decisão.

## Decisão
O que foi decidido, de forma direta.

## Alternativas rejeitadas
- Alternativa: por que não foi escolhida.

## Consequências
O que fica mais fácil, o que fica mais difícil e o que precisa ser acompanhado.
```

## Índice

| ADR | Decisão | Status |
|---|---|---|
| [0001](0001-plataforma-local-em-containers.md) | Plataforma local em containers, acessível só em 127.0.0.1 | Aceito |
| [0002](0002-credenciais-temporarias-por-ambiente.md) | Credenciais temporárias por variável de ambiente, com renovação manual | Aceito |
| [0003](0003-saida-de-rede-por-allowlist.md) | Saída de rede do container restrita por um gateway com allowlist | Aceito |
| [0004](0004-protecao-da-api-local.md) | Proteção da API local contra CSRF e DNS rebinding | Aceito |
| [0005](0005-licencas-e-dco.md) | Apache 2.0 para o código, CC BY-SA 4.0 para o conteúdo e DCO | Aceito |
| [0006](0006-gitflow-com-rebase.md) | GitFlow simplificado com releases e merge só por rebase | Aceito |
| [0007](0007-modulos-com-teoria-e-pratica.md) | 19 módulos com teoria e prática, cenário AnyCompany e dados fictícios | Aceito |
| [0008](0008-aviso-de-custo-sem-usd.md) | Aviso de custo com páginas oficiais de preço, sem valores em USD | Aceito |
| [0009](0009-quiz-e-simulado-corrigidos-no-servidor.md) | Verificação de conhecimento e Simulado corrigidos no servidor | Aceito |
| [0010](0010-conteudo-com-destaques-e-imagens-locais.md) | Destaques e imagens só locais no conteúdo | Aceito |
| [0011](0011-padrao-de-modulo-com-pratica.md) | Padrão de módulo com prática: stack, limpeza, validadores e teste na conta | Aceito |
| [0012](0012-pratica-jdbc-retirada-do-modulo-02.md) | Prática opcional de crawler JDBC retirada do Módulo 02 | Aceito |
