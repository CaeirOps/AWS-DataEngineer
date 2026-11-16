FROM python:3.11-slim

WORKDIR /app

# Dependencias primeiro, para aproveitar o cache de layers do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY labs/ ./labs/

# Volumes externos (nao copiados na imagem):
#   ~/.aws      -> /root/.aws (somente-leitura)
#   ./progress/ -> /app/progress/

EXPOSE 5000

# python:3.11-slim nao inclui curl; o healthcheck usa a biblioteca padrao
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=3)" || exit 1

# Dentro do container o bind e 0.0.0.0; a restricao a localhost e feita
# na publicacao de porta do gateway (127.0.0.1:...).
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app.server:app"]
