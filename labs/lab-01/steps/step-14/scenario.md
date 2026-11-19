# Criar o Access Point do time de análise

O time de análise precisa ler os resumos, e só eles. Crie no bucket `curated` um S3 Access Point chamado `analytics` com uma política que dá à role `workshop-lab-01-analista-<region>` apenas a ação `s3:GetObject` nos objetos de `resumos/`.

**Critério de validação:** o Access Point `analytics` aponta para o bucket `curated`, e a política dele permite `s3:GetObject` à role analista só em `resumos/*`, sem nenhuma ação de escrita ou exclusão.
