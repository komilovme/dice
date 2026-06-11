"""Repository for atomic user-statistics updates."""

from __future__ import annotations

from sqlalchemy import update

from app.models.user import UserStats
from app.repositories.base import BaseRepository


class StatsRepository(BaseRepository[UserStats]):
    model = UserStats

    async def record_game_result(
        self,
        user_id: int,
        *,
        won: bool,
        draw: bool,
        wagered: int,
        net_change: int,
    ) -> None:
        """Apply a single battle outcome to the user's aggregate stats.

        All increments happen in one UPDATE so the row is touched once.
        ``net_change`` is positive for a win payout, negative for a loss.
        """
        values: dict = {
            UserStats.total_games: UserStats.total_games + 1,
            UserStats.total_wagered: UserStats.total_wagered + wagered,
        }
        if draw:
            values[UserStats.draws] = UserStats.draws + 1
        elif won:
            values[UserStats.wins] = UserStats.wins + 1
            values[UserStats.coins_earned] = UserStats.coins_earned + max(net_change, 0)
            values[UserStats.biggest_win] = func_greatest(UserStats.biggest_win, max(net_change, 0))
        else:
            values[UserStats.losses] = UserStats.losses + 1
            loss = abs(min(net_change, 0))
            values[UserStats.coins_spent] = UserStats.coins_spent + loss
            values[UserStats.biggest_loss] = func_greatest(UserStats.biggest_loss, loss)

        await self.session.execute(
            update(UserStats).where(UserStats.user_id == user_id).values(**values)
        )

    async def add_coins_earned(self, user_id: int, amount: int) -> None:
        await self.session.execute(
            update(UserStats)
            .where(UserStats.user_id == user_id)
            .values(coins_earned=UserStats.coins_earned + amount)
        )

    async def add_coins_spent(self, user_id: int, amount: int) -> None:
        await self.session.execute(
            update(UserStats)
            .where(UserStats.user_id == user_id)
            .values(coins_spent=UserStats.coins_spent + amount)
        )

    async def increment_tournaments_won(self, user_id: int) -> None:
        await self.session.execute(
            update(UserStats)
            .where(UserStats.user_id == user_id)
            .values(tournaments_won=UserStats.tournaments_won + 1)
        )


def func_greatest(column, value: int):
    """Return a SQL GREATEST(column, value) expression."""
    from sqlalchemy import func

    return func.greatest(column, value)
