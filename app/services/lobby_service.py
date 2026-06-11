"""Lobby & matchmaking service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.config.constants import BattleMode, LobbyStatus
from app.models.battle import Battle
from app.models.lobby import Lobby
from app.models.user import User
from app.repositories.lobby_repository import LobbyRepository
from app.services.anticheat_service import AntiCheatService
from app.services.base import BaseService
from app.services.battle_service import BattleService
from app.utils.codes import generate_code
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.security import hash_password, verify_password

LOBBY_TTL = timedelta(minutes=30)


class LobbyService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.repo = LobbyRepository(session)
        self.anticheat = AntiCheatService(session, redis)

    async def create_lobby(
        self,
        *,
        host: User,
        mode: BattleMode = BattleMode.DUEL,
        stake: int = 0,
        max_players: int = 2,
        is_private: bool = False,
        password: str | None = None,
        name: str | None = None,
        chat_id: int | None = None,
    ) -> Lobby:
        self.anticheat.ensure_not_banned(host)
        if stake:
            self.anticheat.validate_bet(stake)
        if max_players < 2:
            raise ValidationError("A lobby needs at least 2 players.")

        code = generate_code(6)
        # Ensure uniqueness (codes are short; retry on the rare collision).
        for _ in range(5):
            if await self.repo.get_by_code(code) is None:
                break
            code = generate_code(6)

        password_hash = hash_password(password) if (is_private and password) else None
        lobby = await self.repo.create(
            code=code,
            name=name,
            mode=mode,
            host_id=host.id,
            stake=stake,
            max_players=max_players,
            min_players=2,
            is_private=is_private,
            password_hash=password_hash,
            chat_id=chat_id,
        )
        await self.repo.add_member(lobby.id, host.id)
        lobby.expires_at = datetime.now(UTC) + LOBBY_TTL
        await self.session.flush()
        return lobby

    async def join_lobby(self, *, user: User, code: str, password: str | None = None) -> Lobby:
        self.anticheat.ensure_not_banned(user)
        lobby = await self.repo.get_by_code(code.upper())
        if lobby is None:
            raise NotFoundError("No lobby found with that code.")
        if lobby.status != LobbyStatus.OPEN:
            raise ValidationError("This lobby is no longer open.")
        if lobby.is_full:
            raise ValidationError("This lobby is full.")
        if any(m.user_id == user.id for m in lobby.members):
            raise ValidationError("You are already in this lobby.")
        if (
            lobby.is_private
            and lobby.password_hash
            and (not password or not verify_password(password, lobby.password_hash))
        ):
            raise ValidationError("Incorrect lobby password.")

        await self.repo.add_member(lobby.id, user.id)
        # Refresh members so is_full reflects the new join.
        lobby = await self.repo.get_full(lobby.id)
        assert lobby is not None
        if lobby.is_full:
            await self.session.execute(
                update(Lobby).where(Lobby.id == lobby.id).values(status=LobbyStatus.FULL)
            )
            lobby.status = LobbyStatus.FULL
        return lobby

    async def auto_match(
        self, *, user: User, mode: BattleMode = BattleMode.PUBLIC, stake: int = 0
    ) -> Lobby:
        """Join an open public lobby matching mode+stake, or create a new one."""
        self.anticheat.ensure_not_banned(user)
        if stake:
            self.anticheat.validate_bet(stake)
        match = await self.repo.find_match(mode=mode, stake=stake)
        if match is not None:
            return await self.join_lobby(user=user, code=match.code)
        return await self.create_lobby(host=user, mode=mode, stake=stake, max_players=2)

    async def start_lobby(self, *, lobby: Lobby) -> Battle:
        """Convert a ready lobby into a battle, enrol all members, and return it.

        The caller resolves the battle (e.g. via ``BattleService.auto_resolve``).
        """
        if len(lobby.members) < lobby.min_players:
            raise ValidationError("Not enough players to start.")
        host = next((m.user for m in lobby.members if m.user_id == lobby.host_id), None)
        if host is None:
            raise ValidationError("Lobby host is missing.")

        battle_service = BattleService(self.session, self.redis)
        battle = await battle_service.create_battle(
            host=host,
            mode=lobby.mode,
            stake=lobby.stake,
            chat_id=lobby.chat_id,
            max_players=lobby.max_players,
        )
        for member in lobby.members:
            if member.user_id == lobby.host_id:
                continue
            await battle_service.join_battle(user=member.user, battle=battle)

        await self.session.execute(
            update(Lobby)
            .where(Lobby.id == lobby.id)
            .values(status=LobbyStatus.IN_PROGRESS, battle_id=battle.id)
        )
        return battle

    async def list_public(self, *, mode: BattleMode | None = None) -> list[Lobby]:
        return await self.repo.list_public_open(mode=mode)
