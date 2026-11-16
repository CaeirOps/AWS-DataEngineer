# Imagem base fixada por digest do indice multi-arquitetura (14.4)
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias primeiro, para aproveitar o cache de layers do Docker.
# Instalacao apenas com hashes e sem resolver dependencias (14.5)
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt

# Usuario nao root com UID/GID fixos (14.1); o diretorio de progresso pertence a ele
RUN groupadd --gid 10001 workshop \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin workshop \
 && mkdir -p /app/progress \
 && chown workshop:workshop /app/progress

COPY app/ ./app/
COPY labs/ ./labs/

USER 10001:10001

# Volume externo (nao copiado na imagem):
#   ./progress/ -> /app/progress/
# Nenhuma credencial entra na imagem nem por volume: elas chegam por variaveis de ambiente.

EXPOSE 5000

# python:3.11-slim nao inclui curl; o healthcheck usa a biblioteca padrao
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=3)"]

# Dentro do container o bind e 0.0.0.0; a restricao a localhost e feita
# na publicacao de porta do gateway (127.0.0.1:...).
# O diretorio temporario dos workers fica em /tmp (tmpfs, pois o rootfs e somente leitura).
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--worker-tmp-dir", "/tmp", "app.server:app"]
