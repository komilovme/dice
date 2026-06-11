"""Loot case service: weighted reward draws funded by coins."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config.constants import (
    CASES,
    POWERUPS,
    CaseDefinition,
    CaseReward,
    PowerupType,
    RewardKind,
    TransactionType,
)
from app.models.user import User
from app.repositories.inventory_repository import (
    CaseOpeningRepository,
    InventoryRepository,
    PowerupRepository,
)
from app.services.base import BaseService
from app.services.economy_service import EconomyService
from app.utils.exceptions import NotFoundError

# Booster reward item codes that map onto powerups.
BOOSTER_MAP = {
    "xp_booster": PowerupType.XP_BOOSTER,
    "double_reward": PowerupType.DOUBLE_REWARD,
    "lucky_roll": PowerupType.LUCKY_ROLL,
    "insurance": PowerupType.INSURANCE,
    "streak_protection": PowerupType.STREAK_PROTECTION,
}


@dataclass(slots=True)
class CaseResult:
    case: CaseDefinition
    reward: CaseReward
    new_balance: int


class CaseService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.economy = EconomyService(session, redis)
        self.inventory = InventoryRepository(session)
        self.powerups = PowerupRepository(session)
        self.openings = CaseOpeningRepository(session)

    @staticmethod
    def _draw(case: CaseDefinition) -> CaseReward:
        total = sum(r.weight for r in case.rewards)
        pick = secrets.SystemRandom().uniform(0, total)
        cumulative = 0.0
        for reward in case.rewards:
            cumulative += reward.weight
            if pick <= cumulative:
                return reward
        return case.rewards[-1]

    async def open_case(self, *, user: User, case_code: str) -> CaseResult:
        case = CASES.get(case_code)
        if case is None:
            raise NotFoundError("Unknown case.")

        # Pay for the case first (raises InsufficientBalanceError if too poor).
        await self.economy.debit(
            user.id,
            case.price,
            type=TransactionType.CASE_OPEN,
            description=f"Opened {case.name}",
            reference=case_code,
        )

        reward = self._draw(case)
        new_balance = user.balance - case.price

        if reward.kind == RewardKind.COINS:
            new_balance = await self.economy.credit(
                user.id,
                reward.coins,
                type=TransactionType.CASE_REWARD,
                description=f"{case.name} reward",
                reference=case_code,
            )
        elif reward.kind == RewardKind.BOOSTER and reward.item_code in BOOSTER_MAP:
            ptype = BOOSTER_MAP[reward.item_code]
            definition = POWERUPS[ptype]
            expires = (
                datetime.now(UTC) + timedelta(seconds=definition.duration_seconds)
                if definition.duration_seconds
                else None
            )
            await self.powerups.grant(user_id=user.id, ptype=ptype, charges=1, expires_at=expires)
        else:  # TITLE / FRAME / BADGE
            await self.inventory.grant_item(
                user_id=user.id,
                kind=reward.kind,
                item_code=reward.item_code or reward.kind,
                label=reward.label,
            )

        await self.openings.record(
            user_id=user.id,
            case_code=case_code,
            rarity=case.rarity,
            price=case.price,
            reward_kind=reward.kind,
            reward_coins=reward.coins,
            reward_item_code=reward.item_code,
            reward_label=reward.label,
        )
        return CaseResult(case=case, reward=reward, new_balance=new_balance)
