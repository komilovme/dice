"""Repository layer: all data-access logic lives here.

Services depend on repositories, never on the ORM session directly for queries.
"""

from app.repositories.achievement_repository import AchievementRepository
from app.repositories.admin_repository import AdminLogRepository, AntiCheatRepository
from app.repositories.battle_repository import BattleRepository
from app.repositories.clan_repository import ClanRepository
from app.repositories.economy_repository import (
    RewardClaimRepository,
    TransactionRepository,
)
from app.repositories.inventory_repository import (
    CaseOpeningRepository,
    InventoryRepository,
    PowerupRepository,
)
from app.repositories.leaderboard_repository import (
    LeaderboardEntry,
    LeaderboardRepository,
)
from app.repositories.lobby_repository import LobbyRepository
from app.repositories.season_repository import SeasonRepository
from app.repositories.stats_repository import StatsRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "AchievementRepository",
    "AdminLogRepository",
    "AntiCheatRepository",
    "BattleRepository",
    "ClanRepository",
    "RewardClaimRepository",
    "TransactionRepository",
    "CaseOpeningRepository",
    "InventoryRepository",
    "PowerupRepository",
    "LeaderboardEntry",
    "LeaderboardRepository",
    "LobbyRepository",
    "SeasonRepository",
    "StatsRepository",
    "UserRepository",
]
