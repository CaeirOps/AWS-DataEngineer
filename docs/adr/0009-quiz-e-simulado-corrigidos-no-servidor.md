# ADR-0009: Verificação de conhecimento e Simulado corrigidos no servidor

- **Status:** Aceito
- **Data:** 2026-11-22 (registro de decisão da v0.2.0)

## Contexto
As questões precisam treinar o formato do exame. Se o gabarito chegasse ao browser antes da resposta, bastaria abrir as ferramentas do desenvolvedor.

## Decisão
- As questões chegam ao browser sem o gabarito e sem as explicações. A correção acontece no servidor, que devolve a nota e a explicação de cada alternativa.
- Escolha única tem 4 alternativas e 1 correta. Múltipla escolha tem 5 ou mais alternativas e 2 ou mais corretas, e só conta como certa se o conjunto marcado for igual ao correto. A nota mínima padrão é 70%.
- O Simulado sorteia sem repetição, com 65 questões por padrão e os pesos D1 34%, D2 26%, D3 22% e D4 18%. A cota usa arredondamento meio para cima. Se a soma das cotas ficar abaixo de N, a diferença vai para o D1. Se ficar acima, o excesso sai do domínio de menor peso com cota maior que zero. A falta de questões em um domínio é completada pelos outros, na ordem dos pesos, e a tela avisa.
- O cronômetro de 130 minutos é opcional. O histórico guarda as 20 tentativas mais recentes.

## Alternativas rejeitadas
- Correção no browser: expõe o gabarito.
- Diferença de arredondamento sempre no D1: em simulados curtos, deixaria o D1 com zero questões.

## Consequências
- O quiz e o Simulado não usam a AWS e funcionam com a sessão expirada.
