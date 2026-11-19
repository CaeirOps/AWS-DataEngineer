# Como usar o workshop

Os módulos seguintes intercalam teoria e prática na sua conta AWS. Este step explica as partes da tela que você vai usar.

## Sequência de um módulo

1. **Objetivos:** as skills do exame que o módulo cobre.
2. **Conceitos e práticas:** steps de teoria intercalados com tarefas. Você lê o conceito e já executa a tarefa correspondente.
3. **Verificação de conhecimento:** questões no formato do exame, com explicação de cada alternativa.
4. **Resumo:** o que foi visto e links para a documentação oficial da AWS.

## Deploy, validação e finalização

- **Deploy:** nos módulos com prática, um step cria o cenário inicial na sua conta com AWS CloudFormation, numa stack chamada `workshop-lab-NN`.
- **Validar:** depois de cada tarefa, o botão **Validar** confere na sua conta se o resultado está correto. Depois de algumas tentativas sem sucesso, aparece uma dica detalhada.
- **Finalizar Lab:** o step de teardown exclui a stack e lista os recursos que você precisa conferir e remover manualmente.

## Trilhas Console e CLI

Cada tarefa tem duas trilhas. A trilha **Console** mostra o passo a passo pelas telas do serviço. A trilha **CLI** mostra os comandos do AWS CLI. Escolha a que preferir e alterne quando quiser. A validação é a mesma nas duas.

## Custos

> [!COST] Antes do deploy, o módulo mostra o **Aviso de custo**, com os serviços cobrados e o link da página oficial de preços de cada um. Faça um módulo por vez e sempre finalize ao terminar.

Práticas com serviços de custo mais alto aparecem com o selo **Opcional**. Você pode pulá-las e concluir o módulo mesmo assim.

## Sessão AWS

O cabeçalho mostra quanto tempo falta para a sessão expirar e avisa quando faltam 10 minutos. Ao expirar, as ações que usam a AWS ficam bloqueadas. Para renovar, rode no seu computador:

```bash
aws sso login --profile <seu-profile>
python start.py --refresh
```

> [!WARNING] Nunca cole credenciais na interface, em issues ou em capturas de tela. O workshop recebe só credenciais temporárias, entregues pelo `start.py`.

## Verificação de conhecimento e Simulado

As Verificações de conhecimento e o Simulado final não usam a AWS e não geram custo. O Simulado está no Dashboard e sorteia questões de todos os módulos.
