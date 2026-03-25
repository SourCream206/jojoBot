"""
utils/constants.py
All static game data: areas, items, rarity weights, stand pools, daily rewards.
"""

# ────────────────────────────────────────────────────────────
# RARITY
# ────────────────────────────────────────────────────────────

RARITY_WEIGHTS_STANDARD = {
    "Common":    0.50,
    "Rare":      0.30,
    "Epic":      0.15,
    "Legendary": 0.05,
    "Mythical":  0.00,  # Event only
}

RARITY_WEIGHTS_PREMIUM = {
    "Common":    0.30,
    "Rare":      0.30,
    "Epic":      0.25,
    "Legendary": 0.15,
    "Mythical":  0.00,
}

PITY_LEGENDARY_THRESHOLD = 50
PITY_MYTHICAL_THRESHOLD  = 5000

STAR_MULTIPLIERS = {1: 1.0, 2: 1.1, 3: 1.25, 4: 1.45, 5: 1.70}

SHINY_RATE     = 0.01   # 1% chance on any roll
SHINY_MODIFIER = 1.05   # +5% all stats


# ────────────────────────────────────────────────────────────
# AREAS
# Unlock order: Cairo → Egypt → Morioh → Italy → Philadelphia → Morioh SBR
# Cairo is available from the start; all others require level + quest.
# ────────────────────────────────────────────────────────────

AREA_ORDER = [
    "Cairo",
    "Morioh Town",
    "Italy",
    "Philadelphia",
    "Morioh SBR",
]

# Level thresholds to unlock each area (story quest completion also required)
AREA_LEVEL_REQUIREMENTS = {
    "Cairo":        0,    # Starting area, always unlocked
    "Morioh Town":  10,   # Tune during balancing
    "Italy":        20,
    "Philadelphia": 30,
    "Morioh SBR":   40,
}

# Story quest that must be completed to unlock each area
AREA_QUEST_REQUIREMENTS = {
    "Cairo":        None,
    "Morioh Town":  "quest_cairo_final",
    "Italy":        "quest_morioh_final",
    "Philadelphia": "quest_italy_final",
    "Morioh SBR":   "quest_philly_final",
}

TRAVEL_COST = 50  # Coins


# ────────────────────────────────────────────────────────────
# STAND POOLS PER AREA
# Each stand entry: { name, rarity, type, stand_type }
# "special_unlock" = True means it only enters the pool via
# player_unlocked_stands (Corpse Parts etc.)
# ────────────────────────────────────────────────────────────

# ── Build STAND_POOLS dynamically from stands.json ───────────────────────────
# Rarities, rollability, and stand names all come from stands.json.
# We only define here which part numbers map to which area, and any
# special_unlock overrides (Corpse Parts).

import json as _json
import os as _os

def _load_stands_json() -> dict:
    path = _os.path.normpath(
        _os.path.join(_os.path.dirname(__file__), "..", "..", "stands.json")
    )
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _json.load(f)
    except FileNotFoundError:
        return {}

_STANDS_RAW = _load_stands_json()

# Part number → area name
_PART_TO_AREA = {
    3: "Cairo",
    4: "Morioh Town",
    5: "Italy",
    6: "Italy",       # Part 6 stands go into Italy pool
    7: "Philadelphia",
    8: "Morioh SBR",
}

# Stands that only enter the pool via special unlock (Corpse Parts etc.)
_SPECIAL_UNLOCKS = {
    "D4C":       {"rarity": "Mythical", "part": 7, "special_unlock": True},
    "Tusk ACT4": {"rarity": "Mythical", "part": 7, "special_unlock": True},
}

# ── Name aliases: maps stands.json names → canonical game names ──────────────
# Use this when stands.json uses a different name than what the rest of the
# codebase (evolution tables, battle catalog) expects.
_NAME_ALIASES = {
    "Echoes Act1":                "Echoes ACT1",
    "Echoes Act2":                "Echoes ACT2",
    "Echoes Act3":                "Echoes ACT3",
    "Killer Queen: Bites the Dust": "Bites the Dust",
    "Mr.President":               "Mr. President",
    "Super Fly":                  "Superfly",
    "Shadow Dio":                 "The World",   # Shadow DIO uses The World — skip duplicate
}

