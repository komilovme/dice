"""Admin panel handlers. The whole router is gated by IsAdminFilter."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.is_admin import IsAdminFilter
from app.models.user import User
from app.services.admin_service import AdminService
from app.utils.exceptions import GameError
from app.utils.formatting import fmt_coins

router = Router(name="admin")
# Gate every handler in this router behind the admin filter.
router.message.filter(IsAdminFilter())

ADMIN_HELP = (
    "🛠 <b>Admin panel</b>\n\n"
    "/give &lt;user_id&gt; &lt;amount&gt; — grant coins\n"
    "/take &lt;user_id&gt; &lt;amount&gt; — remove coins\n"
    "/ban &lt;user_id&gt; [reason] — ban a user\n"
    "/unban &lt;user_id&gt; — unban a user\n"
    "/logs — recent admin actions\n"
    "/aclogs — recent anti-cheat flags\n"
    "/seasonreset — force a season rollover\n"
    "/event &lt;name&gt; &lt;message&gt; — schedule an announcement"
)


@router.message(Command("admin", "adminhelp"))
async def cmd_admin_help(message: Message) -> None:
    await message.answer(ADMIN_HELP)


@router.message(Command("give"))
async def cmd_give(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3 or not parts[1].lstrip("-").isdigit() or not parts[2].isdigit():
        await message.answer("Usage: /give &lt;user_id&gt; &lt;amount&gt;")
        return
    try:
        new_balance = await AdminService(session, redis).give_coins(
            admin_id=user.telegram_id,
            target_telegram_id=int(parts[1]),
            amount=int(parts[2]),
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        f"✅ Granted {fmt_coins(int(parts[2]))} coins. New balance: <b>{fmt_coins(new_balance)}</b>"
    )


@router.message(Command("take"))
async def cmd_take(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3 or not parts[1].lstrip("-").isdigit() or not parts[2].isdigit():
        await message.answer("Usage: /take &lt;user_id&gt; &lt;amount&gt;")
        return
    try:
        new_balance = await AdminService(session, redis).remove_coins(
            admin_id=user.telegram_id,
            target_telegram_id=int(parts[1]),
            amount=int(parts[2]),
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(f"✅ Done. New balance: <b>{fmt_coins(new_balance)}</b>")


@router.message(Command("ban"))
async def cmd_ban(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Usage: /ban &lt;user_id&gt; [reason]")
        return
    reason = parts[2] if len(parts) > 2 else None
    try:
        await AdminService(session, redis).ban_user(
            admin_id=user.telegram_id,
            target_telegram_id=int(parts[1]),
            reason=reason,
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(f"🚫 User {parts[1]} banned.")


@router.message(Command("unban"))
async def cmd_unban(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Usage: /unban &lt;user_id&gt;")
        return
    try:
        await AdminService(session, redis).unban_user(
            admin_id=user.telegram_id, target_telegram_id=int(parts[1])
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(f"✅ User {parts[1]} unbanned.")


@router.message(Command("logs"))
async def cmd_logs(message: Message, session: AsyncSession, redis: Redis) -> None:
    logs = await AdminService(session, redis).recent_logs(limit=20)
    if not logs:
        await message.answer("No admin actions logged yet.")
        return
    lines = ["🧾 <b>Recent admin actions</b>", ""]
    for log in logs:
        lines.append(
            f"• {log.created_at:%Y-%m-%d %H:%M} — <b>{log.action}</b> "
            f"by {log.admin_id}" + (f" → {log.target_user_id}" if log.target_user_id else "")
        )
    await message.answer("\n".join(lines))


@router.message(Command("aclogs"))
async def cmd_aclogs(message: Message, session: AsyncSession, redis: Redis) -> None:
    logs = await AdminService(session, redis).recent_anticheat(limit=20)
    if not logs:
        await message.answer("No anti-cheat flags. All clean! ✅")
        return
    lines = ["🛡 <b>Recent anti-cheat flags</b>", ""]
    for log in logs:
        lines.append(
            f"• [{log.severity}] <b>{log.rule}</b> — user {log.user_id}: {log.description or ''}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("seasonreset"))
async def cmd_season_reset(
    message: Message, user: User, session: AsyncSession, redis: Redis
) -> None:
    result = await AdminService(session, redis).force_season_reset(admin_id=user.telegram_id)
    await message.answer(
        f"🗓 Season rolled over. New season: <b>#{result.new_season.number}</b>. "
        f"Rewarded {result.rewarded_players} players."
    )


@router.message(Command("event"))
async def cmd_event(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /event &lt;name&gt; &lt;message&gt;")
        return
    await AdminService(session, redis).create_event(
        admin_id=user.telegram_id,
        name=parts[1],
        payload={"message": parts[2], "ttl": 86_400},
    )
    await message.answer(f"📣 Event '{parts[1]}' created.")
