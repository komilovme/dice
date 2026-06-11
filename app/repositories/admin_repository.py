"""Repository for admin action logs and anti-cheat flags."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from app.models.admin import AdminLog, AntiCheatLog
from app.repositories.base import BaseRepository


class AdminLogRepository(BaseRepository[AdminLog]):
    model = AdminLog

    async def record(
        self,
        *,
        admin_id: int,
        action: str,
        target_user_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> AdminLog:
        log = AdminLog(
            admin_id=admin_id,
            action=action,
            target_user_id=target_user_id,
            details=details or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def recent(self, limit: int = 25) -> list[AdminLog]:
        result = await self.session.execute(
            select(AdminLog).order_by(desc(AdminLog.created_at)).limit(limit)
        )
        return list(result.scalars().all())


class AntiCheatRepository(BaseRepository[AntiCheatLog]):
    model = AntiCheatLog

    async def flag(
        self,
        *,
        user_id: int | None,
        rule: str,
        severity: int = 1,
        description: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AntiCheatLog:
        log = AntiCheatLog(
            user_id=user_id,
            rule=rule,
            severity=severity,
            description=description,
            meta=meta or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def recent(self, limit: int = 25) -> list[AntiCheatLog]:
        result = await self.session.execute(
            select(AntiCheatLog).order_by(desc(AntiCheatLog.created_at)).limit(limit)
        )
        return list(result.scalars().all())
