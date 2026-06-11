"""Repository for battles and participants."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.config.constants import BattleMode, BattleStatus
from app.models.battle import Battle, BattleParticipant
from app.repositories.base import BaseRepository


class BattleRepository(BaseRepository[Battle]):
    model = Battle

    async def get_full(self, battle_id: int) -> Battle | None:
        result = await self.session.execute(
            select(Battle)
            .where(Battle.id == battle_id)
            .options(selectinload(Battle.participants).selectinload(BattleParticipant.user))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        mode: BattleMode,
        stake: int,
        created_by_id: int | None,
        season_id: int | None,
        chat_id: int | None = None,
        is_team_mode: bool = False,
        status: BattleStatus = BattleStatus.PENDING,
    ) -> Battle:
        battle = Battle(
            mode=mode,
            stake=stake,
            created_by_id=created_by_id,
            season_id=season_id,
            chat_id=chat_id,
            is_team_mode=is_team_mode,
            status=status,
        )
        self.session.add(battle)
        await self.session.flush()
        return battle

    async def add_participant(
        self, battle_id: int, user_id: int, *, team: int | None = None
    ) -> BattleParticipant:
        participant = BattleParticipant(battle_id=battle_id, user_id=user_id, team=team)
        self.session.add(participant)
        await self.session.flush()
        return participant

    async def find_open_public(self, mode: BattleMode, stake: int) -> Battle | None:
        """Find an open public battle awaiting an opponent (for matchmaking)."""
        result = await self.session.execute(
            select(Battle)
            .where(
                Battle.mode == mode,
                Battle.stake == stake,
                Battle.status == BattleStatus.PENDING,
            )
            .options(selectinload(Battle.participants))
            .order_by(Battle.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return result.scalar_one_or_none()

    async def find_active_in_chat(self, chat_id: int) -> Battle | None:
        """Return the open group battle awaiting rolls in a chat, if any."""
        result = await self.session.execute(
            select(Battle)
            .where(
                Battle.chat_id == chat_id,
                Battle.status.in_([BattleStatus.PENDING, BattleStatus.ACTIVE]),
            )
            .options(selectinload(Battle.participants).selectinload(BattleParticipant.user))
            .order_by(Battle.created_at.desc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return result.scalar_one_or_none()

    async def recent_for_user(self, user_id: int, limit: int = 10) -> list[Battle]:
        result = await self.session.execute(
            select(Battle)
            .join(BattleParticipant, BattleParticipant.battle_id == Battle.id)
            .where(BattleParticipant.user_id == user_id)
            .order_by(desc(Battle.created_at))
            .limit(limit)
        )
        return list(result.scalars().unique().all())
