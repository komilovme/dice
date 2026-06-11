# Scalability Guide

The bot is designed to scale to **tens of thousands of users**. This document
explains the levers and how to operate the system under load.

## 1. Where the load goes

| Workload | Bottleneck | Mitigation |
|----------|-----------|------------|
| Incoming updates | Bot process CPU / event loop | uvloop, async I/O, horizontal replicas (webhook) |
| Reads (profile, leaderboards) | PostgreSQL | Redis caching, targeted indexes, read replicas |
| Writes (battles, ledger) | PostgreSQL | Connection pooling, atomic updates, append-only ledger |
| Rate limiting / cooldowns | Redis | O(1) `INCR`/`SET NX EX`, sharded by key |

## 2. Horizontal scaling of the bot

- **Webhook mode** is required to run multiple bot replicas. Put them behind a
  load balancer that forwards `/webhook` to any replica. Long-polling cannot be
  safely run on more than one replica.
- The dispatcher's FSM state lives in **Redis** (`RedisStorage`), so any replica
  can handle any user's next update.
- The **scheduler must run on exactly one replica** (or a dedicated worker). Set
  `RUN_SCHEDULER=true` on a single replica/worker and `false` on the rest to
  avoid duplicate season rollovers and cleanups. A `worker` service is included
  (commented) in `docker-compose.yml` for this purpose.

```
                ┌───────────┐
  Telegram ───▶ │  LB / TLS │ ──┬─▶ bot replica 1 (RUN_SCHEDULER=false)
                └───────────┘   ├─▶ bot replica 2 (RUN_SCHEDULER=false)
                                └─▶ bot replica N (RUN_SCHEDULER=false)
                                     │
                       ┌─────────────┴───────────────┐
                       ▼                             ▼
                  PostgreSQL                      Redis
                (primary + replicas)        (cache/FSM/locks)
                       ▲
                  worker (RUN_SCHEDULER=true)
```

## 3. PostgreSQL

- **Connection pooling**: each replica keeps an async pool
  (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`, with `pool_pre_ping` and `pool_recycle`).
  Keep `replicas × (pool_size + max_overflow)` comfortably below the server's
  `max_connections`. For many replicas put **PgBouncer** (transaction pooling)
  in front and lower per-replica pool sizes.
- **Atomic counters**: balances and stats are updated with single
  `UPDATE … RETURNING` / `UPDATE … SET col = col + n` statements — no
  read-modify-write races, minimal lock duration.
- **Append-only ledger**: `transactions` is insert-only and time-indexed; it can
  be **range-partitioned by month** (`PARTITION BY RANGE (created_at)`) once it
  grows large, keeping indexes small and enabling cheap archival.
- **Read replicas**: route leaderboard/profile reads to a replica if the primary
  becomes write-bound (the repository layer isolates these queries).
- **Index hygiene**: indexes match query patterns (see `docs/ERD.md`). Review
  with `pg_stat_statements` and add/drop as real traffic dictates.

## 4. Redis

- Used for FSM storage, rate limiting/cooldowns (anti-cheat), distributed locks,
  and short-TTL leaderboard caching. All operations are O(1)/O(log n).
- Leaderboards are cached for 60s and warmed by the scheduler, so spikes of
  viewers do not translate into repeated full scans.
- Configure `maxmemory` + `allkeys-lru` (already set in compose) so Redis stays
  bounded; nothing in Redis is the source of truth.
- For very high throughput, use Redis Cluster or a managed Redis and shard by
  key (keys are already namespaced: `rl:`, `cd:`, `lb:`, `lock:`, FSM keys).

## 5. The group dice hot path

Group battles are the highest-frequency interactive flow. It is kept cheap:

- A single indexed lookup (`ix_battles_chat_status`) finds the open battle,
  using `FOR UPDATE SKIP LOCKED` so concurrent dice in the same chat serialise
  safely without blocking other chats.
- The raw dice message is deleted and exactly one result message is posted,
  minimising Telegram API calls and keeping chats clean.

## 6. Capacity planning rules of thumb

- Start with 2–3 bot replicas (webhook) + 1 worker.
- PostgreSQL: 2–4 vCPU / 8–16 GB to start; scale vertically first, then add a
  read replica and/or partition the ledger.
- Redis: 512 MB–1 GB is plenty for cache + FSM at tens of thousands of users.
- Watch: event-loop lag, DB pool checkout wait time, Redis latency, and Telegram
  API 429 rate-limit responses (aiogram backs off automatically).

## 7. Telegram API limits

- ~30 messages/second globally and ~20 messages/minute per group. Batch/avoid
  chatty per-roll messages in very large groups; the clean single-result design
  already minimises message volume. Use aiogram's built-in flood-control
  handling and consider per-chat queues if you broadcast events.
