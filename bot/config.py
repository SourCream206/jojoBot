"""
config.py — All constants, weights, cooldowns, and game configuration
"""

# ─────────────────────────────────────────────
# ROLL WEIGHTS
# ─────────────────────────────────────────────
RARITY_WEIGHTS = {
    "mythical":  0,
    "Legendary": 5,
    "Epic":      15,
    "Rare":      30,
    "Common":    50,
}

RARE_ROLL_WEIGHTS = {
    "mythical":  10,
    "Legendary": 30,
    "Epic":      45,
    "Rare":      60,
    "Common":    0,
}

EPIC_ROLL_WEIGHTS = {
    "mythical":  20,
    "Legendary": 60,
    "Epic":      80,
    "Rare":      0,
    "Common":    0,
}

DARBY_WEIGHTS = {
    "Common":    5,
    "Rare":      15,
    "Epic":      30,
    "Legendary": 28,
    "mythical":  8,
}

DARBY_WIN_CHANCE = {
    "Common":    0.30,
    "Rare":      0.40,
    "Epic":      0.50,
    "Legendary": 0.60,
    "mythical":  0.80,
}

# ─────────────────────────────────────────────
# PITY
# ─────────────────────────────────────────────
PITY_THRESHOLD = 50

# ─────────────────────────────────────────────
# COOLDOWNS (seconds)
# ─────────────────────────────────────────────
COOLDOWN_ROLL      = 600
COOLDOWN_DAILY     = 86400
COOLDOWN_DARBY     = 1800
COOLDOWN_EXPLORE   = 1800
COOLDOWN_DUNGEON   = 7200
COOLDOWN_SEARCH    = 600
COOLDOWN_TRAIN     = 14400
COOLDOWN_STANDBY   = 28800
COOLDOWN_SUGGEST   = 900

# ─────────────────────────────────────────────
# CURRENCY
# ─────────────────────────────────────────────
CURRENCY_HAMON  = "hamon"
CURRENCY_DUST   = "stand_dust"
CURRENCY_SHARDS = "sos_shards"

TRADE_TAX_PERCENT  = 0.05
DAILY_HAMON_REWARD = 100
DAILY_ARROW_TICKET = 1

DISMANTLE_DUST = {
    "Common":    10,
    "Rare":      30,
    "Epic":      80,
    "Legendary": 200,
    "mythical":  500,
}

# ─────────────────────────────────────────────
# RARITY COLORS
# ─────────────────────────────────────────────
RARITY_COLORS = {
    "Common":    0x57F287,
    "Rare":      0x3498DB,
    "Epic":      0x9B59B6,
    "Legendary": 0xF1C40F,
    "mythical":  0xE74C3C,
}

# ─────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────
TRAIN_HAMON_COST = 50
TRAIN_STAT_GAIN  = 1
STAT_NAMES = ["destructive_power", "speed", "range", "stamina", "precision", "development_potential"]
STAT_DISPLAY = {
    "destructive_power":    "Destructive Power",
    "speed":                "Speed",
    "range":                "Range",
    "stamina":              "Stamina",
    "precision":            "Precision",
    "development_potential":"Development Potential",
}
MAX_TRAIN_BY_POTENTIAL = {5: 10, 4: 8, 3: 5, 2: 3, 1: 1}

# ─────────────────────────────────────────────
# EVOLUTION
# ─────────────────────────────────────────────
ACT_REQUIREMENTS = {
    "Act II":  {"level": 30, "act_stones": 1},
    "Act III": {"level": 60, "act_stones": 2},
    "Act IV":  {"level": 90, "act_stones": 3},
}

REQUIEM_STAT_BONUS = 0.30

ACT_UPGRADES = {
    "echoesact1": {
        "new_stand": "Echoes Act2",
        "gif_url": "https://cdn.discordapp.com/attachments/1353096163410055170/1353826415337799851/UntitledProject-ezgif.com-cut.gif",
        "image_url": "https://media.discordapp.net/attachments/1348433490269700198/1349369860349493299/image.png",
    },
    "echoesact2": {
        "new_stand": "Echoes Act3",
        "gif_url": "https://tenor.com/view/okay-jojo-jjba-dui-part4-gif-13897254",
        "image_url": "https://media.discordapp.net/attachments/1348433490269700198/1349370095909994540/image.png",
    },
    "tuskact1": {
        "new_stand": "Tusk ACT2",
        "gif_url": "",
        "image_url": "",
    },
    "tuskact2": {
        "new_stand": "Tusk ACT3",
        "gif_url": "",
        "image_url": "",
    },
    "tuskact3": {
        "new_stand": "Tusk ACT4",
        "gif_url": "",
        "image_url": "",
    },
}

