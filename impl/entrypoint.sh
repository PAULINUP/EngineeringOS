#!/bin/sh
# Uma imagem, dois papéis. A plataforma escolhe por EOS_ROLE, em vez de exigir
# um comando de start diferente por serviço (que é onde o deploy anterior
# quebrou em silêncio).
set -e

case "${EOS_ROLE:-api}" in
  worker)
    echo "Papel: worker (Celery)"
    exec celery -A src.celery_worker.celery_app worker \
      --loglevel="${CELERY_LOGLEVEL:-info}" \
      --concurrency="${CELERY_CONCURRENCY:-2}" \
      --max-tasks-per-child=200
    ;;
  beat)
    echo "Papel: agendador (Celery beat)"
    exec celery -A src.celery_worker.celery_app beat --loglevel=info
    ;;
  *)
    echo "Papel: api (uvicorn)"
    exec uvicorn main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips='*'
    ;;
esac
