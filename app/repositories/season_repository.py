"""Repository for seasons, season participants and the hall of fame."""

from __future__ import annotations

from sqlalchemy import desc, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.season import HallOfFame, Season, SeasonParticipant
from app.repositories.base import BaseRepository


class SeasonRepository(BaseRepository[Season]):
    model = Season

    async def get_active(self) -> Season | None:
        result = await self.session.execute(
            select(Season).where(Season.is_active.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()

    async def latest_number(self) -> int:
        result = await self.session.execute(select(func_max(Season.number)))
        return int(result.scalar_one() or 0)

    async def create(self, *, name: str, number: int, ends_at=None) -> Season:
        season = Season(name=name, number=number, ends_at=ends_at)
        self.session.add(season)
        await self.session.flush()
        return season

    async def deactivate(self, season_id: int) -> None:
        from sqlalchemy import func

        await self.session.execute(
            update(Season)
            .where(Season.id == season_id)
            .values(is_active=False, finalized_at=func.now())
        )

    async def add_points(
        self, *, season_id: int, user_id: int, points: int, won: bool, coins: int
    ) -> None:
        """Upsert a season participant and accumulate their score."""
        stmt = (
            pg_insert(SeasonParticipant)
            .values(
                season_id=season_id,
                user_id=user_id,
                season_points=points,
                season_wins=1 if won else 0,
                season_coins=coins,
            )
            .on_conflict_do_update(
                index_elements=["season_id", "user_id"],
                set_={
                    "season_points": SeasonParticipant.season_points + points,
                    "season_wins": SeasonParticipant.season_wins + (1 if won else 0),
                    "season_coins": SeasonParticipant.season_coins + coins,
                },
            )
        )
        await self.session.execute(stmt)

    async def top_participants(self, season_id: int, limit: int = 100) -> list[SeasonParticipant]:
        result = await self.session.execute(
            select(SeasonParticipant)
            .where(SeasonParticipant.season_id == season_id)
            .order_by(desc(SeasonParticipant.season_points))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def record_hall_of_fame(
        self,
        *,
        season_id: int,
        user_id: int,
        placement: int,
        season_points: int,
        badge_code: str | None,
        reward_coins: int,
    ) -> HallOfFame:
        hof = HallOfFame(
            season_id=season_id,
            user_id=user_id,
            placement=placement,
            season_points=season_points,
            badge_code=badge_code,
            reward_coins=reward_coins,
        )
        self.session.add(hof)
        await self.session.flush()
        return hof

    async def hall_of_fame(self, limit: int = 30) -> list[HallOfFame]:
        result = await self.session.execute(
            select(HallOfFame)
            .order_by(desc(HallOfFame.season_id), HallOfFame.placement)
            .limit(limit)
        )
        return list(result.scalars().all())


def func_max(column):
    from sqlalchemy import func

    return func.max(column)