REQUIEM_UPGRADES = {
    "goldexperience": {
        "new_stand": "Gold Experience Requiem",
        "gif_url": "https://tenor.com/view/jojo-jo-jos-adventurebizarre-giorno-giovanna-golden-wind-gold-experience-gif-14487899",
        "image_url": "https://media.discordapp.net/attachments/1353096163410055170/1353098891452612658/image.png",
    },
    "silverchariot": {
        "new_stand": "Silver Chariot Requiem",
        "gif_url": "https://cdn.discordapp.com/attachments/1353096163410055170/1353163280553873449/UntitledProject-ezgif.com-optimize.gif",
        "image_url": "https://cdn.discordapp.com/attachments/1353096163410055170/1353162556805746688/image.png",
    },
}

# ─────────────────────────────────────────────
# PVP RANKS
# ─────────────────────────────────────────────
PVP_RANKS = [
    ("E",  "Stand User",     0),
    ("D",  "Ripple Warrior", 100),
    ("C",  "Pillar Man",     300),
    ("B",  "Crusader",       600),
    ("A",  "JoJo",           1000),
    ("S",  "Platinum",       1500),
    ("SS", "WRYYY (DIO)",    2500),
]

ELO_WIN_GAIN  = 25
ELO_LOSS_LOSE = 20

# ─────────────────────────────────────────────
# EXPLORATION AREAS
# ─────────────────────────────────────────────
WORLD_AREAS = {
    "morioh": {
        "name": "Morioh",
        "part": 4,
        "min_level": 1,
        "description": "A quiet town with bizarre secrets lurking beneath the surface.",
        "drops": ["Common", "Rare"],
        "hamon_range": (50, 150),
        "arrow_fragment_chance": 0.01,
    },
    "dio_mansion": {
        "name": "Dio's Mansion",
        "part": 3,
        "min_level": 15,
        "description": "A dark, opulent mansion filled with Stand users loyal to DIO.",
        "drops": ["Rare", "Epic"],
        "hamon_range": (100, 250),
        "arrow_fragment_chance": 0.03,
    },
    "colosseum": {
        "name": "Colosseum",
        "part": 5,
        "min_level": 30,
        "description": "A brutal arena where only the strongest Stand users survive.",
        "drops": ["Epic", "Legendary"],
        "hamon_range": (200, 400),
        "arrow_fragment_chance": 0.05,
    },
    "green_dolphin": {
        "name": "Green Dolphin Prison",
        "part": 6,
        "min_level": 50,
        "description": "A trap-laden maximum security prison filled with Stone Ocean Stands.",
        "drops": ["Epic", "Legendary"],
        "hamon_range": (300, 500),
        "arrow_fragment_chance": 0.05,
    },
    "steel_ball_run": {
        "name": "Steel Ball Run Track",
        "part": 7,
        "min_level": 70,
        "description": "A cross-continental race where death is always one step behind.",
        "drops": ["Legendary", "mythical"],
        "hamon_range": (400, 700),
        "arrow_fragment_chance": 0.07,
    },
    "the_void": {
        "name": "The Void",
        "part": 8,
        "min_level": 90,
        "description": "A reality-bending endgame zone inhabited by Rock Humans.",
        "drops": ["Legendary", "mythical"],
        "hamon_range": (600, 1000),
        "arrow_fragment_chance": 0.10,
        "rokakaka_chance": 0.005,
    },
}

# ─────────────────────────────────────────────
# SHOP
# ─────────────────────────────────────────────
BIZARRE_BAZAAR = {
    "Common Roll":      {"cost": 100,  "currency": CURRENCY_HAMON,  "item": "rareRoll"},
    "Training Boost":   {"cost": 200,  "currency": CURRENCY_HAMON,  "item": "training_boost"},
    "HP Potion":        {"cost": 50,   "currency": CURRENCY_HAMON,  "item": "hp_potion"},
}

BLACK_MARKET = {
    "Act Stone":        {"cost": 150,  "currency": CURRENCY_DUST,   "item": "actStone"},
    "Star Up Token":    {"cost": 500,  "currency": CURRENCY_DUST,   "item": "star_up_token"},
    "Ability Reroll":   {"cost": 300,  "currency": CURRENCY_DUST,   "item": "ability_reroll"},
}

VOID_SHOP = {
    "Epic Roll":        {"cost": 50,   "currency": CURRENCY_SHARDS, "item": "epicRoll"},
    "Requiem Arrow":    {"cost": 200,  "currency": CURRENCY_SHARDS, "item": "Requiem Arrow"},
}

