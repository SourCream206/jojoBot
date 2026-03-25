"""
battle/stand.py
Stand dataclass, stat calculation, and power score.
"""

from dataclasses import dataclass, field
from typing import Optional
import math
from src.utils.constants import STAR_MULTIPLIERS, SHINY_MODIFIER


@dataclass
class Move:
    name:     str
    category: str          # 'Physical' | 'Special' | 'Status'
    power:    int          # 0 for Status moves
    accuracy: float        # 0.0 – 1.0
    pp:       int          # Uses per battle
    effect:   str = ""     # Description / special trigger key
    pp_remaining: int = field(init=False)

    def __post_init__(self):
        self.pp_remaining = self.pp


@dataclass
class StandStats:
    hp:  int
    atk: int
    def_: int   # 'def' is a Python keyword so we use def_
    spa: int
    spd: int
    rng: int


@dataclass
class Stand:
    # Identity
    name:       str
    stand_type: str          # Close-Range | Long-Distance | Automatic | Colony | Ability
    rarity:     str
    part:       int

    # Base stats (before level/star scaling)
    base_stats: StandStats

    # Moveset (2 to 4 moves)
    moves: list[Move]

    # Gimmick key (maps to gimmicks.py)
    gimmick: Optional[str] = None

    # Runtime state (set when instantiated for battle)
    level:   int  = 1
    stars:   int  = 1
    is_shiny: bool = False

    # Battle state (mutable during a fight)
    current_hp:      int   = field(init=False)
    gimmick_used:    bool  = False
    status:          Optional[str] = None   # 'burn' | 'bomb' | etc.

    def __post_init__(self):
        self.current_hp = self.max_hp

    # ── Stat calculations ─────────────────────────────────────────────────────

    def _scale(self, base: int) -> int:
        star_mult  = STAR_MULTIPLIERS[self.stars]
        shiny_mult = SHINY_MODIFIER if self.is_shiny else 1.0
        return int(base * (1 + self.level / 50) * star_mult * shiny_mult)

    @property
    def max_hp(self)  -> int: return self._scale(self.base_stats.hp)
    @property
    def atk(self)     -> int: return self._scale(self.base_stats.atk)
    @property
    def defense(self) -> int: return self._scale(self.base_stats.def_)
    @property
    def spa(self)     -> int: return self._scale(self.base_stats.spa)
    @property
    def spd(self)     -> int: return self._scale(self.base_stats.spd)
    @property
    def rng(self)     -> int: return self._scale(self.base_stats.rng)

    # ── Derived combat values ─────────────────────────────────────────────────

    @property
    def dodge_chance(self) -> float:
        THRESHOLD = 150
        if self.spd <= THRESHOLD:
            raw = self.spd / THRESHOLD * 0.30
        else:
            raw = 0.30 + (1 - math.exp(-(self.spd - THRESHOLD) / 100)) * 0.10
        return max(0.05, min(0.40, raw))

    @property
    def crit_chance(self) -> float:
        base = 0.10
        # Star Platinum gimmick adds +15%
        if self.gimmick == "precision_strike":
            base += 0.15
        return min(base, 0.50)

    @property
    def available_moves(self) -> list[Move]:
        """Moves unlocked at current level with PP remaining."""
        unlock_levels = [1, 1, 15, 30]
        return [
            m for i, m in enumerate(self.moves)
            if self.level >= unlock_levels[i] and m.pp_remaining > 0
        ]

    @property
    def damaging_moves(self) -> list[Move]:
        return [m for m in self.available_moves if m.category != "Status"]

    # ── Damage formula ────────────────────────────────────────────────────────

    def calc_damage(self, move: Move, target: "Stand", crit: bool = False, random_roll: float = 1.0) -> int:
        if move.category == "Status":
            return 0

        attacker_stat = self.atk if move.category == "Physical" else self.spa
        defender_stat = target.defense

        crit_mult = 1.5 if crit else 1.0

        damage = (
            (2 * self.level / 5 + 2)
            * move.power
            * (attacker_stat / defender_stat)
            / 50
            + 2
        ) * crit_mult * random_roll

        return max(1, int(damage))


# ── Power score (for leaderboard) ─────────────────────────────────────────────

def compute_power_score(stand_row: dict) -> int:
    """
    Lightweight power estimate from DB row (no full Stand instantiation needed).
    Used for leaderboard sorting.
    """
    from src.battle.stand_stats import STAND_BASE_STATS
    name   = stand_row["stand_name"]
    level  = stand_row.get("level", 1)
    stars  = stand_row.get("stars", 1)
    shiny  = stand_row.get("is_shiny", False)

    base = STAND_BASE_STATS.get(name)
    if not base:
        return 0

    mult  = STAR_MULTIPLIERS[stars] * (SHINY_MODIFIER if shiny else 1.0)
    scale = 1 + level / 50
    total = sum([base.hp, base.atk, base.def_, base.spa, base.spd, base.rng])
    return int(total * scale * mult)
