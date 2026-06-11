"""Services layer: business logic orchestrating repositories and Redis.

Each service takes the request-scoped ``AsyncSession`` (and optional Redis) so
all repository operations within a handler share one transaction.
"""

from app.services.achievement_service import AchievementService
from app.services.admin_service import AdminService
from app.services.announcer_service import AnnouncerContext, AnnouncerService
from app.services.anticheat_service import AntiCheatService
from app.services.battle_service import BattleService, DiceRollOutcome
from app.services.case_service import CaseService
from app.services.clan_service import ClanService
from app.services.economy_service import EconomyService
from app.services.leaderboard_service import LeaderboardService
from app.services.lobby_service import LobbyService
from app.services.powerup_service import PowerupService
from app.services.ranking_service import RankingService
from app.services.season_service import SeasonService
from app.services.user_service import UserService

__all__ = [
    "AchievementService",
    "AdminService",
    "AnnouncerContext",
    "AnnouncerService",
    "AntiCheatService",
    "BattleService",
    "DiceRollOutcome",
    "CaseService",
    "ClanService",
    "EconomyService",
    "LeaderboardService",
    "LobbyService",
    "PowerupService",
    "RankingService",
    "SeasonService",
    "UserService",
]
