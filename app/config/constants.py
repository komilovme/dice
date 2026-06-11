"""Game-balancing constants and static catalogues.

Keeping all tunable game data in one place makes economy balancing and game
design changes easy to reason about and review.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Rank(enum.StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    MASTER = "master"
    GRANDMASTER = "grandmaster"


class BattleMode(enum.StrEnum):
    DUEL = "duel"  # 1v1
    FRIEND = "friend"  # friend challenge
    PUBLIC = "public"  # public open battle
    GROUP = "group"  # in-group battle
    TEAM = "team"  # team vs team
    ROYALE = "royale"  # battle royale (many players)
    JACKPOT = "jackpot"  # pooled jackpot
    TOURNAMENT = "tournament"  # bracketed tournament


class BattleStatus(enum.StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    ROLLING = "rolling"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class LobbyStatus(enum.StrEnum):
    OPEN = "open"
    FULL = "full"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class TransactionType(enum.StrEnum):
    SIGNUP_BONUS = "signup_bonus"
    DAILY_REWARD = "daily_reward"
    WEEKLY_REWARD = "weekly_reward"
    REFERRAL_REWARD = "referral_reward"
    ACHIEVEMENT_REWARD = "achievement_reward"
    CHEST_REWARD = "chest_reward"
    CASE_OPEN = "case_open"
    CASE_REWARD = "case_reward"
    BATTLE_STAKE = "battle_stake"
    BATTLE_WIN = "battle_win"
    BATTLE_REFUND = "battle_refund"
    POWERUP_PURCHASE = "powerup_purchase"
    CLAN_DONATION = "clan_donation"
    CLAN_WITHDRAW = "clan_withdraw"
    SEASON_REWARD = "season_reward"
    ADMIN_GRANT = "admin_grant"
    ADMIN_REMOVE = "admin_remove"
    HOUSE_EDGE = "house_edge"


class CaseRarity(enum.StrEnum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class RewardKind(enum.StrEnum):
    COINS = "coins"
    TITLE = "title"
    FRAME = "frame"
    BADGE = "badge"
    BOOSTER = "booster"


class PowerupType(enum.StrEnum):
    LUCKY_ROLL = "lucky_roll"  # reroll the lower of two dice once
    DOUBLE_REWARD = "double_reward"  # double winnings on next win
    INSURANCE = "insurance"  # refund stake on a loss
    STREAK_PROTECTION = "streak_protection"  # a loss does not break the streak
    XP_BOOSTER = "xp_booster"  # +100% XP for a duration


class ClanRole(enum.StrEnum):
    LEADER = "leader"
    CO_LEADER = "co_leader"
    ELDER = "elder"
    MEMBER = "member"


# ---------------------------------------------------------------------------
# Rank progression
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RankTier:
    rank: Rank
    min_xp: int
    min_wins: int
    icon: str


# Ordered from lowest to highest. Promotion uses XP as the primary driver with
# a wins gate so that pure grinding without playing cannot skip tiers.
RANK_TIERS: tuple[RankTier, ...] = (
    RankTier(Rank.BRONZE, min_xp=0, min_wins=0, icon="🥉"),
    RankTier(Rank.SILVER, min_xp=1_000, min_wins=10, icon="🥈"),
    RankTier(Rank.GOLD, min_xp=5_000, min_wins=50, icon="🥇"),
    RankTier(Rank.PLATINUM, min_xp=15_000, min_wins=150, icon="💠"),
    RankTier(Rank.DIAMOND, min_xp=40_000, min_wins=400, icon="💎"),
    RankTier(Rank.MASTER, min_xp=100_000, min_wins=1_000, icon="🔱"),
    RankTier(Rank.GRANDMASTER, min_xp=250_000, min_wins=2_500, icon="👑"),
)

# XP gained per game outcome.
XP_PER_WIN = 50
XP_PER_LOSS = 15
XP_PER_DRAW = 25
# Bonus XP for a win scales gently with the size of the pot.
XP_POT_DIVISOR = 100


# ---------------------------------------------------------------------------
# Lucky chest (free periodic reward, distinct from paid cases)
# ---------------------------------------------------------------------------
LUCKY_CHEST_COOLDOWN_HOURS = 6
LUCKY_CHEST_REWARDS: tuple[tuple[int, float], ...] = (
    # (coins, weight)
    (50, 40.0),
    (150, 30.0),
    (400, 18.0),
    (1_000, 9.0),
    (5_000, 3.0),
)


# ---------------------------------------------------------------------------
# Cases / loot boxes
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CaseReward:
    kind: RewardKind
    weight: float
    coins: int = 0
    item_code: str | None = None
    label: str = ""


@dataclass(frozen=True, slots=True)
class CaseDefinition:
    code: str
    name: str
    rarity: CaseRarity
    price: int
    rewards: tuple[CaseReward, ...]


CASES: dict[str, CaseDefinition] = {
    "common": CaseDefinition(
        code="common",
        name="Common Case",
        rarity=CaseRarity.COMMON,
        price=500,
        rewards=(
            CaseReward(RewardKind.COINS, weight=60, coins=300, label="300 Coins"),
            CaseReward(RewardKind.COINS, weight=25, coins=700, label="700 Coins"),
            CaseReward(RewardKind.BADGE, weight=10, item_code="badge_common", label="Common Badge"),
            CaseReward(RewardKind.BOOSTER, weight=5, item_code="xp_booster", label="XP Booster"),
        ),
    ),
    "rare": CaseDefinition(
        code="rare",
        name="Rare Case",
        rarity=CaseRarity.RARE,
        price=1_500,
        rewards=(
            CaseReward(RewardKind.COINS, weight=50, coins=1_200, label="1,200 Coins"),
            CaseReward(RewardKind.COINS, weight=25, coins=2_500, label="2,500 Coins"),
            CaseReward(RewardKind.FRAME, weight=15, item_code="frame_rare", label="Rare Frame"),
            CaseReward(
                RewardKind.BOOSTER, weight=7, item_code="double_reward", label="Double Reward"
            ),
            CaseReward(RewardKind.TITLE, weight=3, item_code="title_lucky", label="Title: Lucky"),
        ),
    ),
    "epic": CaseDefinition(
        code="epic",
        name="Epic Case",
        rarity=CaseRarity.EPIC,
        price=5_000,
        rewards=(
            CaseReward(RewardKind.COINS, weight=45, coins=4_000, label="4,000 Coins"),
            CaseReward(RewardKind.COINS, weight=20, coins=9_000, label="9,000 Coins"),
            CaseReward(RewardKind.FRAME, weight=18, item_code="frame_epic", label="Epic Frame"),
            CaseReward(
                RewardKind.TITLE,
                weight=12,
                item_code="title_highroller",
                label="Title: High Roller",
            ),
            CaseReward(RewardKind.BOOSTER, weight=5, item_code="lucky_roll", label="Lucky Roll x3"),
        ),
    ),
    "legendary": CaseDefinition(
        code="legendary",
        name="Legendary Case",
        rarity=CaseRarity.LEGENDARY,
        price=20_000,
        rewards=(
            CaseReward(RewardKind.COINS, weight=40, coins=18_000, label="18,000 Coins"),
            CaseReward(RewardKind.COINS, weight=18, coins=40_000, label="40,000 Coins"),
            CaseReward(
                RewardKind.FRAME, weight=20, item_code="frame_legendary", label="Legendary Frame"
            ),
            CaseReward(
                RewardKind.TITLE, weight=15, item_code="title_legend", label="Title: Legend"
            ),
            CaseReward(
                RewardKind.BADGE, weight=7, item_code="badge_legendary", label="Legendary Badge"
            ),
        ),
    ),
}


# ---------------------------------------------------------------------------
# Powerups catalogue
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PowerupDefinition:
    type: PowerupType
    name: str
    description: str
    price: int
    duration_seconds: int = 0  # 0 == single use / not time-based
    icon: str = "✨"


POWERUPS: dict[PowerupType, PowerupDefinition] = {
    PowerupType.LUCKY_ROLL: PowerupDefinition(
        PowerupType.LUCKY_ROLL,
        "Lucky Roll",
        "Reroll your dice once if you are losing.",
        price=800,
        icon="🍀",
    ),
    PowerupType.DOUBLE_REWARD: PowerupDefinition(
        PowerupType.DOUBLE_REWARD,
        "Double Reward",
        "Double the coins from your next win.",
        price=1_200,
        icon="💰",
    ),
    PowerupType.INSURANCE: PowerupDefinition(
        PowerupType.INSURANCE,
        "Insurance",
        "Refund your stake if you lose the next battle.",
        price=1_000,
        icon="🛡",
    ),
    PowerupType.STREAK_PROTECTION: PowerupDefinition(
        PowerupType.STREAK_PROTECTION,
        "Streak Protection",
        "A loss will not reset your win streak.",
        price=1_500,
        icon="🔥",
    ),
    PowerupType.XP_BOOSTER: PowerupDefinition(
        PowerupType.XP_BOOSTER,
        "XP Booster",
        "+100% experience for 1 hour.",
        price=900,
        duration_seconds=3600,
        icon="⚡",
    ),
}


# ---------------------------------------------------------------------------
# Achievements catalogue
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    code: str
    name: str
    description: str
    reward_coins: int
    icon: str = "🏅"
    # metric + threshold used by the achievement service to auto-evaluate.
    metric: str = ""  # e.g. "wins", "coins_earned", "best_streak"
    threshold: int = 0


ACHIEVEMENTS: dict[str, AchievementDefinition] = {
    "first_win": AchievementDefinition(
        "first_win",
        "First Win",
        "Win your very first battle.",
        reward_coins=200,
        icon="🌟",
        metric="wins",
        threshold=1,
    ),
    "wins_10": AchievementDefinition(
        "wins_10",
        "10 Wins",
        "Win 10 battles.",
        reward_coins=500,
        icon="✅",
        metric="wins",
        threshold=10,
    ),
    "wins_100": AchievementDefinition(
        "wins_100",
        "100 Wins",
        "Win 100 battles.",
        reward_coins=2_500,
        icon="💪",
        metric="wins",
        threshold=100,
    ),
    "wins_1000": AchievementDefinition(
        "wins_1000",
        "1000 Wins",
        "Win 1000 battles.",
        reward_coins=25_000,
        icon="🏆",
        metric="wins",
        threshold=1_000,
    ),
    "coins_1000": AchievementDefinition(
        "coins_1000",
        "1000 Coins Earned",
        "Earn 1,000 coins in total.",
        reward_coins=300,
        icon="🪙",
        metric="coins_earned",
        threshold=1_000,
    ),
    "coins_1m": AchievementDefinition(
        "coins_1m",
        "Millionaire",
        "Earn 1,000,000 coins in total.",
        reward_coins=50_000,
        icon="💎",
        metric="coins_earned",
        threshold=1_000_000,
    ),
    "streak_10": AchievementDefinition(
        "streak_10",
        "Win Streak 10",
        "Win 10 battles in a row.",
        reward_coins=3_000,
        icon="🔥",
        metric="best_streak",
        threshold=10,
    ),
    "tournament_champion": AchievementDefinition(
        "tournament_champion",
        "Tournament Champion",
        "Win a tournament.",
        reward_coins=10_000,
        icon="👑",
        metric="tournaments_won",
        threshold=1,
    ),
}


# ---------------------------------------------------------------------------
# AI announcer phrase banks
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AnnouncerBanks:
    close_win: tuple[str, ...] = field(
        default_factory=lambda: (
            "😱 What a nail-biter!",
            "🫣 Decided by a single pip!",
            "⚔️ Too close to call... almost!",
        )
    )
    blowout: tuple[str, ...] = field(
        default_factory=lambda: (
            "🤯 Absolute domination!",
            "💥 That was a massacre!",
            "🚀 Not even close!",
        )
    )
    high_roll: tuple[str, ...] = field(
        default_factory=lambda: (
            "🔥 Amazing roll!",
            "🎯 Perfect throw!",
            "✨ The dice gods are pleased!",
        )
    )
    comeback: tuple[str, ...] = field(
        default_factory=lambda: (
            "😱 Unexpected comeback!",
            "🔄 From the ashes!",
            "🙃 Nobody saw that coming!",
        )
    )
    streak: tuple[str, ...] = field(
        default_factory=lambda: (
            "👑 New streak leader!",
            "🔥 On fire — unstoppable!",
            "🏆 Another one for the win column!",
        )
    )
    legendary: tuple[str, ...] = field(
        default_factory=lambda: (
            "🤯 Legendary win!",
            "🌟 One for the history books!",
            "💫 Truly legendary!",
        )
    )


ANNOUNCER = AnnouncerBanks()
