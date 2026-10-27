# AWS Certified Data Engineer – Associate (DEA-C01)
## Laboratórios Práticos de Data Engineering na AWS

[![AWS](https://img.shields.io/badge/AWS-Data%20Engineer-orange?logo=amazon-aws)](https://aws.amazon.com/certification/certified-data-engineer-associate/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Idioma](https://img.shields.io/badge/Idioma-Português-green)](README.md)

---

## Sobre o Projeto

Este repositório reúne laboratórios práticos de **Data Engineering na AWS**, desenvolvidos como material de estudo para a certificação **AWS Certified Data Engineer – Associate (DEA-C01)**.

A proposta é aprender construindo: cada laboratório apresenta um conceito do exame, implementa um pipeline ou solução real em ambiente AWS, e documenta o raciocínio por trás de cada decisão.

> Toda a documentação está em **português**, preservando os termos técnicos em inglês (ex.: *pipeline*, *ingestion*, *batch*, *streaming*).

---

## Objetivos

- Cobrir os domínios do exame DEA-C01 com exercícios práticos e reproduzíveis.
- Desenvolver fluência em Apache Spark, PySpark, AWS Glue, Amazon S3, Redshift, Kinesis e demais serviços de dados da AWS.
- Documentar cada laboratório de forma clara para que outros profissionais possam reproduzir e aprender.
- Fomentar a troca de conhecimento na comunidade AWS brasileira.

---

## Domínios do Exame (DEA-C01)

| Domínio | Descrição | Peso |
|---------|-----------|------|
| 1 | Ingestão e transformação de dados | 34% |
| 2 | Armazenamento e gerenciamento de dados | 26% |
| 3 | Operações e suporte a pipelines de dados | 22% |
| 4 | Segurança e governança de dados | 18% |

---

## Estrutura do Repositório

```
AWS-DataEngineer/
├── README.md              # Este arquivo
├── LICENSE                # Licença MIT
├── .gitignore             # Arquivos ignorados pelo Git
├── docs/                  # Documentação complementar e guias
├── datasets/              # Dados fictícios para os laboratórios
└── labs/                  # Laboratórios práticos
    └── lab-01-spark-fundamentals/   # Em breve
```

---

## Laboratórios

| # | Laboratório | Domínio | Status |
|---|-------------|---------|--------|
| 01 | Fundamentos de Apache Spark e PySpark | Transformação | 🔜 Em breve |

> Novos laboratórios serão adicionados progressivamente.

---

## Pré-requisitos

Para executar os laboratórios localmente você precisará ter instalado:

- **Python 3.9+**
- **Java 11 ou 17** (exigido pelo Apache Spark — recomendamos o Java 17 via [Homebrew](https://brew.sh/): `brew install openjdk@17`)
- **AWS CLI v2** ([guia oficial](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))

> O PySpark e demais dependências são instalados automaticamente via `pip` no passo abaixo.

---

## Configuração do Ambiente

### 1. Clone o repositório

```bash
git clone https://github.com/CaeirOps/AWS-DataEngineer.git
cd AWS-DataEngineer
```

### 2. Crie e ative o virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure o JAVA_HOME (necessário para o Spark)

Adicione ao seu `~/.zshrc` ou `~/.bashrc`:

```bash
# Java 17 via Homebrew (macOS)
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
export PYSPARK_PYTHON=$(which python3)
```

Recarregue: `source ~/.zshrc`

### 5. Configure as credenciais AWS

```bash
aws configure
```

Informe sua `Access Key ID`, `Secret Access Key`, região padrão (ex.: `us-east-1`) e formato de saída (ex.: `json`).

### 6. Valide o ambiente

```bash
python3 -c "import pyspark; print('PySpark OK:', pyspark.__version__)"
aws sts get-caller-identity
```

---

## Como Contribuir

Contribuições são bem-vindas! Veja como participar:

1. Faça um *fork* do repositório.
2. Crie uma *branch* descritiva: `git checkout -b lab/02-glue-etl`.
3. Implemente seu laboratório seguindo o padrão dos existentes.
4. Abra um *Pull Request* com uma descrição clara do que foi adicionado.

**Diretrizes:**
- Documentação em português, termos técnicos em inglês.
- Use apenas dados fictícios nos laboratórios.
- Nunca inclua credenciais, tokens ou informações sensíveis.
- Prefira recursos AWS de baixo custo ou elegíveis ao *Free Tier*.

---

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

---

## Autor

**Ricardo Caeiro** — [@CaeirOps](https://github.com/CaeirOps)

*Construído com o objetivo de aprender em público e devolver à comunidade.*
