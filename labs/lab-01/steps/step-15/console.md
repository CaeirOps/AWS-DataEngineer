## Passos no console

1. Crie o bucket de destino: **Create bucket**, escolha outra Region (por exemplo `sa-east-1` se o workshop estiver em `us-east-1`), use o nome `workshop-lab-01-dr-<conta>-<region-de-destino>`, deixe o **Block all public access** marcado, ative **Bucket Versioning** e clique em **Create bucket**.
2. Abra o bucket `raw`, aba **Management**, e clique em **Create replication rule** na seção **Replication rules**.
3. Preencha:
   - **Replication rule name:** `dr`
   - **Status:** **Enabled**
   - **Choose a rule scope:** **Apply to all objects in the bucket**
   - **Destination:** **Choose a bucket in this account** e selecione o bucket de destino
   - **IAM role:** **Create new role**
4. Deixe as opções adicionais desligadas e clique em **Save**.
5. Quando o console perguntar se quer replicar os objetos que já existem, escolha **No, do not replicate existing objects**. A replicação dos existentes usa o S3 Batch Operations e tem custo próprio.
6. Copie de novo um CSV para gerar um objeto novo, por exemplo para `pedidos/dt=2026-03-12/`. Em alguns segundos, ele aparece no bucket de destino. No objeto de origem, **Properties > Replication status** muda para `COMPLETED`.
7. Clique em **Validar**.

## O que explorar nesta tela

- Em **Additional replication options**, veja **Replication Time Control (RTC)**, **Replication metrics** e **Delete marker replication**.
- Em **Destination storage class**, veja que as cópias podem ir direto para uma classe mais barata, como Glacier Instant Retrieval.
- No IAM, abra a role `s3crr_role_for_...` criada pelo console e leia as permissões que a replicação precisa.
