"""Seasonal system service: rollover, rewards, and hall of fame.

A season runs for a calendar month. At rollover the current season is finalised
(top players rewarded and immortalised in the hall of fame) and a fresh season
begins. Per-season scores live in ``season_participants`` so each new season
starts from zero without touching lifetime stats or balances.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.config.constants import RewardKind, TransactionType
from app.models.season import Season
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.season_repository import SeasonRepository
from app.services.base import BaseService
from app.services.economy_service import EconomyService

# placement (inclusive upper bound) -> (coins, badge_code or None)
SEASON_REWARD_TIERS: tuple[tuple[int, int, str | None], ...] = (
    (1, 50_000, "season_champion"),
    (2, 30_000, "season_runner_up"),
    (3, 20_000, "season_bronze"),
    (10, 5_000, "season_top10"),
    (50, 2_000, None),
    (100, 1_000, None),
)


@dataclass(slots=True)
class SeasonRolloverResult:
    finalized_season: Season | None
    new_season: Season
    rewarded_players: int


def _reward_for(placement: int) -> tuple[int, str | None]:
    for upper, coins, badge in SEASON_REWARD_TIERS:
        if placement <= upper:
            return coins, badge
    return 0, None


class SeasonService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.repo = SeasonRepository(session)
        self.economy = EconomyService(session, redis)
        self.inventory = InventoryRepository(session)

    async def ensure_active_season(self) -> Season:
        """Return the active season, creating the first one if none exists."""
        season = await self.repo.get_active()
        if season is not None:
            return season
        return await self._create_next_season()

    async def _create_next_season(self) -> Season:
        number = await self.repo.latest_number() + 1
        now = datetime.now(UTC)
        name = f"Season {number} - {now:%B %Y}"
        return await self.repo.create(name=name, number=number)

    async def rollover(self) -> SeasonRolloverResult:
        """Finalise the current season and start a new one."""
        current = await self.repo.get_active()
        rewarded = 0
        if current is not None:
            rewarded = await self._finalize(current)
            await self.repo.deactivate(current.id)
        new_season = await self._create_next_season()
        return SeasonRolloverResult(
            finalized_season=current,
            new_season=new_season,
            rewarded_players=rewarded,
        )

    async def _finalize(self, season: Season) -> int:
        participants = await self.repo.top_participants(season.id, limit=100)
        rewarded = 0
        for placement, participant in enumerate(participants, start=1):
            coins, badge = _reward_for(placement)
            if coins == 0:
                continue
            await self.economy.credit(
                participant.user_id,
                coins,
                type=TransactionType.SEASON_REWARD,
                description=f"{season.name} placement #{placement}",
                reference=f"season:{season.id}",
            )
            if badge:
                await self.inventory.grant_item(
                    user_id=participant.user_id,
                    kind=RewardKind.BADGE,
                    item_code=badge,
                    label=f"{season.name} Badge",
                )
            await self.repo.record_hall_of_fame(
                season_id=season.id,
                user_id=participant.user_id,
                placement=placement,
                season_points=participant.season_points,
                badge_code=badge,
                reward_coins=coins,
            )
            rewarded += 1
        return rewarded

    async def hall_of_fame(self, limit: int = 30):
        return await self.repo.hall_of_fame(limit)
