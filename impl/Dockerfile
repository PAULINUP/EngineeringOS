FROM python:3.12-slim

# Não gera .pyc e não bufferiza o log (senão o log só aparece ao encerrar)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Processo sem privilégio: um comprometimento da aplicação não vira root
RUN useradd --create-home --uid 10001 eos && chown -R eos:eos /app
USER eos

EXPOSE 8000

# O orquestrador precisa saber que a aplicação está PRONTA, não só viva —
# /health/ready confere o banco antes de responder ok.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health/ready" || exit 1

# O app vive em main.py. O CMD anterior apontava para "src.api:app", que não
# existe (src/api.py define apenas o router) — o container nunca subia.
# $PORT é injetada por Railway/Heroku; 8000 é o padrão local.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips='*'"]
