# 🎲 Dice Arena — Telegram Dice Game Bot

A production-ready, fully async multiplayer **Telegram Dice Game Bot** with a
virtual economy, dice battles, lobbies, statistics, leaderboards, ranks,
monthly seasons, clans, achievements, loot cases, powerups, an admin panel, an
anti-cheat system, and a fun "AI announcer".

Built with **Python 3.13**, **Aiogram 3.x**, **PostgreSQL + SQLAlchemy 2.0
(async) + Alembic**, **Redis**, and **Docker** — designed to scale to tens of
thousands of users.

---

## ✨ Features

| Area | Highlights |
|------|------------|
| **Virtual economy** | Coins, daily/weekly rewards (with streaks), referral system, achievement rewards, free lucky chests, full append-only transaction ledger, configurable house edge |
| **Dice battles** | 1v1 duels, friend challenges, public & group battles, team battles, battle royale, jackpot & tournament modes |
| **Group optimization** | Reads the Telegram 🎲 emoji, settles the battle, **deletes the dice message** and posts one clean formatted result — no emoji spam |
| **Lobbies** | Create/join, public & password-protected private lobbies, auto-matchmaking |
| **Statistics** | Games, wins/losses, win rate, biggest win/loss, total wagered, current & best streak, coins earned/spent |
| **Leaderboards** | Richest, most wins, highest win rate, longest streak, per-season, group boards (Redis-cached) |
| **Ranks** | Bronze → Silver → Gold → Platinum → Diamond → Master → Grandmaster, driven by XP + wins |
| **Seasons** | Monthly reset, season rewards, season leaderboard, Hall of Fame, exclusive badges |
| **Clans** | Create/join, treasury, donations, clan leaderboard, clan wars, roles |
| **Achievements** | First win, 10/100/1000 wins, coins earned, win streaks, tournament champion, … (auto-awarded) |
| **Cases & rewards** | Common/Rare/Epic/Legendary cases → coins, titles, frames, badges, boosters |
| **Powerups** | Lucky Roll, Double Reward, Insurance, Streak Protection, XP Booster |
| **Admin panel** | Give/remove coins, ban/unban, view logs, force season reset, create events |
| **Anti-cheat** | Flood protection, cooldowns, bet limits, daily caps, referral-farm detection, suspicion scoring, audit logging |
| **AI announcer** | Context-aware hype lines (close calls, blowouts, comebacks, streaks, legendary wins) |

---

## 🏗 Architecture

Clean, layered architecture with one-way dependencies
(`handlers → services → repositories → models`):

```
app/
├── config/         # Settings (pydantic), constants/game balancing, logging
├── database/       # Async engine/session, declarative base, Redis client
├── models/         # SQLAlchemy ORM models (20 tables)
├── repositories/   # Data-access layer (all queries live here)
├── services/       # Business logic (economy, battles, clans, seasons, …)
├── filters/        # Aiogram filters (admin, chat type)
├── middlewares/    # DB session, auth/ban, throttling
├── keyboards/      # Inline keyboards + typed callback data
├── handlers/       # Aiogram routers (commands & callbacks)
├── scheduler/      # APScheduler jobs (season rollover, cleanup, cache warmup)
├── utils/          # Dice, security, codes, formatting, domain errors
├── bot.py          # Bot & Dispatcher factory
└── main.py         # Entrypoint (polling or webhook)
alembic/            # Migrations
```

Design principles:

- **Fully async** end-to-end (asyncpg, redis.asyncio, aiogram 3).
- **One transaction per update** via `DatabaseMiddleware` — handlers are atomic.
- **Atomic money movements**: balances change with guarded
  `UPDATE … WHERE balance >= amount RETURNING` statements, never read-modify-write.
- **Provably fair group dice**: the bot uses Telegram's server-authoritative
  dice value; for non-group flows it uses a CSPRNG (`secrets`).
- **Repositories own all SQL**; services compose them; handlers stay thin.

See [`docs/ERD.md`](docs/ERD.md) for the full data model.

---

## 🚀 Quick start (Docker)

```bash
git clone <your-repo-url> dice-game-bot
cd dice-game-bot
cp .env.example .env
# Edit .env: set BOT_TOKEN (from @BotFather) and ADMIN_IDS, change passwords.

docker compose up -d --build
docker compose logs -f bot
```

The `bot` container waits for PostgreSQL & Redis, applies migrations
(`alembic upgrade head`), then starts. By default it runs in **long-polling**
mode. Set `WEBHOOK_URL` in `.env` to switch to webhook mode.

## 🧑‍💻 Local development (without Docker)

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Start your own PostgreSQL and Redis, then:
cp .env.example .env        # point POSTGRES_HOST/REDIS_HOST at localhost
alembic upgrade head
python -m app.main
```

---

## 🎮 Commands

**Players**

| Command | Description |
|---------|-------------|
| `/start` | Open the main menu |
| `/profile` | View your profile (rank, stats, achievements) |
| `/balance` | Check your coins |
| `/daily`, `/weekly`, `/chest` | Claim rewards |
| `/play <bet>` | Quick duel vs the house (private chat) |
| `/duel <bet>` | Open a dice battle in a group — players then send 🎲 |
| `/lobby <bet>` / `/join <code>` / `/matchmake <bet>` | Lobbies |
| `/createclan <TAG> <name>` / `/joinclan <TAG>` / `/donate <amount>` / `/clantop` | Clans |
| `/top` | Leaderboards |
| `/history` | Transaction history |
| `/help` | How to play |

**Admins** (configured via `ADMIN_IDS`)

`/give`, `/take`, `/ban`, `/unban`, `/logs`, `/aclogs`, `/seasonreset`, `/event`

### The group dice flow (feature highlight)

1. A player runs `/duel 500` in a group.
2. Both players send the 🎲 emoji.
3. The bot reads each dice value, **deletes the raw dice messages**, and posts:

```
🎲 Dice Battle

Player A: 7
🏆 Player B: 9

🏆 Winner: Player B
💰 Reward: 980 Coins

🔥 Amazing roll!
```

---

## ⚙️ Configuration

All configuration is via environment variables (see [`.env.example`](.env.example)).
Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | — | Telegram bot token (required) |
| `ADMIN_IDS` | — | Comma-separated admin Telegram IDs |
| `POSTGRES_*` | — | Database connection + pool tuning |
| `REDIS_*` | — | Redis connection |
| `WEBHOOK_URL` | empty | If set, run in webhook mode (else long-polling) |
| `STARTING_BALANCE` | 1000 | New-user coin balance |
| `DAILY_REWARD` / `WEEKLY_REWARD` | 250 / 1500 | Periodic rewards |
| `REFERRAL_REWARD` | 500 | Referral bonus |
| `MIN_BET` / `MAX_BET` | 10 / 1,000,000 | Bet limits |
| `HOUSE_EDGE` | 0.02 | Fraction skimmed from each PvP pot |
| `RATE_LIMIT_PER_SECOND` | 3 | Flood protection |
| `BATTLE_COOLDOWN_SECONDS` | 3 | Per-user battle cooldown |
| `RUN_SCHEDULER` | true | Run the scheduler in this process (one replica only) |

---

## 📚 Documentation

- [Database design & ERD](docs/ERD.md)
- [Deployment guide](docs/DEPLOYMENT.md)
- [Scalability guide](docs/SCALABILITY.md)
- [Security recommendations](docs/SECURITY.md)

## 🧪 Quality

```bash
ruff check app          # lint
mypy app                # type-check
pytest                  # tests
```

## 📝 License

MIT.
