"""Achievement evaluation service.

After meaningful events (battle finished, reward claimed) the relevant user is
re-evaluated against the achievement catalogue. Newly satisfied achievements are
unlocked and their coin rewards paid out automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.constants import ACHIEVEMENTS, TransactionType
from app.models.user import User
from app.repositories.achievement_repository import AchievementRepository
from app.services.base import BaseService
from app.services.economy_service import EconomyService


@dataclass(slots=True)
class UnlockedAchievement:
    code: str
    name: str
    icon: str
    reward_coins: int


class AchievementService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.repo = AchievementRepository(session)
        self.economy = EconomyService(session, redis)

    def _metric_value(self, user: User, metric: str) -> int:
        stats = user.stats
        match metric:
            case "wins":
                return stats.wins if stats else 0
            case "coins_earned":
                return stats.coins_earned if stats else 0
            case "best_streak":
                return user.best_streak
            case "tournaments_won":
                return stats.tournaments_won if stats else 0
            case _:
                return 0

    async def evaluate(self, user: User) -> list[UnlockedAchievement]:
        """Unlock any newly-earned achievements and pay rewards.

        Returns the list of achievements unlocked in this call (for notifying
        the player).
        """
        already = await self.repo.unlocked_codes(user.id)
        unlocked: list[UnlockedAchievement] = []

        for code, definition in ACHIEVEMENTS.items():
            if code in already or not definition.metric:
                continue
            if self._metric_value(user, definition.metric) >= definition.threshold:
                await self.repo.unlock(user.id, code)
                if definition.reward_coins:
                    await self.economy.credit(
                        user.id,
                        definition.reward_coins,
                        type=TransactionType.ACHIEVEMENT_REWARD,
                        description=f"Achievement: {definition.name}",
                        reference=code,
                    )
                unlocked.append(
                    UnlockedAchievement(
                        code=code,
                        name=definition.name,
                        icon=definition.icon,
                        reward_coins=definition.reward_coins,
                    )
                )
        return unlocked

    async def list_for_user(self, user: User):
        unlocked = await self.repo.unlocked_codes(user.id)
        return [(definition, definition.code in unlocked) for definition in ACHIEVEMENTS.values()]
