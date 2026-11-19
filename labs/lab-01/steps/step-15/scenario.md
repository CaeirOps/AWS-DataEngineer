# Replicação entre Regions (prática opcional)

A AnyCompany quer uma cópia dos dados brutos em outra Region, para recuperação de desastre. Crie um bucket de destino em outra Region e uma regra de replicação (CRR) no bucket `raw`.

- **Bucket de destino:** `workshop-lab-01-dr-<conta>-<region-de-destino>`, com versionamento ativado e Block Public Access ligado.
- **Regra:** replica todos os objetos do `raw`, com uma role do IAM própria para a replicação.

**Critério de validação:** o bucket `raw` tem uma regra de replicação ativa cujo destino fica em uma Region diferente da do workshop.

> [!COST] A replicação cobra o armazenamento das cópias na outra Region, a transferência entre Regions e as requisições de replicação. O bucket de destino e a role ficam fora da stack: remova os dois no step 17.
