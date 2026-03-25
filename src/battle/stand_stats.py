"""
battle/stand_stats.py
Base stats and movesets for every stand.
Add new stands here — the rest of the system picks them up automatically.
"""

from src.battle.stand import Stand, StandStats, Move


# ── Helper ─────────────────────────────────────────────────────────────────────

def S(hp, atk, def_, spa, spd, rng) -> StandStats:
    return StandStats(hp=hp, atk=atk, def_=def_, spa=spa, spd=spd, rng=rng)

def M(name, category, power, accuracy, pp, effect="") -> Move:
    return Move(name=name, category=category, power=power,
                accuracy=accuracy, pp=pp, effect=effect)


# ── Base stats lookup (used by power score without full instantiation) ──────────

STAND_BASE_STATS: dict[str, StandStats] = {}


# ── Factory ────────────────────────────────────────────────────────────────────

import copy as _copy
from dataclasses import asdict as _asdict

def make_stand(name: str, level: int = 1, stars: int = 1, is_shiny: bool = False, secondary_stand_name: str = "") -> Stand:
    """Instantiate a Stand by name with given level/stars/shiny."""
    data = STAND_CATALOG.get(name)
    if not data:
        raise ValueError(f"Unknown stand: {name}")

    # Always deep-copy moves so PP resets fresh every battle.
    # Catalog stores Move objects; we convert back to dict and reconstruct
    # so each battle gets its own independent Move instances.
    fresh_moves = []
    for m in data["moves"]:
        if isinstance(m, dict):
            fresh_moves.append(Move(**m))
        else:
            # m is a Move dataclass — reconstruct from its fields
            fresh_moves.append(Move(
                name     = m.name,
                category = m.category,
                power    = m.power,
                accuracy = m.accuracy,
                pp       = m.pp,
                effect   = m.effect,
            ))

    stand = Stand(
        name       = name,
        stand_type = data["type"],
        rarity     = data["rarity"],
        part       = data["part"],
        base_stats = data["stats"],
        moves      = fresh_moves,
        gimmick    = data.get("gimmick"),
        level      = level,
        stars      = stars,
        is_shiny   = is_shiny,
        secondary_stand_name = secondary_stand_name,
    )
    return stand


# ══════════════════════════════════════════════════════════════════════════════
# STAND CATALOG
# Format: name → {type, rarity, part, stats, moves (list of 4), gimmick}
# Moves list order: [move1, move2, move3_lvl15, move4_lvl30]
# ══════════════════════════════════════════════════════════════════════════════

