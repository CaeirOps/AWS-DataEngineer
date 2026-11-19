## Passos no console

1. No console do S3, abra o bucket `workshop-lab-01-raw-<conta>-<region>`.
2. Na aba **Properties**, encontre **Bucket Versioning** e clique em **Edit**.
3. Escolha **Enable** e clique em **Save changes**.
4. Clique em **Validar**.

## O que explorar nesta tela

- Na mesma seção aparece **Multi-factor authentication (MFA) delete**. Ele só pode ser ligado pelo usuário root, pela CLI.
- Abra `clientes/` e ligue a chave **Show versions**. Os objetos gravados antes do versionamento aparecem com o *Version ID* `null`.
- Para ver uma versão nova: faça o upload de um arquivo qualquer com o nome `teste.txt` duas vezes na raiz do bucket e compare as versões. Depois apague as duas versões e o delete marker, se houver.

> [!WARNING] Depois de ativado, o versionamento não pode ser desligado, só suspenso. Em uma conta real, decida antes como as versões antigas serão apagadas (você faz isso no step 08).
