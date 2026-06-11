"""Clan system service: creation, membership, treasury and clan wars."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config.constants import ClanRole, TransactionType
from app.models.clan import Clan, ClanWar
from app.models.user import User
from app.repositories.clan_repository import ClanRepository
from app.services.base import BaseService
from app.services.economy_service import EconomyService
from app.utils.exceptions import NotFoundError, PermissionError_, ValidationError

CLAN_CREATION_COST = 10_000
DONATION_POINTS_DIVISOR = 100  # 1 clan point per 100 coins donated
CLAN_WAR_DURATION = timedelta(days=3)


class ClanService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.repo = ClanRepository(session)
        self.economy = EconomyService(session, redis)

    async def create_clan(
        self, *, leader: User, name: str, tag: str, description: str | None = None
    ) -> Clan:
        name = name.strip()
        tag = tag.strip().upper()
        if not (3 <= len(name) <= 48):
            raise ValidationError("Clan name must be 3-48 characters.")
        if not (2 <= len(tag) <= 8) or not tag.isalnum():
            raise ValidationError("Clan tag must be 2-8 alphanumeric characters.")
        if await self.repo.get_membership(leader.id) is not None:
            raise ValidationError("You are already in a clan. Leave it first.")
        if await self.repo.get_by_name(name) is not None:
            raise ValidationError("A clan with that name already exists.")
        if await self.repo.get_by_tag(tag) is not None:
            raise ValidationError("That clan tag is taken.")

        await self.economy.debit(
            leader.id,
            CLAN_CREATION_COST,
            type=TransactionType.CLAN_WITHDRAW,
            description="Clan creation fee",
        )
        clan = await self.repo.create(
            name=name, tag=tag, description=description, leader_id=leader.id
        )
        await self.repo.add_member(clan.id, leader.id, role=ClanRole.LEADER)
        return clan

    async def join_clan(self, *, user: User, tag: str) -> Clan:
        if await self.repo.get_membership(user.id) is not None:
            raise ValidationError("You are already in a clan.")
        clan = await self.repo.get_by_tag(tag.strip().upper())
        if clan is None:
            raise NotFoundError("No clan with that tag.")
        full = await self.repo.get_full(clan.id)
        assert full is not None
        if full.member_count >= full.max_members:
            raise ValidationError("That clan is full.")
        await self.repo.add_member(clan.id, user.id, role=ClanRole.MEMBER)
        return clan

    async def leave_clan(self, *, user: User) -> None:
        membership = await self.repo.get_membership(user.id)
        if membership is None:
            raise ValidationError("You are not in a clan.")
        if membership.role == ClanRole.LEADER:
            raise PermissionError_("Leaders must transfer leadership or disband before leaving.")
        await self.session.delete(membership)

    async def donate(self, *, user: User, amount: int) -> int:
        """Donate coins to the clan treasury. Returns the new treasury balance."""
        if amount <= 0:
            raise ValidationError("Donation must be positive.")
        membership = await self.repo.get_membership(user.id)
        if membership is None:
            raise ValidationError("You are not in a clan.")
        await self.economy.debit(
            user.id,
            amount,
            type=TransactionType.CLAN_DONATION,
            description=f"Donation to clan #{membership.clan_id}",
        )
        treasury = await self.repo.adjust_treasury(membership.clan_id, amount)
        await self.repo.add_contribution(membership.id, amount)
        await self.repo.add_points(membership.clan_id, amount // DONATION_POINTS_DIVISOR)
        return treasury

    async def withdraw(self, *, user: User, amount: int) -> int:
        """Leader/co-leader withdraws from the treasury to their balance."""
        membership = await self.repo.get_membership(user.id)
        if membership is None:
            raise ValidationError("You are not in a clan.")
        if membership.role not in (ClanRole.LEADER, ClanRole.CO_LEADER):
            raise PermissionError_("Only leaders can withdraw from the treasury.")
        full = await self.repo.get_full(membership.clan_id)
        assert full is not None
        if amount <= 0 or amount > full.treasury:
            raise ValidationError("Invalid withdrawal amount.")
        await self.repo.adjust_treasury(membership.clan_id, -amount)
        await self.economy.credit(
            user.id,
            amount,
            type=TransactionType.CLAN_WITHDRAW,
            description=f"Treasury withdrawal clan #{membership.clan_id}",
        )
        return full.treasury - amount

    async def leaderboard(self, limit: int = 10) -> list[Clan]:
        return await self.repo.leaderboard(limit)

    async def my_clan(self, user: User) -> Clan | None:
        membership = await self.repo.get_membership(user.id)
        if membership is None:
            return None
        return await self.repo.get_full(membership.clan_id)

    # ----- Clan wars -----
    async def declare_war(
        self, *, challenger: User, opponent_tag: str, prize_pool: int = 0
    ) -> ClanWar:
        membership = await self.repo.get_membership(challenger.id)
        if membership is None or membership.role not in (
            ClanRole.LEADER,
            ClanRole.CO_LEADER,
        ):
            raise PermissionError_("Only clan leaders can declare war.")
        opponent = await self.repo.get_by_tag(opponent_tag.strip().upper())
        if opponent is None:
            raise NotFoundError("Opponent clan not found.")
        if opponent.id == membership.clan_id:
            raise ValidationError("A clan cannot war itself.")
        war = await self.repo.create_war(
            clan_a_id=membership.clan_id,
            clan_b_id=opponent.id,
            prize_pool=prize_pool,
        )
        war.ends_at = datetime.now(UTC) + CLAN_WAR_DURATION
        await self.session.flush()
        return war
