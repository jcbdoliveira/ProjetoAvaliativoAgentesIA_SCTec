#!/usr/bin/env bash
set -Eeuo pipefail

echo "Aguardando o PostgreSQL ficar disponível..."
until uv run python -c "from app.database import engine; engine.connect().close()" >/dev/null 2>&1; do
  sleep 2
done

echo "Executando migrations e seed inicial do SaaS..."
uv run alembic upgrade head

echo "Iniciando servidor FastAPI do SaaS..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