STAND_CATALOG: dict[str, dict] = {

    # ── PART 3 ────────────────────────────────────────────────────────────────

    "Star Platinum": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   3,
        "stats":  S(hp=87, atk=118, def_=73, spa=64, spd=101, rng=37),
        "gimmick": "precision_strike",
        "moves": [
            M("ORA Barrage",  "Physical", 80,  0.95, 8,  "hit_3_times"),
            M("Star Finger",      "Physical", 60,  1.00, 10, ""),
            M("Precision Strike", "Physical", 100, 0.85, 5,  "high_crit"),
            M("Star Platinum, The World!",  "Physical", 120, 0.80, 3,  ""),
        ],
    },

    "The World": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   3,
        "stats":  S(hp=94, atk=118, def_=80, spa=56, spd=94, rng=38),
        "gimmick": "time_stop",
        "moves": [
            M("MUDA Barrage", "Physical", 80,  0.95, 8,  "hit_3_times"),
            M("Knife Volley",      "Physical", 70,  0.90, 8,  "multi_hit"),
            M("Road Roller",       "Physical", 110, 0.80, 5,  ""),
            M("ZA WARUDO",  "Physical", 130, 0.75, 3,  "ignores_dodge"),
        ],
    },

    "Hermit Purple": {
        "type":   "Ability",
        "rarity": "Common",
        "part":   3,
        "stats":  S(hp=67, atk=41, def_=57, spa=94, spd=73, rng=88),
        "gimmick": "foresight",
        "moves": [
            M("Thorn Whip",      "Physical", 50, 1.00, 12, ""),
            M("Spirit Photo",    "Special",  60, 0.85, 8,  "reveals_info"),
            M("Vine Snare",      "Status",   0,  0.90, 5,  "lower_spd"),
            M("Psychic Lash",    "Special",  85, 0.80, 5,  ""),
        ],
    },

    "Magician's Red": {
        "type":   "Long-Distance",
        "rarity": "Rare",
        "part":   3,
        "stats":  S(hp=68, atk=77, def_=59, spa=90, spd=64, rng=82),
        "gimmick": None,
        "moves": [
            M("Red Bind",        "Special",  60, 0.95, 10, "burn"),
            M("Crossfire Hurricane", "Special", 80, 0.90, 8, ""),
            M("Ankh Inferno",    "Special",  100, 0.80, 5, "aoe_burn"),
            M("Flame Barrier",   "Status",   0,   1.00, 5, "burn_reflect"),
        ],
    },

    "Silver Chariot": {
        "type":   "Close-Range",
        "rarity": "Rare",
        "part":   3,
        "stats":  S(hp=66, atk=95, def_=66, spa=52, spd=114, rng=47),
        "gimmick": None,
        "moves": [
            M("Rapier Thrust",   "Physical", 65,  1.00, 10, "multi_hit"),
            M("Armor Off",       "Status",   0,   1.00, 3,  "raise_spd_def"),
            M("Thousand Cuts",   "Physical", 90,  0.85, 6,  ""),
            M("Lightning Lunge", "Physical", 115, 0.80, 3,  ""),
        ],
    },

    "Osiris": {
        "type":   "Ability",
        "rarity": "Legendary",
        "part":   3,
        "stats":  S(hp=74, atk=58, def_=69, spa=115, spd=90, rng=74),
        "gimmick": None,
        "moves": [
            M("Soul Steal",      "Special",  70,  0.90, 8,  "drain_hp"),
            M("Gamble Curse",    "Status",   0,   0.85, 5,  "confusion"),
            M("Soul Dice",       "Special",  90,  0.80, 5,  "random_power"),
            M("Final Bet",       "Special",  130, 0.70, 2,  ""),
        ],
    },

    "Cream": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   3,
        "stats":  S(hp=81, atk=116, def_=91, spa=61, spd=91, rng=40),
        "gimmick": None,
        "moves": [
            M("Void Bite",       "Physical", 85,  0.90, 8,  ""),
            M("Dimensional Lunge","Physical", 100, 0.85, 5,  ""),
            M("Void Swallow",    "Status",   0,   1.00, 3,  "evade_next"),
            M("Erasure",         "Physical", 130, 0.75, 3,  ""),
        ],
    },

    "Anubis": {
        "type":   "Close-Range",
        "rarity": "Epic",
        "part":   3,
        "stats":  S(hp=75, atk=115, def_=62, spa=52, spd=109, rng=47),
        "gimmick": None,
        "moves": [
            M("Sword Slash",     "Physical", 70,  1.00, 10, ""),
            M("Counter Read",    "Status",   0,   1.00, 5,  "counter_next"),
            M("Adapt & Strike",  "Physical", 95,  0.90, 5,  "power_up_per_hit"),
            M("Perfect Memory",  "Physical", 120, 0.80, 3,  ""),
        ],
    },

    "Geb": {
        "type":   "Long-Distance",
        "rarity": "Epic",
        "part":   3,
        "stats":  S(hp=68, atk=73, def_=64, spa=91, spd=77, rng=87),
        "gimmick": None,
        "moves": [
            M("Water Hand",      "Special",  65,  0.95, 10, ""),
            M("Hydro Slash",     "Special",  80,  0.90, 8,  ""),
            M("Tidal Surge",     "Special",  100, 0.85, 5,  ""),
            M("Aqua Obliteration","Special", 120, 0.75, 3,  ""),
        ],
    },

    # ── PART 4 ────────────────────────────────────────────────────────────────

    "Crazy Diamond": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   4,
        "stats":  S(hp=88, atk=118, def_=83, spa=59, spd=93, rng=39),
        "gimmick": "restoration",
        "moves": [
            M("DORA Barrage",    "Physical", 80,  0.95, 8,  ""),
            M("Restore Strike",  "Physical", 70,  1.00, 8,  "self_heal_10"),
            M("Reconstruction",  "Status",   0,   1.00, 3,  "heal_30pct"),
            M("Diamond Crash",   "Physical", 120, 0.80, 3,  ""),
        ],
    },

    "Killer Queen": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   4,
        "stats":  S(hp=80, atk=103, def_=75, spa=85, spd=85, rng=52),
        "gimmick": "bomb_set",
        "moves": [
            M("Primary Bomb",    "Physical", 90,  0.90, 6,  "bomb_trigger"),
            M("Shrapnel",        "Physical", 70,  1.00, 8,  ""),
            M("Bites the Dust",  "Status",   0,   1.00, 1,  "bites_the_dust"),
            M("Air Bomb",        "Physical", 110, 0.85, 4,  ""),
        ],
    },

    "Echoes ACT1": {
        "type":   "Ability",
        "rarity": "Rare",
        "part":   4,
        "stats":  S(hp=65, atk=54, def_=60, spa=87, spd=93, rng=81),
        "gimmick": None,
        "moves": [
            M("Sound Effect",    "Special",  55,  0.95, 10, ""),
            M("SFX Imprint",     "Status",   0,   0.90, 5,  "lower_atk"),
            M("Echo Blast",      "Special",  75,  0.85, 6,  ""),
            M("Sizzle",          "Special",  90,  0.80, 4,  "burn"),
        ],
    },

    "Echoes ACT2": {
        "type":   "Ability",
        "rarity": "Epic",
        "part":   4,
        "stats":  S(hp=69, atk=61, def_=61, spa=97, spd=91, rng=81),
        "gimmick": None,
        "moves": [
            M("Sound Pressure",  "Special",  65,  0.95, 10, ""),
            M("ACT2 Imprint",    "Status",   0,   0.90, 5,  "lower_def"),
            M("Reverb",          "Special",  85,  0.85, 6,  ""),
            M("Sonic Boom",      "Special",  105, 0.80, 3,  ""),
        ],
    },

    "Echoes ACT3": {
        "type":   "Ability",
        "rarity": "Epic",
        "part":   4,
        "stats":  S(hp=69, atk=69, def_=60, spa=101, spd=87, rng=74),
        "gimmick": None,
        "moves": [
            M("3 Freeze",        "Special",  80,  0.90, 8,  "lower_spd"),
            M("ACT3 Loop",       "Special",  70,  1.00, 8,  ""),
            M("Gravity Press",   "Special",  100, 0.85, 5,  ""),
            M("Ultimate Freeze", "Special",  125, 0.75, 3,  ""),
        ],
    },

    "Harvest": {
        "type":   "Colony",
        "rarity": "Epic",
        "part":   4,
        "stats":  S(hp=66, atk=56, def_=61, spa=82, spd=103, rng=92),
        "gimmick": "scavenge",
        "moves": [
            M("Swarm Strike",    "Physical", 60,  0.95, 10, "multi_hit"),
            M("Harvest Drain",   "Special",  65,  0.90, 8,  "drain_hp"),
            M("Colony Crush",    "Physical", 85,  0.85, 5,  ""),
            M("Overwhelming Swarm","Physical",110, 0.80, 3, ""),
        ],
    },

    "Heaven's Door": {
        "type":   "Ability",
        "rarity": "Epic",
        "part":   4,
        "stats":  S(hp=72, atk=56, def_=66, spa=107, spd=82, rng=77),
        "gimmick": None,
        "moves": [
            M("Paper Slash",     "Physical", 55,  1.00, 10, ""),
            M("Read the Soul",   "Status",   0,   1.00, 3,  "reveal_moves"),
            M("Write Weakness",  "Status",   0,   0.90, 3,  "lower_all_stats"),
            M("Book Barrage",    "Special",  100, 0.80, 4,  ""),
        ],
    },

    "Bites the Dust": {
        "type":   "Automatic",
        "rarity": "Legendary",
        "part":   4,
        "stats":  S(hp=75, atk=95, def_=80, spa=94, spd=80, rng=56),
        "gimmick": "bomb_set",
        "moves": [
            M("Loop Bomb",       "Special",  90,  0.85, 6,  "bomb_trigger"),
            M("Time Loop",       "Status",   0,   1.00, 1,  "time_loop"),
            M("Explosive Secret","Physical", 100, 0.85, 5,  ""),
            M("Detonation",      "Special",  130, 0.75, 2,  ""),
        ],
    },

    # ── PART 5 ────────────────────────────────────────────────────────────────

    "Gold Experience": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   5,
        "stats":  S(hp=78, atk=92, def_=74, spa=102, spd=88, rng=46),
        "gimmick": "life_reflection",
        "moves": [
            M("Life Shot",       "Special",  75,  0.95, 8,  ""),
            M("Frog Barrage",    "Physical", 65,  1.00, 8,  "multi_hit"),
            M("Life Surge",      "Special",  95,  0.85, 5,  "heal_on_hit"),
            M("Animating Punch", "Physical", 120, 0.80, 3,  ""),
        ],
    },

    "Gold Experience Requiem": {
        "type":   "Close-Range",
        "rarity": "Mythical",
        "part":   5,
        "stats":  S(hp=80, atk=96, def_=76, spa=112, spd=88, rng=48),
        "gimmick": "life_reflection",
        "moves": [
            M("Return to Zero",  "Special",  130, 0.90, 4,  "nullify_effect"),
            M("Life Barrage",    "Physical", 90,  0.95, 6,  "multi_hit"),
            M("Infinite Death",  "Special",  150, 0.80, 2,  ""),
            M("Reality Reset",   "Status",   0,   1.00, 1,  "reset_enemy_buffs"),
        ],
    },

    "King Crimson": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   5,
        "stats":  S(hp=84, atk=116, def_=70, spa=65, spd=103, rng=42),
        "gimmick": None,
        "moves": [
            M("Epitaph Foresee", "Status",   0,   1.00, 3,  "dodge_next"),
            M("Chop",            "Physical", 90,  0.90, 8,  ""),
            M("Time Skip",       "Physical", 110, 0.85, 5,  "ignores_dodge"),
            M("Severing Blow",   "Physical", 130, 0.80, 3,  ""),
        ],
    },

    "Sex Pistols": {
        "type":   "Long-Distance",
        "rarity": "Epic",
        "part":   5,
        "stats":  S(hp=55, atk=64, def_=46, spa=83, spd=101, rng=111),
        "gimmick": None,
        "moves": [
            M("Bullet Redirect", "Special",  70,  1.00, 8,  ""),
            M("Six-Shot Burst",  "Physical", 60,  0.95, 8,  "multi_hit"),
            M("Ricochet",        "Special",  90,  0.90, 5,  "bypass_def"),
            M("Pistols Max",     "Physical", 110, 0.80, 3,  ""),
        ],
    },

    "Purple Haze": {
        "type":   "Close-Range",
        "rarity": "Epic",
        "part":   5,
        "stats":  S(hp=79, atk=119, def_=54, spa=109, spd=59, rng=40),
        "gimmick": None,
        "moves": [
            M("Virus Capsule",   "Special",  90,  0.85, 6,  "poison"),
            M("Frenzied Punch",  "Physical", 95,  0.85, 6,  ""),
            M("Plague Cloud",    "Special",  75,  1.00, 8,  "poison"),
            M("Viral Overdrive", "Special",  130, 0.70, 2,  ""),
        ],
    },

    "Sticky Fingers": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   5,
        "stats":  S(hp=86, atk=112, def_=76, spa=64, spd=98, rng=44),
        "gimmick": None,
        "moves": [
            M("Zipper Punch",    "Physical", 80,  1.00, 8,  ""),
            M("Dismember",       "Physical", 95,  0.90, 6,  "lower_atk"),
            M("Unzip",           "Status",   0,   1.00, 3,  "evade_next"),
            M("ARRIVEDERCI",     "Physical", 125, 0.80, 3,  ""),
        ],
    },

    # ── PART 7 ────────────────────────────────────────────────────────────────

    "Tusk ACT1": {
        "type":   "Close-Range",
        "rarity": "Rare",
        "part":   7,
        "stats":  S(hp=74, atk=80, def_=69, spa=63, spd=85, rng=69),
        "gimmick": None,
        "moves": [
            M("Nail Shot",       "Physical", 55,  0.95, 10, ""),
            M("Spin Shot",       "Physical", 65,  0.90, 8,  ""),
            M("Piercing Nail",   "Physical", 80,  0.85, 5,  ""),
            M("Spiral Energy",   "Physical", 95,  0.80, 4,  ""),
        ],
    },

    "Tusk ACT2": {
        "type":   "Close-Range",
        "rarity": "Epic",
        "part":   7,
        "stats":  S(hp=76, atk=91, def_=68, spa=68, spd=89, rng=68),
        "gimmick": None,
        "moves": [
            M("Golden Spin",     "Physical", 70,  0.95, 8,  ""),
            M("Wormhole Punch",  "Physical", 85,  0.85, 6,  ""),
            M("ACT2 Barrage",    "Physical", 90,  0.90, 5,  ""),
            M("Nail Vortex",     "Physical", 110, 0.80, 3,  ""),
        ],
    },

    "Tusk ACT3": {
        "type":   "Close-Range",
        "rarity": "Epic",
        "part":   7,
        "stats":  S(hp=75, atk=94, def_=67, spa=70, spd=89, rng=65),
        "gimmick": None,
        "moves": [
            M("ACT3 Spin",       "Physical", 85,  0.90, 6,  ""),
            M("Dimensional Nail","Physical", 100, 0.85, 5,  ""),
            M("Power Barrage",   "Physical", 95,  0.90, 5,  ""),
            M("Spiral Infinity", "Physical", 120, 0.80, 3,  ""),
        ],
    },

    "Tusk ACT4": {
        "type":   "Close-Range",
        "rarity": "Mythical",
        "part":   7,
        "stats":  S(hp=81, atk=111, def_=73, spa=81, spd=90, rng=64),
        "gimmick": None,
        "moves": [
            M("Love Train Piercer","Physical",120, 0.90, 5,  "ignores_dodge"),
            M("Infinite Rotation","Physical", 100, 1.00, 6,  "unstoppable"),
            M("ACT4 Barrage",    "Physical", 90,  0.95, 6,  "multi_hit"),
            M("Godlike Spin",    "Physical", 150, 0.80, 2,  ""),
        ],
    },

    "D4C": {
        "type":   "Close-Range",
        "rarity": "Mythical",
        "part":   7,
        "stats":  S(hp=87, atk=105, def_=83, spa=83, spd=92, rng=50),
        "gimmick": None,
        "moves": [
            M("Parallel Swap",   "Status",   0,   1.00, 2,  "dimension_swap"),
            M("D4C Punch",       "Physical", 95,  0.90, 6,  ""),
            M("Alternate Self",  "Physical", 110, 0.85, 4,  ""),
            M("Love Train",      "Status",   0,   1.00, 1,  "love_train_redirect"),
        ],
    },

    # ── PART 8 ────────────────────────────────────────────────────────────────

    "Soft & Wet": {
        "type":   "Close-Range",
        "rarity": "Legendary",
        "part":   8,
        "stats":  S(hp=79, atk=95, def_=72, spa=90, spd=90, rng=54),
        "gimmick": None,
        "moves": [
            M("Bubble Barrage",  "Physical", 75,  0.95, 8,  ""),
            M("Plunder Bubble",  "Special",  80,  0.90, 6,  "steal_buff"),
            M("Soap Trap",       "Status",   0,   0.90, 5,  "lower_def"),
            M("Void Bubble",     "Special",  120, 0.80, 3,  ""),
        ],
    },

}

# Populate STAND_BASE_STATS lookup from catalog
for _name, _data in STAND_CATALOG.items():
    STAND_BASE_STATS[_name] = _data["stats"]