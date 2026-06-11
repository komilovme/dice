"""ORM models package.

Importing every model here ensures they are all registered on ``Base.metadata``
so Alembic autogenerate and ``create_all`` see the full schema.
"""

from app.database.base import Base
from app.models.admin import AdminLog, AntiCheatLog
from app.models.battle import Battle, BattleParticipant
from app.models.clan import Clan, ClanMember, ClanWar
from app.models.economy import RewardClaim, Transaction
from app.models.inventory import CaseOpening, InventoryItem, UserPowerup
from app.models.lobby import Lobby, LobbyMember
from app.models.season import HallOfFame, Season, SeasonParticipant
from app.models.user import User, UserStats
from app.models.user_achievement import UserAchievement

__all__ = [
    "Base",
    "User",
    "UserStats",
    "Transaction",
    "RewardClaim",
    "Battle",
    "BattleParticipant",
    "Lobby",
    "LobbyMember",
    "Clan",
    "ClanMember",
    "ClanWar",
    "UserAchievement",
    "InventoryItem",
    "UserPowerup",
    "CaseOpening",
    "Season",
    "SeasonParticipant",
    "HallOfFame",
    "AdminLog",
    "AntiCheatLog",
]