# ─────────────────────────────────────────────
# CRAFTING
# ─────────────────────────────────────────────
CRAFTING_RECIPES = {
    "requiemarrow": {
        "description": "Combine 5 Arrow Fragments into a Requiem Arrow",
        "requirements": [{"item": "arrow_fragment", "amount": 5}],
        "reward": {"item": "Requiem Arrow", "amount": 1},
    },
    "actstone": {
        "description": "Fuse 5 Epic (★1) stands into an Act Stone",
        "requirements": [{"rarity": "Epic", "stars": 1, "amount": 5}],
        "reward": {"item": "actStone", "amount": 1},
    },
    "rareroll": {
        "description": "Recycle 10 Common stands into a Rare Roll",
        "requirements": [{"rarity": "Common", "stars": 1, "amount": 10}],
        "reward": {"item": "rareRoll", "amount": 1},
    },
    "epicroll": {
        "description": "Recycle 10 Rare stands into an Epic Roll",
        "requirements": [{"rarity": "Rare", "stars": 1, "amount": 10}],
        "reward": {"item": "epicRoll", "amount": 1},
    },
    "bitesthedust": {
        "description": "Fuse Killer Queen + Stray Cat + Sheer Heart Attack",
        "requirements": [
            {"stand": "Killer Queen",       "stars": 1, "amount": 1},
            {"stand": "Stray Cat",          "stars": 1, "amount": 1},
            {"stand": "Sheer Heart Attack", "stars": 1, "amount": 1},
        ],
        "reward": {"stand": "Killer Queen: Bites the Dust", "amount": 1},
        "auto_craft": True,
        "cutscene": "https://tenor.com/view/killer-queen-kira-yoshikage-stand-diamond-is-unbreakable-aura-gif-26566253",
        "image_url": "https://cdn.discordapp.com/attachments/1348433490269700198/1348797763030093834/image.png",
    },
    "bizarre": {
        "description": "Combine any 5 bizarre items into an Epic Roll",
        "requirements": [],
        "reward": {"item": "epicRoll", "amount": 1},
        "is_bizarre": True,
    },
}

# ─────────────────────────────────────────────
# DARBY STAND
# ─────────────────────────────────────────────
DARBY_STAND = "Osiris"

# ─────────────────────────────────────────────
# PLAYER LEVEL
# ─────────────────────────────────────────────
MAX_PLAYER_LEVEL = 100
BASE_EXP_PER_LEVEL = 100

LEVEL_UNLOCKS = {
    11: "pvp_ranked",
    26: "act_evolution",
    51: "requiem_quest",
    76: "omega_raids",
    100: "over_heaven",
}

# ─────────────────────────────────────────────
# QUESTS
# ─────────────────────────────────────────────
DAILY_QUEST_POOL = [
    {"id": "dq_win2", "title": "Duel Master", "desc": "Win 2 duels", "type": "win_duels", "target": 2, "reward_hamon": 150, "reward_exp": 50},
    {"id": "dq_explore", "title": "Explorer", "desc": "Complete an exploration run", "type": "explore", "target": 1, "reward_hamon": 100, "reward_exp": 40},
    {"id": "dq_roll3", "title": "Arrow Seeker", "desc": "Roll 3 times", "type": "roll", "target": 3, "reward_hamon": 80, "reward_exp": 30},
    {"id": "dq_craft", "title": "Craftsman", "desc": "Craft any item", "type": "craft", "target": 1, "reward_hamon": 120, "reward_exp": 45},
    {"id": "dq_train", "title": "Discipline", "desc": "Train your stand", "type": "train", "target": 1, "reward_hamon": 100, "reward_exp": 35},
    {"id": "dq_daily", "title": "Regular", "desc": "Claim your daily reward", "type": "daily", "target": 1, "reward_hamon": 50, "reward_exp": 20},
]

WEEKLY_QUEST_POOL = [
    {"id": "wq_rank", "title": "Rank Climber", "desc": "Reach B rank this week", "type": "reach_rank", "target": "B", "reward_dust": 100, "reward_item": "rareRoll"},
    {"id": "wq_duel10", "title": "Street Fighter", "desc": "Win 10 duels", "type": "win_duels", "target": 10, "reward_dust": 80, "reward_hamon": 500},
    {"id": "wq_explore5", "title": "Wanderer", "desc": "Complete 5 exploration runs", "type": "explore", "target": 5, "reward_dust": 60, "reward_hamon": 400},
]