# Stands to exclude entirely from the roll pool regardless of rollable flag
_POOL_EXCLUDE = {
    "Shadow Dio",           # duplicate of The World
    "Gold Experience Requiem",   # evolution result, not rollable
    "Silver Chariot Requiem",    # evolution result, not rollable
    "Shenron Platinum",     # fan/placeholder
    "Goro Zeppeli",         # fan/placeholder
    "The Duck",             # fan/placeholder
    "Star Platinum: Act 2", # fan/placeholder
}

def _build_pools() -> dict:
    pools: dict[str, list] = {area: [] for area in _PART_TO_AREA.values()}
    seen: set[str] = set()

    for part_key, stands in _STANDS_RAW.items():
        try:
            part_num = int(part_key.split()[-1])
        except (ValueError, IndexError):
            continue
        area = _PART_TO_AREA.get(part_num)
        if not area:
            continue

        for raw_name, data in stands.items():
            if raw_name in _POOL_EXCLUDE:
                continue
            if not data.get("rollable", True):
                continue

            # Apply alias
            stand_name = _NAME_ALIASES.get(raw_name, raw_name)

            if stand_name in seen:
                continue
            if stand_name in _SPECIAL_UNLOCKS:
                continue

            rarity = data.get("rarity", "Common")
            pools[area].append({"name": stand_name, "rarity": rarity, "part": part_num})
            seen.add(stand_name)

    # Add special unlocks to their area but flagged
    for stand_name, meta in _SPECIAL_UNLOCKS.items():
        area = _PART_TO_AREA.get(meta["part"])
        if area:
            pools[area].append({**meta, "name": stand_name})

    return pools

STAND_POOLS = _build_pools()

# Flat lookup: stand name → stand data + area
ALL_STANDS = {
    stand["name"]: {**stand, "area": area}
    for area, pool in STAND_POOLS.items()
    for stand in pool
}


# ────────────────────────────────────────────────────────────
# ACT EVOLUTIONS
# ────────────────────────────────────────────────────────────

ACT_EVOLUTIONS = {
    "Echoes ACT1": {"required_level": 15, "evolves_to": "Echoes ACT2"},
    "Echoes ACT2": {"required_level": 25, "evolves_to": "Echoes ACT3"},
    "Tusk ACT1":   {"required_level": 10, "evolves_to": "Tusk ACT2"},
    "Tusk ACT2":   {"required_level": 20, "evolves_to": "Tusk ACT3"},
    "Tusk ACT3":   {"required_level": 35, "evolves_to": "Tusk ACT4"},
}

REQUIEM_EVOLUTIONS = {
    "Gold Experience":  {"required_level": 40, "evolves_to": "Gold Experience Requiem"},
    "Silver Chariot":   {"required_level": 40, "evolves_to": "Silver Chariot Requiem"},
}


# ────────────────────────────────────────────────────────────
# SAINT'S CORPSE PARTS
# ────────────────────────────────────────────────────────────

CORPSE_PARTS = {
    "left_arm":  {"unlocks_stand": "Tusk ACT1", "guaranteed": True},
    "heart":     {"unlocks_stand": "D4C",        "guaranteed": True},
    "right_arm": {"unlocks_stand": None,          "guaranteed": False},  # Passive lore only for now
    "eyes":      {"unlocks_stand": None,          "guaranteed": False},
    "spine":     {"unlocks_stand": None,          "guaranteed": False},
    "rib_cage":  {"unlocks_stand": None,          "guaranteed": False},
    "ears":      {"unlocks_stand": None,          "guaranteed": False},
    "legs":      {"unlocks_stand": None,          "guaranteed": False},
    "skull":     {"unlocks_stand": None,          "guaranteed": False},
}

CORPSE_PART_DROP_RATE = 0.15   # 15% chance per non-guaranteed part per boss kill


# ────────────────────────────────────────────────────────────
# ITEMS
# ────────────────────────────────────────────────────────────

