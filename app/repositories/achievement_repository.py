"""Repository for user achievement unlocks."""

from __future__ import annotations

from sqlalchemy import select

from app.models.user_achievement import UserAchievement
from app.repositories.base import BaseRepository


class AchievementRepository(BaseRepository[UserAchievement]):
    model = UserAchievement

    async def unlocked_codes(self, user_id: int) -> set[str]:
        result = await self.session.execute(
            select(UserAchievement.code).where(UserAchievement.user_id == user_id)
        )
        return set(result.scalars().all())

    async def list_for_user(self, user_id: int) -> list[UserAchievement]:
        result = await self.session.execute(
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.unlocked_at.desc())
        )
        return list(result.scalars().all())

    async def unlock(self, user_id: int, code: str) -> UserAchievement:
        ua = UserAchievement(user_id=user_id, code=code)
        self.session.add(ua)
        await self.session.flush()
        return ua
