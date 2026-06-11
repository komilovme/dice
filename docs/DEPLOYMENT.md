# Deployment Guide

This guide covers deploying the Dice Game Bot with Docker Compose (recommended),
manually, and in webhook mode, plus migration management.

## 1. Prerequisites

- A Telegram bot token from [@BotFather](https://t.me/BotFather).
- Docker + Docker Compose **or** Python 3.13, PostgreSQL 14+, and Redis 6+.
- Your Telegram numeric user ID(s) for admin access (get it from
  [@userinfobot](https://t.me/userinfobot)).

## 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```ini
BOT_TOKEN=123456:your-real-token
ADMIN_IDS=11111111,22222222
POSTGRES_PASSWORD=<strong-random-password>
WEBHOOK_SECRET=<long-random-string>     # only needed for webhook mode
```

> **Never commit `.env`.** It is git-ignored by default.

## 3. Deploy with Docker Compose (recommended)

```bash
docker compose up -d --build
```

This starts three services:

- `postgres` — PostgreSQL 16 with a persistent volume (`pgdata`).
- `redis` — Redis 7 with AOF persistence and an LRU memory cap (`redisdata`).
- `bot` — the bot; on startup it waits for the datastores, runs
  `alembic upgrade head`, then launches.

Check it is healthy:

```bash
docker compose ps
docker compose logs -f bot
```

Stop / update:

```bash
docker compose down                # stop (keeps volumes/data)
docker compose up -d --build       # redeploy after code changes
docker compose down -v             # ⚠️ also deletes data volumes
```

## 4. Manual deployment (systemd)

1. Install dependencies into a virtualenv:

   ```bash
   python3.13 -m venv /opt/dicebot/.venv
   /opt/dicebot/.venv/bin/pip install -r requirements.txt
   ```

2. Provision PostgreSQL and Redis, and point `.env` at them
   (`POSTGRES_HOST`, `REDIS_HOST`, …).

3. Apply migrations:

   ```bash
   cd /opt/dicebot && .venv/bin/alembic upgrade head
   ```

4. Create a systemd unit `/etc/systemd/system/dicebot.service`:

   ```ini
   [Unit]
   Description=Dice Game Bot
   After=network.target postgresql.service redis.service

   [Service]
   User=dicebot
   WorkingDirectory=/opt/dicebot
   EnvironmentFile=/opt/dicebot/.env
   ExecStart=/opt/dicebot/.venv/bin/python -m app.main
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   systemctl daemon-reload
   systemctl enable --now dicebot
   journalctl -u dicebot -f
   ```

## 5. Polling vs Webhook

- **Long-polling (default):** leave `WEBHOOK_URL` empty. Simplest; works behind
  NAT with no inbound ports. Great for a single replica.
- **Webhook (recommended at scale):** set:

  ```ini
  WEBHOOK_URL=https://bot.example.com
  WEBHOOK_PATH=/webhook
  WEBHOOK_SECRET=<long-random-string>
  WEBAPP_PORT=8080
  ```

  Put the bot behind a TLS-terminating reverse proxy (nginx/Caddy/Traefik)
  forwarding `https://bot.example.com/webhook` → `bot:8080`. Telegram requires
  HTTPS on port 443/80/88/8443; terminate TLS at the proxy.

  Example nginx location:

  ```nginx
  location /webhook {
      proxy_pass http://127.0.0.1:8080;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $remote_addr;
  }
  ```

## 6. Database migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "describe change"

# Roll back the most recent migration
alembic downgrade -1

# Preview SQL without touching the DB (offline)
ALEMBIC_DB_URL=postgresql+psycopg2://u:p@host/db alembic upgrade head --sql
```

The Docker `bot` service runs `alembic upgrade head` automatically on startup.
You can also run migrations as a one-off: `docker compose run --rm bot migrate`.

## 7. Backups

- **PostgreSQL:** schedule `pg_dump` (logical) and/or use WAL archiving / a
  managed service with PITR.

  ```bash
  docker compose exec postgres pg_dump -U dicebot dicebot | gzip > backup_$(date +%F).sql.gz
  ```

- **Redis:** Redis here is a cache + FSM store + rate-limiter. It is **not** the
  source of truth — all durable state is in PostgreSQL — but AOF persistence is
  enabled so FSM state survives restarts.

## 8. Upgrades / zero-downtime

1. Build the new image.
2. Run migrations (backwards-compatible first): `docker compose run --rm bot migrate`.
3. Roll the `bot` replicas. With webhook mode + multiple replicas behind a load
   balancer you can do a rolling restart with no downtime.

## 9. Health & observability

- Logs are structured (JSON in production) — ship them to Loki/ELK/CloudWatch.
- Postgres and Redis containers have health checks; `bot` waits for both.
- Add an uptime monitor that sends `/start` to a canary chat, or watch the
  `startup.complete` log line.