ITEMS = {
    "xpPotion": {
        "name": "XP Potion",
        "description": "Instantly grants your stand 1 level.",
        "emoji": "🧪",
        "usable": True,
    },
    "actStone": {
        "name": "Act Stone",
        "description": "Triggers an Act evolution when your stand reaches the required level.",
        "emoji": "💠",
        "usable": True,
    },
    "requiemArrow": {
        "name": "Requiem Arrow",
        "description": "Evolves an eligible stand into its Requiem form at level 40+.",
        "emoji": "🏹",
        "usable": True,
    },
    "healingItem": {
        "name": "Healing Bandage",
        "description": "Restores 30% of your stand's max HP during battle.",
        "emoji": "🩹",
        "usable": True,
        "battle_only": True,
        "heal_percent": 0.30,
    },
    "mythicalTicket": {
        "name": "Mythical Ticket",
        "description": "Guarantees a Mythical stand on your next roll.",
        "emoji": "🎟️",
        "usable": True,
    },
    "epicRoll": {
        "name": "Epic Roll",
        "description": "Guaranteed Epic or higher stand roll.",
        "emoji": "🎲",
        "usable": True,
    },
    "rareRoll": {
        "name": "Rare Roll",
        "description": "Guaranteed Rare or higher stand roll.",
        "emoji": "🎰",
        "usable": True,
    },
    # Corpse Parts
    **{
        part_id: {
            "name": f"Saint's Corpse: {part_id.replace('_', ' ').title()}",
            "description": f"A sacred relic. Use it to unlock a hidden power.",
            "emoji": "✝️",
            "usable": True,
            "is_corpse_part": True,
        }
        for part_id in CORPSE_PARTS
    },
}


# ────────────────────────────────────────────────────────────
# DAILY REWARDS  (tiered)
# ────────────────────────────────────────────────────────────

def get_daily_reward(streak: int) -> dict:
    """Returns the reward dict for a given streak day."""
    milestones = {
        5:   {"coins": 500,   "items": {"xpPotion": 1}},
        10:  {"coins": 800,   "items": {"rareRoll": 1}},
        25:  {"coins": 1200,  "diamonds": 5},
        50:  {"coins": 2000,  "diamonds": 10,  "items": {"epicRoll": 1}},
        100: {"coins": 3500,  "diamonds": 25,  "items": {"actStone": 1}},
        250: {"coins": 5000,  "diamonds": 50,  "items": {"requiemArrow": 1}},
        500: {"coins": 10000, "diamonds": 100, "items": {"mythicalTicket": 1}},
    }

    base_coins = (
        200 if streak <= 4 else
        250 if streak <= 9 else
        300 if streak <= 24 else
        400 if streak <= 49 else
        500 if streak <= 99 else
        600 if streak <= 249 else
        750
    )

    if streak in milestones:
        reward = {"coins": milestones[streak]["coins"]}
        reward["diamonds"] = milestones[streak].get("diamonds", 0)
        reward["items"]    = milestones[streak].get("items", {})
    else:
        reward = {"coins": base_coins, "diamonds": 0, "items": {}}

    return reward


# ────────────────────────────────────────────────────────────
# RARITY COLOURS  (for Discord embeds)
# ────────────────────────────────────────────────────────────

RARITY_COLORS = {
    "Common":    0xAAAAAA,
    "Rare":      0x4A90D9,
    "Epic":      0x9B59B6,
    "Legendary": 0xF1C40F,
    "Mythical":  0xFF0000,
}

RARITY_EMOJIS = {
    "Common":    "⚪",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythical":  "🔴",
}




# ────────────────────────────────────────────────────────────
# XP & COINS FORMULAS
# ────────────────────────────────────────────────────────────

def xp_to_next_level(level: int) -> int:
    return int(50 * (level ** 1.5))

def xp_from_pve(opponent_level: int) -> int:
    return 10 + (opponent_level * 2)

def xp_from_pvp(opponent_level: int) -> int:
    return 25 + (opponent_level * 3)

def coins_from_pve(enemy_level: int) -> int:
    return int(20 + (enemy_level * 3))

def coins_from_pvp(opponent_stand_level: int, opponent_stars: int) -> int:
    return int(30 + (opponent_stand_level * 4) + (opponent_stars * 10))


# ────────────────────────────────────────────────────────────
# META-PASSIVES
# ────────────────────────────────────────────────────────────

META_PASSIVES = {
    "Harvest":       {"description": "+25% Coin gain from battles",              "type": "coin_bonus",     "value": 0.25},
    "Osiris":        {"description": "+10% D'Arby win chance",                   "type": "darby_bonus",    "value": 0.10},
    "Crazy Diamond": {"description": "Healing items restore 25% more HP",        "type": "heal_bonus",     "value": 0.25},
    "Gold Experience":{"description": "5% chance to double XP after a battle",   "type": "xp_double",      "value": 0.05},
}