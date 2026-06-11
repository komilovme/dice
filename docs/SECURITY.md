# Security Recommendations

Security guidance for operating the Dice Game Bot. The codebase ships with
sensible defaults; this document highlights what to verify and harden before and
during production.

## 1. Secrets management

- **Never commit `.env`** (it is git-ignored). Keep `BOT_TOKEN`,
  `POSTGRES_PASSWORD`, `WEBHOOK_SECRET`, and `REDIS_PASSWORD` out of version
  control.
- In production, inject secrets via your orchestrator's secret store (Docker
  secrets, Kubernetes Secrets, AWS Secrets Manager, etc.) rather than plaintext
  files where possible.
- Rotate the bot token immediately if it is ever exposed (regenerate in
  @BotFather) and rotate DB credentials on a schedule.

## 2. Webhook hardening

- Always serve the webhook over **HTTPS** behind a TLS-terminating proxy.
- Set a strong random `WEBHOOK_SECRET`. The bot registers it as Telegram's
  `secret_token` and the request handler validates the
  `X-Telegram-Bot-Api-Secret-Token` header, rejecting forged requests.
- Restrict inbound traffic to Telegram's IP ranges at the proxy/firewall if
  feasible, and expose only the webhook path.

## 3. Authorization

- Admin commands are gated by `IsAdminFilter`, which checks the configured
  `ADMIN_IDS`. The entire admin router is filtered, so non-admins cannot reach
  any privileged handler.
- Every admin action is recorded in `admin_logs` (who, what, target, details)
  for a complete audit trail.
- Clan treasury withdrawals and war declarations are role-checked
  (leader/co-leader only).

## 4. Input validation & abuse prevention

- **Bet limits**: every wager is validated against `MIN_BET`/`MAX_BET`.
- **Atomic, guarded balances**: debits use `UPDATE … WHERE balance >= amount`,
  so users can never spend coins they don't have, even under race conditions,
  and balances cannot go negative.
- **Flood protection**: `ThrottlingMiddleware` applies a per-user Redis rate
  limit before any DB work; abusive senders are dropped with a single warning.
- **Cooldowns & caps**: per-user battle cooldowns and a daily battle cap are
  enforced via Redis (`SET NX EX`, atomic counters).
- **Referral-farm detection**: bursts of referrals from one account are flagged
  and raise the account's `suspicion_score`.
- **Bans**: banned non-admins are blocked at the middleware layer before any
  handler runs.

## 5. Anti-cheat & fairness

- **Provably fair group dice**: the bot trusts Telegram's server-authoritative
  `message.dice.value` (validated to be in range 1–6) and never fabricates group
  rolls. Non-group rolls use a CSPRNG (`secrets`), not `random`.
- All suspicious events are written to `anti_cheat_logs` with a severity score;
  admins review them with `/aclogs`. Escalation thresholds
  (`SUSPICION_SOFT_LIMIT`, `SUSPICION_HARD_LIMIT`) let you restrict high-risk
  accounts.

## 6. Data protection

- Private lobby passwords are stored as **PBKDF2-HMAC-SHA256** hashes with a
  per-password random salt — never in plaintext — and verified in constant time.
- The `transactions` ledger is append-only with balance snapshots, giving a
  tamper-evident audit trail for dispute resolution.
- Only minimal Telegram profile data is stored (id, username, names, language).
  Avoid logging full PII; structured logs use stable identifiers.

## 7. Database & infrastructure

- Run PostgreSQL and Redis on a **private network**; do not expose their ports
  publicly. In the provided compose file they are reachable only on the internal
  Docker network.
- Set a strong `POSTGRES_PASSWORD` and a `REDIS_PASSWORD` (enable Redis AUTH).
- Apply least-privilege DB roles: the app needs DML on its tables; run
  migrations with a separate, more-privileged role if you prefer.
- Keep base images patched (`python:3.13-slim`, `postgres:16`, `redis:7`); the
  bot runs as a **non-root** user inside the container.

## 8. Dependency & supply-chain hygiene

- Pin and periodically audit dependencies (`pip-audit` / Dependabot).
- Treat any externally fetched content as untrusted; the bot does not execute
  user-supplied code.

## 9. Operational safety

- Back up PostgreSQL regularly and test restores (see `docs/DEPLOYMENT.md`).
- Monitor for anomalies: spikes in `anti_cheat_logs`, unusual coin inflation in
  `transactions`, or abnormal API error rates.
- Use the `HOUSE_EDGE` and reward settings to keep the economy balanced and
  resistant to inflation; review the ledger periodically for net coin issuance.
