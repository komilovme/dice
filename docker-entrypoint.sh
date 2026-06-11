#!/usr/bin/env bash
# Container entrypoint. Waits for dependencies, applies DB migrations, then
# launches the requested process. Usage (via CMD): bot | migrate | shell
set -euo pipefail

wait_for() {
    local host="$1" port="$2" name="$3" retries=60
    echo "Waiting for ${name} at ${host}:${port}..."
    until python -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(0 if s.connect_ex(('${host}', ${port}))==0 else 1)"; do
        retries=$((retries - 1))
        if [ "${retries}" -le 0 ]; then
            echo "ERROR: ${name} did not become available in time." >&2
            exit 1
        fi
        sleep 1
    done
    echo "${name} is up."
}

run_migrations() {
    echo "Applying database migrations..."
    alembic upgrade head
    echo "Migrations applied."
}

# Derive host/port for readiness checks from DATABASE_URL / REDIS_URL when
# present (Railway/Render style), else fall back to the discrete env vars.
pg_hostport=$(python - <<'PY'
import os
from urllib.parse import urlsplit
u = urlsplit(os.getenv("DATABASE_URL") or "")
print(u.hostname or os.getenv("POSTGRES_HOST", "postgres"),
      u.port or os.getenv("POSTGRES_PORT", "5432"))
PY
)
redis_hostport=$(python - <<'PY'
import os
from urllib.parse import urlsplit
u = urlsplit(os.getenv("REDIS_URL") or "")
print(u.hostname or os.getenv("REDIS_HOST", "redis"),
      u.port or os.getenv("REDIS_PORT", "6379"))
PY
)
PG_HOST=$(echo "$pg_hostport" | cut -d' ' -f1)
PG_PORT=$(echo "$pg_hostport" | cut -d' ' -f2)
RD_HOST=$(echo "$redis_hostport" | cut -d' ' -f1)
RD_PORT=$(echo "$redis_hostport" | cut -d' ' -f2)

wait_for "${PG_HOST}" "${PG_PORT}" "PostgreSQL"
wait_for "${RD_HOST}" "${RD_PORT}" "Redis"

case "${1:-bot}" in
    bot)
        run_migrations
        echo "Starting Dice Game Bot..."
        exec python -m app.main
        ;;
    migrate)
        run_migrations
        ;;
    worker)
        # Dedicated scheduler/worker process (RUN_SCHEDULER should be true here,
        # and false on the bot replicas).
        echo "Starting scheduler worker..."
        exec python -m app.main
        ;;
    shell)
        exec python
        ;;
    *)
        exec "$@"
        ;;
esac
