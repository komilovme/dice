"""Repository for clans, clan members, and clan wars."""

from __future__ import annotations

from sqlalchemy import desc, select, update
from sqlalchemy.orm import selectinload

from app.config.constants import ClanRole
from app.models.clan import Clan, ClanMember, ClanWar
from app.repositories.base import BaseRepository


class ClanRepository(BaseRepository[Clan]):
    model = Clan

    async def get_full(self, clan_id: int) -> Clan | None:
        result = await self.session.execute(
            select(Clan)
            .where(Clan.id == clan_id)
            .options(selectinload(Clan.members).selectinload(ClanMember.user))
        )
        return result.scalar_one_or_none()

    async def get_by_tag(self, tag: str) -> Clan | None:
        result = await self.session.execute(select(Clan).where(Clan.tag == tag))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Clan | None:
        result = await self.session.execute(select(Clan).where(Clan.name == name))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        tag: str,
        description: str | None,
        leader_id: int,
        emblem: str = "🛡",
    ) -> Clan:
        clan = Clan(
            name=name,
            tag=tag,
            description=description,
            leader_id=leader_id,
            emblem=emblem,
        )
        self.session.add(clan)
        await self.session.flush()
        return clan

    async def get_membership(self, user_id: int) -> ClanMember | None:
        result = await self.session.execute(
            select(ClanMember)
            .where(ClanMember.user_id == user_id)
            .options(selectinload(ClanMember.clan))
        )
        return result.scalar_one_or_none()

    async def add_member(
        self, clan_id: int, user_id: int, role: ClanRole = ClanRole.MEMBER
    ) -> ClanMember:
        member = ClanMember(clan_id=clan_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.session.flush()
        return member

    async def adjust_treasury(self, clan_id: int, delta: int) -> int:
        result = await self.session.execute(
            update(Clan)
            .where(Clan.id == clan_id)
            .values(treasury=Clan.treasury + delta)
            .returning(Clan.treasury)
        )
        return int(result.scalar_one())

    async def add_points(self, clan_id: int, points: int) -> None:
        await self.session.execute(
            update(Clan).where(Clan.id == clan_id).values(total_points=Clan.total_points + points)
        )

    async def add_contribution(self, member_id: int, amount: int) -> None:
        await self.session.execute(
            update(ClanMember)
            .where(ClanMember.id == member_id)
            .values(contributed=ClanMember.contributed + amount)
        )

    async def leaderboard(self, limit: int = 10) -> list[Clan]:
        result = await self.session.execute(
            select(Clan).order_by(desc(Clan.total_points)).limit(limit)
        )
        return list(result.scalars().all())

    async def create_war(self, *, clan_a_id: int, clan_b_id: int, prize_pool: int) -> ClanWar:
        war = ClanWar(clan_a_id=clan_a_id, clan_b_id=clan_b_id, prize_pool=prize_pool)
        self.session.add(war)
        await self.session.flush()
        return war
