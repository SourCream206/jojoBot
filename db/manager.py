"""
db/manager.py — SQLite database abstraction layer using aiosqlite
All tables, queries, and migrations live here.
"""

import aiosqlite
import asyncio
import json
import os
import logging
from typing import Optional

log = logging.getLogger("standarena.db")
DB_PATH = os.path.join(os.path.dirname(__file__), "standarena.db")


class DatabaseManager:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self._conn.commit()
        log.info("Database initialized.")

    # ─────────────────────────────────────────────
    # TABLE CREATION
    # ─────────────────────────────────────────────
    async def _create_tables(self):
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                user_id     TEXT PRIMARY KEY,
                username    TEXT,
                level       INTEGER DEFAULT 1,
                exp         INTEGER DEFAULT 0,
                hamon       INTEGER DEFAULT 0,
                stand_dust  INTEGER DEFAULT 0,
                sos_shards  INTEGER DEFAULT 0,
                elo         INTEGER DEFAULT 0,
                pity_count  INTEGER DEFAULT 0,
                equipped_stand TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inventory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                stand_name  TEXT NOT NULL,
                stars       INTEGER DEFAULT 1,
                stand_exp   INTEGER DEFAULT 0,
                is_equipped INTEGER DEFAULT 0,
                trained_dp  INTEGER DEFAULT 0,
                trained_sp  INTEGER DEFAULT 0,
                trained_rng INTEGER DEFAULT 0,
                trained_sta INTEGER DEFAULT 0,
                trained_pre INTEGER DEFAULT 0,
                trained_pot INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES players(user_id)
            );

            CREATE TABLE IF NOT EXISTS items (
                user_id     TEXT NOT NULL,
                item_name   TEXT NOT NULL,
                quantity    INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, item_name),
                FOREIGN KEY(user_id) REFERENCES players(user_id)
            );

            CREATE TABLE IF NOT EXISTS duel_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_id   TEXT NOT NULL,
                loser_id    TEXT NOT NULL,
                winner_elo  INTEGER,
                loser_elo   INTEGER,
                wager       INTEGER DEFAULT 0,
                fought_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS gangs (
                gang_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                leader_id   TEXT NOT NULL,
                treasury    INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS gang_members (
                gang_id     INTEGER NOT NULL,
                user_id     TEXT NOT NULL,
                joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(gang_id, user_id),
                FOREIGN KEY(gang_id) REFERENCES gangs(gang_id)
            );

            CREATE TABLE IF NOT EXISTS quests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                quest_id    TEXT NOT NULL,
                progress    INTEGER DEFAULT 0,
                completed   INTEGER DEFAULT 0,
                quest_type  TEXT DEFAULT 'daily',
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES players(user_id)
            );

            CREATE TABLE IF NOT EXISTS achievements (
                user_id         TEXT NOT NULL,
                achievement_id  TEXT NOT NULL,
                earned_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, achievement_id)
            );

            CREATE TABLE IF NOT EXISTS auctions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id       TEXT NOT NULL,
                stand_inv_id    INTEGER NOT NULL,
                starting_price  INTEGER NOT NULL,
                current_bid     INTEGER,
                bidder_id       TEXT,
                ends_at         TIMESTAMP NOT NULL,
                active          INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS raids (
                raid_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                boss_name   TEXT NOT NULL,
                raid_type   TEXT DEFAULT 'skirmish',
                channel_id  TEXT,
                phase       INTEGER DEFAULT 1,
                hp          INTEGER DEFAULT 1000,
                max_hp      INTEGER DEFAULT 1000,
                active      INTEGER DEFAULT 1,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS raid_participants (
                raid_id     INTEGER NOT NULL,
                user_id     TEXT NOT NULL,
                damage_dealt INTEGER DEFAULT 0,
                PRIMARY KEY(raid_id, user_id),
                FOREIGN KEY(raid_id) REFERENCES raids(raid_id)
            );

            CREATE TABLE IF NOT EXISTS stand_stats (
                stand_name  TEXT PRIMARY KEY,
                base_dp     INTEGER NOT NULL,
                base_sp     INTEGER NOT NULL,
                base_rng    INTEGER NOT NULL,
                base_sta    INTEGER NOT NULL,
                base_pre    INTEGER NOT NULL,
                base_pot    INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id);
            CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id);
            CREATE INDEX IF NOT EXISTS idx_quests_user ON quests(user_id);
        """)

    # ─────────────────────────────────────────────
    # PLAYER HELPERS
    # ─────────────────────────────────────────────
    async def get_player(self, user_id: str) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM players WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone()

    async def ensure_player(self, user_id: str, username: str = "Unknown") -> aiosqlite.Row:
        player = await self.get_player(user_id)
        if not player:
            await self._conn.execute(
                "INSERT OR IGNORE INTO players(user_id, username) VALUES(?,?)",
                (user_id, username)
            )
            await self._conn.commit()
            player = await self.get_player(user_id)
        return player

    async def update_player(self, user_id: str, **kwargs):
        if not kwargs:
            return
        cols = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        await self._conn.execute(f"UPDATE players SET {cols} WHERE user_id = ?", vals)
        await self._conn.commit()

    async def add_currency(self, user_id: str, currency: str, amount: int):
        await self._conn.execute(
            f"UPDATE players SET {currency} = {currency} + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await self._conn.commit()

    async def deduct_currency(self, user_id: str, currency: str, amount: int) -> bool:
        """Returns True if successful, False if insufficient funds."""
        player = await self.get_player(user_id)
        if not player or player[currency] < amount:
            return False
        await self._conn.execute(
            f"UPDATE players SET {currency} = {currency} - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await self._conn.commit()
        return True

    async def add_exp(self, user_id: str, amount: int):
        from bot.config import BASE_EXP_PER_LEVEL, MAX_PLAYER_LEVEL
        player = await self.get_player(user_id)
        if not player:
            return
        new_exp = player["exp"] + amount
        new_level = player["level"]
        leveled_up = False
        while new_level < MAX_PLAYER_LEVEL:
            needed = BASE_EXP_PER_LEVEL * new_level
            if new_exp >= needed:
                new_exp -= needed
                new_level += 1
                leveled_up = True
            else:
                break
        await self.update_player(user_id, exp=new_exp, level=new_level)
        return leveled_up, new_level

    # ─────────────────────────────────────────────
    # INVENTORY HELPERS
    # ─────────────────────────────────────────────
    async def add_stand(self, user_id: str, stand_name: str, stars: int = 1, rarity: str = None) -> int:
        async with self._conn.execute(
            "INSERT INTO inventory(user_id, stand_name, stars) VALUES(?,?,?)",
            (user_id, stand_name, stars)
        ) as cur:
            row_id = cur.lastrowid
        await self._conn.commit()
        # Seed base stats the first time any copy of this stand is added
        if rarity:
            await self.seed_base_stats(stand_name, rarity)
        else:
            # Try to look up rarity from the stand roster
            try:
                from bot.utils.helpers import find_stand as _fs
                _, data = _fs(stand_name)
                if data:
                    await self.seed_base_stats(stand_name, data.get("rarity", "Common"))
            except Exception:
                pass
        return row_id

    async def get_inventory(self, user_id: str):
        async with self._conn.execute(
            "SELECT * FROM inventory WHERE user_id = ? ORDER BY stars DESC, stand_name ASC",
            (user_id,)
        ) as cur:
            return await cur.fetchall()

    async def get_stand_entry(self, user_id: str, stand_name: str, stars: int = None):
        """Get first matching stand in inventory."""
        if stars is not None:
            async with self._conn.execute(
                "SELECT * FROM inventory WHERE user_id=? AND LOWER(stand_name)=LOWER(?) AND stars=? LIMIT 1",
                (user_id, stand_name, stars)
            ) as cur:
                return await cur.fetchone()
        async with self._conn.execute(
            "SELECT * FROM inventory WHERE user_id=? AND LOWER(stand_name)=LOWER(?) ORDER BY stars DESC LIMIT 1",
            (user_id, stand_name)
        ) as cur:
            return await cur.fetchone()

    async def remove_stand(self, inv_id: int):
        await self._conn.execute("DELETE FROM inventory WHERE id=?", (inv_id,))
        await self._conn.commit()

    async def update_stand(self, inv_id: int, **kwargs):
        if not kwargs:
            return
        cols = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [inv_id]
        await self._conn.execute(f"UPDATE inventory SET {cols} WHERE id=?", vals)
        await self._conn.commit()

    async def count_stand_copies(self, user_id: str, stand_name: str, stars: int = None) -> int:
        if stars is not None:
            async with self._conn.execute(
                "SELECT COUNT(*) FROM inventory WHERE user_id=? AND LOWER(stand_name)=LOWER(?) AND stars=?",
                (user_id, stand_name, stars)
            ) as cur:
                row = await cur.fetchone()
        else:
            async with self._conn.execute(
                "SELECT COUNT(*) FROM inventory WHERE user_id=? AND LOWER(stand_name)=LOWER(?)",
                (user_id, stand_name)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else 0

    async def count_stands_by_rarity(self, user_id: str, rarity: str, stars: int = 1) -> list:
        """Return all stand entries of a given rarity and star level for a user."""
        from bot.utils.helpers import load_stands
        part_stands = load_stands()
        # Get all stand names matching rarity
        matching = []
        for part in part_stands.values():
            for name, data in part.items():
                if data.get("rarity") == rarity:
                    matching.append(name.lower())

        async with self._conn.execute(
            "SELECT * FROM inventory WHERE user_id=? AND stars=?",
            (user_id, stars)
        ) as cur:
            rows = await cur.fetchall()
        return [r for r in rows if r["stand_name"].lower() in matching]

    # ─────────────────────────────────────────────
    # ITEMS
    # ─────────────────────────────────────────────
    async def get_item_count(self, user_id: str, item_name: str) -> int:
        async with self._conn.execute(
            "SELECT quantity FROM items WHERE user_id=? AND item_name=?",
            (user_id, item_name)
        ) as cur:
            row = await cur.fetchone()
        return row["quantity"] if row else 0

    async def get_all_items(self, user_id: str):
        async with self._conn.execute(
            "SELECT item_name, quantity FROM items WHERE user_id=? AND quantity > 0",
            (user_id,)
        ) as cur:
            return await cur.fetchall()

    async def add_item(self, user_id: str, item_name: str, amount: int = 1):
        await self._conn.execute(
            """INSERT INTO items(user_id, item_name, quantity) VALUES(?,?,?)
               ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + ?""",
            (user_id, item_name, amount, amount)
        )
        await self._conn.commit()

    async def remove_item(self, user_id: str, item_name: str, amount: int = 1) -> bool:
        count = await self.get_item_count(user_id, item_name)
        if count < amount:
            return False
        await self._conn.execute(
            "UPDATE items SET quantity = quantity - ? WHERE user_id=? AND item_name=?",
            (amount, user_id, item_name)
        )
        await self._conn.commit()
        return True

    # ─────────────────────────────────────────────
    # QUESTS
    # ─────────────────────────────────────────────
    async def get_active_quests(self, user_id: str, quest_type: str = "daily"):
        async with self._conn.execute(
            "SELECT * FROM quests WHERE user_id=? AND quest_type=? AND completed=0",
            (user_id, quest_type)
        ) as cur:
            return await cur.fetchall()

    async def assign_quest(self, user_id: str, quest_id: str, quest_type: str = "daily"):
        await self._conn.execute(
            "INSERT OR IGNORE INTO quests(user_id, quest_id, quest_type) VALUES(?,?,?)",
            (user_id, quest_id, quest_type)
        )
        await self._conn.commit()

    async def update_quest_progress(self, user_id: str, quest_type_filter: str, progress_type: str, amount: int = 1):
        """Increment progress on all matching quests."""
        rows = await self.get_active_quests(user_id, quest_type_filter)
        for row in rows:
            from bot.config import DAILY_QUEST_POOL, WEEKLY_QUEST_POOL
            pool = DAILY_QUEST_POOL if quest_type_filter == "daily" else WEEKLY_QUEST_POOL
            quest_def = next((q for q in pool if q["id"] == row["quest_id"]), None)
            if not quest_def or quest_def.get("type") != progress_type:
                continue
            new_progress = row["progress"] + amount
            completed = 1 if new_progress >= quest_def["target"] else 0
            await self._conn.execute(
                "UPDATE quests SET progress=?, completed=? WHERE id=?",
                (new_progress, completed, row["id"])
            )
        await self._conn.commit()

    # ─────────────────────────────────────────────
    # DUELS / ELO
    # ─────────────────────────────────────────────
    async def record_duel(self, winner_id: str, loser_id: str, wager: int = 0):
        from bot.config import ELO_WIN_GAIN, ELO_LOSS_LOSE
        winner = await self.get_player(winner_id)
        loser  = await self.get_player(loser_id)
        new_w_elo = (winner["elo"] if winner else 0) + ELO_WIN_GAIN
        new_l_elo = max(0, (loser["elo"] if loser else 0) - ELO_LOSS_LOSE)
        await self._conn.execute(
            "INSERT INTO duel_history(winner_id, loser_id, winner_elo, loser_elo, wager) VALUES(?,?,?,?,?)",
            (winner_id, loser_id, new_w_elo, new_l_elo, wager)
        )
        await self.update_player(winner_id, elo=new_w_elo)
        await self.update_player(loser_id,  elo=new_l_elo)
        await self._conn.commit()
        return new_w_elo, new_l_elo

    async def get_pvp_leaderboard(self, limit: int = 20):
        async with self._conn.execute(
            "SELECT user_id, username, elo FROM players ORDER BY elo DESC LIMIT ?",
            (limit,)
        ) as cur:
            return await cur.fetchall()

    # ─────────────────────────────────────────────
    # GANGS
    # ─────────────────────────────────────────────
    async def create_gang(self, name: str, leader_id: str) -> bool:
        try:
            await self._conn.execute(
                "INSERT INTO gangs(name, leader_id) VALUES(?,?)", (name, leader_id)
            )
            async with self._conn.execute("SELECT last_insert_rowid()") as cur:
                row = await cur.fetchone()
                gang_id = row[0]
            await self._conn.execute(
                "INSERT INTO gang_members(gang_id, user_id) VALUES(?,?)", (gang_id, leader_id)
            )
            await self._conn.commit()
            return True
        except Exception:
            return False

    async def get_gang(self, gang_name: str = None, user_id: str = None):
        if gang_name:
            async with self._conn.execute("SELECT * FROM gangs WHERE LOWER(name)=LOWER(?)", (gang_name,)) as cur:
                return await cur.fetchone()
        if user_id:
            async with self._conn.execute(
                "SELECT g.* FROM gangs g JOIN gang_members m ON g.gang_id=m.gang_id WHERE m.user_id=?",
                (user_id,)
            ) as cur:
                return await cur.fetchone()
        return None

    async def get_gang_members(self, gang_id: int):
        async with self._conn.execute(
            "SELECT gm.user_id, p.username FROM gang_members gm JOIN players p ON p.user_id=gm.user_id WHERE gm.gang_id=?",
            (gang_id,)
        ) as cur:
            return await cur.fetchall()

    # ─────────────────────────────────────────────
    # ACHIEVEMENTS
    # ─────────────────────────────────────────────
    async def grant_achievement(self, user_id: str, achievement_id: str) -> bool:
        try:
            await self._conn.execute(
                "INSERT OR IGNORE INTO achievements(user_id, achievement_id) VALUES(?,?)",
                (user_id, achievement_id)
            )
            await self._conn.commit()
            return True
        except Exception:
            return False

    async def get_achievements(self, user_id: str):
        async with self._conn.execute(
            "SELECT achievement_id, earned_at FROM achievements WHERE user_id=?",
            (user_id,)
        ) as cur:
            return await cur.fetchall()

    # ─────────────────────────────────────────────
    # LEADERBOARD / RICHLIST
    # ─────────────────────────────────────────────
    async def get_richlist(self, limit: int = 20):
        async with self._conn.execute(
            "SELECT user_id, username, hamon FROM players ORDER BY hamon DESC LIMIT ?", (limit,)
        ) as cur:
            return await cur.fetchall()


    # ─────────────────────────────────────────────
    # STAND STATS
    # ─────────────────────────────────────────────
    # Base stats seeded once per stand name (shared archetype).
    # Trained bonuses stored per inventory row so each copy levels independently.

    STAT_DB_COLS = {
        "destructive_power":     "trained_dp",
        "speed":                 "trained_sp",
        "range":                 "trained_rng",
        "stamina":               "trained_sta",
        "precision":             "trained_pre",
        "development_potential": "trained_pot",
    }

    RARITY_STAT_RANGES = {
        "Common":    (1, 3),
        "Rare":      (2, 4),
        "Epic":      (3, 5),
        "Legendary": (4, 5),
        "mythical":  (5, 5),
    }

    async def get_base_stats(self, stand_name: str):
        """Return stored base stats dict, or None if not seeded."""
        async with self._conn.execute(
            "SELECT * FROM stand_stats WHERE stand_name = ?", (stand_name,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return {
            "destructive_power":     row["base_dp"],
            "speed":                 row["base_sp"],
            "range":                 row["base_rng"],
            "stamina":               row["base_sta"],
            "precision":             row["base_pre"],
            "development_potential": row["base_pot"],
        }

    async def seed_base_stats(self, stand_name: str, rarity: str) -> dict:
        """Generate and persist base stats if they do not exist yet."""
        import random as _r
        existing = await self.get_base_stats(stand_name)
        if existing:
            return existing
        lo, hi = self.RARITY_STAT_RANGES.get(rarity, (1, 3))
        stats = {
            "destructive_power":     _r.randint(lo, hi),
            "speed":                 _r.randint(lo, hi),
            "range":                 _r.randint(lo, hi),
            "stamina":               _r.randint(lo, hi),
            "precision":             _r.randint(lo, hi),
            "development_potential": _r.randint(max(1, lo - 1), hi),
        }
        await self._conn.execute(
            """INSERT OR IGNORE INTO stand_stats
               (stand_name, base_dp, base_sp, base_rng, base_sta, base_pre, base_pot)
               VALUES (?,?,?,?,?,?,?)""",
            (stand_name,
             stats["destructive_power"], stats["speed"], stats["range"],
             stats["stamina"], stats["precision"], stats["development_potential"])
        )
        await self._conn.commit()
        return stats

    async def get_full_stats(self, inv_id: int, stand_name: str, rarity: str) -> dict:
        """Return base + trained totals for a specific inventory entry."""
        base = await self.seed_base_stats(stand_name, rarity)
        async with self._conn.execute(
            "SELECT trained_dp,trained_sp,trained_rng,trained_sta,trained_pre,trained_pot FROM inventory WHERE id=?",
            (inv_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return base
        trained = {
            "destructive_power":     row["trained_dp"],
            "speed":                 row["trained_sp"],
            "range":                 row["trained_rng"],
            "stamina":               row["trained_sta"],
            "precision":             row["trained_pre"],
            "development_potential": row["trained_pot"],
        }
        return {stat: base[stat] + trained[stat] for stat in base}

    async def train_stand_stat(self, inv_id: int, stand_name: str, rarity: str, stat: str) -> dict:
        """Increment one trained stat by 1, respecting the dev_potential cap."""
        col = self.STAT_DB_COLS.get(stat)
        if not col:
            return {"success": False, "reason": "unknown_stat"}

        base = await self.seed_base_stats(stand_name, rarity)
        from bot.config import MAX_TRAIN_BY_POTENTIAL
        pot = base.get("development_potential", 1)
        cap = MAX_TRAIN_BY_POTENTIAL.get(pot, 1)

        async with self._conn.execute(f"SELECT {col} FROM inventory WHERE id=?", (inv_id,)) as cur:
            row = await cur.fetchone()
        current_trained = row[col] if row else 0

        if current_trained >= cap:
            full = await self.get_full_stats(inv_id, stand_name, rarity)
            return {"success": False, "reason": "cap_reached", "cap": cap, "total": full[stat]}

        await self._conn.execute(
            f"UPDATE inventory SET {col} = {col} + 1 WHERE id = ?", (inv_id,)
        )
        await self._conn.commit()

        full = await self.get_full_stats(inv_id, stand_name, rarity)
        return {
            "success": True,
            "new_val": full[stat],
            "trained": current_trained + 1,
            "cap":     cap,
        }

    # ─────────────────────────────────────────────
    # MIGRATION FROM JSON
    # ─────────────────────────────────────────────
    async def migrate_from_json(self, inventories_path: str, items_path: str):
        """One-time migration from old JSON files."""
        if not os.path.exists(inventories_path):
            return
        log.info("Running JSON → SQLite migration...")
        with open(inventories_path, "r") as f:
            old_inv = json.load(f)
        old_items = {}
        if os.path.exists(items_path):
            with open(items_path, "r") as f:
                old_items = json.load(f)

        for user_id, entries in old_inv.items():
            await self.ensure_player(user_id)
            for entry in entries:
                if isinstance(entry, dict) and "name" in entry:
                    await self.add_stand(user_id, entry["name"], entry.get("stars", 1))
                elif isinstance(entry, str):
                    await self.add_stand(user_id, entry, 1)

        for user_id, items in old_items.items():
            await self.ensure_player(user_id)
            for item_name, qty in items.items():
                if qty > 0:
                    await self.add_item(user_id, item_name, qty)

        log.info("Migration complete.")

    async def close(self):
        if self._conn:
            await self._conn.close()
