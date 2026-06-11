"""Repository for lobbies and lobby members / matchmaking."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config.constants import BattleMode, LobbyStatus
from app.models.lobby import Lobby, LobbyMember
from app.repositories.base import BaseRepository


class LobbyRepository(BaseRepository[Lobby]):
    model = Lobby

    async def get_by_code(self, code: str) -> Lobby | None:
        result = await self.session.execute(
            select(Lobby)
            .where(Lobby.code == code)
            .options(selectinload(Lobby.members).selectinload(LobbyMember.user))
        )
        return result.scalar_one_or_none()

    async def get_full(self, lobby_id: int) -> Lobby | None:
        result = await self.session.execute(
            select(Lobby)
            .where(Lobby.id == lobby_id)
            .options(selectinload(Lobby.members).selectinload(LobbyMember.user))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        code: str,
        name: str | None,
        mode: BattleMode,
        host_id: int,
        stake: int,
        max_players: int,
        min_players: int,
        is_private: bool,
        password_hash: str | None,
        chat_id: int | None,
    ) -> Lobby:
        lobby = Lobby(
            code=code,
            name=name,
            mode=mode,
            host_id=host_id,
            stake=stake,
            max_players=max_players,
            min_players=min_players,
            is_private=is_private,
            password_hash=password_hash,
            chat_id=chat_id,
        )
        self.session.add(lobby)
        await self.session.flush()
        return lobby

    async def add_member(
        self, lobby_id: int, user_id: int, *, team: int | None = None
    ) -> LobbyMember:
        member = LobbyMember(lobby_id=lobby_id, user_id=user_id, team=team)
        self.session.add(member)
        await self.session.flush()
        return member

    async def list_public_open(
        self, *, limit: int = 20, mode: BattleMode | None = None
    ) -> list[Lobby]:
        stmt = (
            select(Lobby)
            .where(Lobby.status == LobbyStatus.OPEN, Lobby.is_private.is_(False))
            .options(selectinload(Lobby.members))
            .order_by(Lobby.created_at.desc())
            .limit(limit)
        )
        if mode is not None:
            stmt = stmt.where(Lobby.mode == mode)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_match(self, *, mode: BattleMode, stake: int) -> Lobby | None:
        """Auto-matchmaking: find an open, non-full public lobby to join."""
        result = await self.session.execute(
            select(Lobby)
            .where(
                Lobby.status == LobbyStatus.OPEN,
                Lobby.is_private.is_(False),
                Lobby.mode == mode,
                Lobby.stake == stake,
            )
            .options(selectinload(Lobby.members))
            .order_by(Lobby.created_at)
            .with_for_update(skip_locked=True)
            .limit(5)
        )
        for lobby in result.scalars().all():
            if not lobby.is_full:
                return lobby
        return None
