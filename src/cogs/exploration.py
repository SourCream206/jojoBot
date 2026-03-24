"""
cogs/exploration.py
Stravel, Squests, Sarea
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta

from src.db import client as db
from src.utils.constants import (
    AREA_ORDER, AREA_LEVEL_REQUIREMENTS, AREA_QUEST_REQUIREMENTS,
    STAND_POOLS, TRAVEL_COST,
)


# ── Quest definitions ─────────────────────────────────────────────────────────

STORY_QUESTS = {
    "quest_cairo_start": {
        "title":       "Jotaro's Journey",
        "description": "Win 3 battles in Cairo.",
        "area":        "Cairo",
        "type":        "story",
        "goal":        3,
        "goal_type":   "wins",
        "rewards":     {"coins": 500, "items": {"xpPotion": 1}},
        "unlocks_quest": "quest_cairo_final",
    },
    "quest_cairo_final": {
        "title":       "Defeat DIO",
        "description": "Defeat DIO in Cairo. (Win a battle against a Legendary-tier enemy.)",
        "area":        "Cairo",
        "type":        "story",
        "goal":        1,
        "goal_type":   "boss_win",
        "rewards":     {"coins": 1000, "items": {"actStone": 1}},
        "unlocks_area": "Morioh Town",
    },
    "quest_morioh_final": {
        "title":       "Diamond is Unbreakable",
        "description": "Defeat Yoshikage Kira in Morioh Town.",
        "area":        "Morioh Town",
        "type":        "story",
        "goal":        1,
        "goal_type":   "boss_win",
        "rewards":     {"coins": 1500, "items": {"actStone": 1}},
        "unlocks_area": "Italy",
    },
    "quest_italy_final": {
        "title":       "Vento Aureo",
        "description": "Defeat Diavolo in Italy.",
        "area":        "Italy",
        "type":        "story",
        "goal":        1,
        "goal_type":   "boss_win",
        "rewards":     {"coins": 2000, "items": {"requiemArrow": 1}},
        "unlocks_area": "Philadelphia",
    },
    "quest_philly_final": {
        "title":       "Steel Ball Run",
        "description": "Defeat Funny Valentine in Philadelphia.",
        "area":        "Philadelphia",
        "type":        "story",
        "goal":        1,
        "goal_type":   "boss_win",
        "rewards":     {"coins": 3000, "diamonds": 10},
        "unlocks_area": "Morioh SBR",
    },
}

DAILY_QUESTS = [
    {
        "id":          "daily_battles",
        "title":       "Brawler",
        "description": "Win 5 battles.",
        "goal":        5,
        "goal_type":   "wins",
        "rewards":     {"coins": 300},
    },
    {
        "id":          "daily_rolls",
        "title":       "Stand Hunter",
        "description": "Roll 3 times.",
        "goal":        3,
        "goal_type":   "rolls",
        "rewards":     {"coins": 200, "items": {"xpPotion": 1}},
    },
    {
        "id":          "daily_travel",
        "title":       "Explorer",
        "description": "Travel to a different area.",
        "goal":        1,
        "goal_type":   "travel",
        "rewards":     {"coins": 150},
    },
]

WEEKLY_QUESTS = [
    {
        "id":          "weekly_pvp",
        "title":       "Rival Crusher",
        "description": "Win 10 PvP battles this week.",
        "goal":        10,
        "goal_type":   "pvp_wins",
        "rewards":     {"coins": 1500, "diamonds": 5},
    },
    {
        "id":          "weekly_merge",
        "title":       "Stand Upgrader",
        "description": "Perform 3 merges this week.",
        "goal":        3,
        "goal_type":   "merges",
        "rewards":     {"coins": 1000, "items": {"epicRoll": 1}},
    },
]


class Exploration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Stravel ───────────────────────────────────────────────────────────────

    @commands.command(name="travel", aliases=["go", "move", "goto"])
    async def stravel(self, ctx: commands.Context, *, area_name: str):
        """Travel to a different area. Costs 50 Coins. Usage: Stravel <area name>"""
        user_id = str(ctx.author.id)
        user    = await db.get_or_create_user(user_id, ctx.author.name)

        # Normalise input
        normalised = _normalise_area(area_name)
        if not normalised:
            area_list = "\n".join(f"• {a}" for a in AREA_ORDER)
            await ctx.reply(
                f"Unknown area. Available areas:\n{area_list}",
                mention_author=False,
            )
            return

        if normalised == user["current_area"]:
            await ctx.reply("You're already in that area!", mention_author=False)
            return

        # Check unlock
        unlocked_areas = await db.get_unlocked_areas(user_id)
        if normalised not in unlocked_areas:
            req_level = AREA_LEVEL_REQUIREMENTS.get(normalised, 999)
            req_quest = AREA_QUEST_REQUIREMENTS.get(normalised)
            await ctx.reply(
                f"**{normalised}** is locked!\n"
                f"Requirements: Player level **{req_level}** + complete quest `{req_quest}`.",
                mention_author=False,
            )
            return

        # Cost
        if user["coins"] < TRAVEL_COST:
            await ctx.reply(
                f"Not enough coins! Travel costs **{TRAVEL_COST} 🪙** (you have {user['coins']}).",
                mention_author=False,
            )
            return

        await db.add_coins(user_id, -TRAVEL_COST)
        await db.update_user(user_id, current_area=normalised)

        # Trigger daily travel quest progress
        await _advance_quest(user_id, "travel")

        stand_names = [s["name"] for s in STAND_POOLS.get(normalised, []) if not s.get("special_unlock")]
        preview = ", ".join(stand_names[:5])
        if len(stand_names) > 5:
            preview += f" (+{len(stand_names) - 5} more)"

        embed = discord.Embed(
            title=f"✈️ Arrived in {normalised}!",
            description=f"Spent **{TRAVEL_COST} 🪙**\n\n**Available stands:** {preview}",
            color=0x00BFFF,
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ── Sarea ──────────────────────────────────────────────────────────────────

    @commands.command(name="area", aliases=["map", "location", "where"])
    async def sarea(self, ctx: commands.Context):
        """View your current area and unlocked areas."""
        user_id = str(ctx.author.id)
        user    = await db.get_or_create_user(user_id, ctx.author.name)
        unlocked = await db.get_unlocked_areas(user_id)

        embed = discord.Embed(title="🗺️ World Map", color=0x00BFFF)
        for area in AREA_ORDER:
            if area in unlocked:
                marker = "📍 **HERE**" if area == user["current_area"] else "✅ Unlocked"
            else:
                req_level = AREA_LEVEL_REQUIREMENTS.get(area, "?")
                marker = f"🔒 Locked (Lv.{req_level} required)"
            embed.add_field(name=area, value=marker, inline=False)

        await ctx.reply(embed=embed, mention_author=False)

    # ── Squests ────────────────────────────────────────────────────────────────

    @commands.command(name="quests", aliases=["quest", "q", "missions"])
    async def squests(self, ctx: commands.Context, tab: str = "daily"):
        """
        View quests.
        - Squests daily   → daily quests
        - Squests weekly  → weekly quests
        - Squests story   → story quests
        """
        user_id = str(ctx.author.id)
        await db.get_or_create_user(user_id, ctx.author.name)
        tab = tab.lower()

        if tab == "story":
            await self._show_story_quests(ctx, user_id)
        elif tab == "weekly":
            await self._show_repeatable_quests(ctx, user_id, WEEKLY_QUESTS, "Weekly")
        else:
            await self._show_repeatable_quests(ctx, user_id, DAILY_QUESTS, "Daily")

    async def _show_story_quests(self, ctx, user_id: str):
        embed = discord.Embed(title="📜 Story Quests", color=0xF1C40F)
        for qid, qdata in STORY_QUESTS.items():
            record = await db.get_quest(user_id, qid)
            if record and record["completed"]:
                status = "✅ Completed"
            elif record:
                status = f"🔄 {record['progress']}/{qdata['goal']}"
            else:
                status = "🔒 Not started"
            embed.add_field(
                name=f"{qdata['title']} ({qdata['area']})",
                value=f"{qdata['description']}\n{status}",
                inline=False,
            )
        await ctx.reply(embed=embed, mention_author=False)

    async def _show_repeatable_quests(self, ctx, user_id: str, quest_list: list, label: str):
        embed = discord.Embed(title=f"📋 {label} Quests", color=0x00BFFF)
        for q in quest_list:
            record = await db.get_quest(user_id, q["id"])
            if record and record["completed"]:
                # Check if it needs resetting
                if record["refreshes_at"]:
                    refreshes = datetime.fromisoformat(record["refreshes_at"])
                    if refreshes.tzinfo is None:
                        refreshes = refreshes.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) >= refreshes:
                        await db.upsert_quest(user_id, q["id"], progress=0, completed=False)
                        status = "🔄 0/" + str(q["goal"])
                    else:
                        status = "✅ Completed"
                else:
                    status = "✅ Completed"
            elif record:
                status = f"🔄 {record['progress']}/{q['goal']}"
            else:
                status = f"⬜ 0/{q['goal']}"

            rewards = _format_rewards(q["rewards"])
            embed.add_field(
                name=q["title"],
                value=f"{q['description']}\n{status}\n🎁 {rewards}",
                inline=False,
            )
        await ctx.reply(embed=embed, mention_author=False)


# ── Quest progress helper (called from other cogs) ────────────────────────────

async def _advance_quest(user_id: str, goal_type: str, amount: int = 1) -> list[str]:
    """
    Called externally to advance quest progress.
    Returns list of quest titles that were completed this call (for popup notifications).
    goal_type: 'wins' | 'rolls' | 'travel' | 'pvp_wins' | 'merges' | 'boss_win'
    """
    all_quests = list(STORY_QUESTS.items()) + [
        (q["id"], q) for q in DAILY_QUESTS + WEEKLY_QUESTS
    ]

    completed_titles = []

    for qid, qdata in all_quests:
        if qdata.get("goal_type") != goal_type:
            continue
        record = await db.get_quest(user_id, qid)
        if record and record["completed"]:
            continue

        current  = record["progress"] if record else 0
        new_prog = current + amount

        if new_prog >= qdata["goal"]:
            # Award rewards
            rewards = qdata.get("rewards", {})
            if rewards.get("coins"):
                await db.add_coins(user_id, rewards["coins"])
            if rewards.get("diamonds"):
                await db.add_diamonds(user_id, rewards["diamonds"])
            for item_id, qty in rewards.get("items", {}).items():
                await db.add_item(user_id, item_id, qty)

            # Unlock area if story quest
            if qdata.get("unlocks_area"):
                user = await db.get_user(user_id)
                req_level = AREA_LEVEL_REQUIREMENTS.get(qdata["unlocks_area"], 0)
                if user and user["level"] >= req_level:
                    await db.unlock_area(user_id, qdata["unlocks_area"])

            # Determine refresh time
            refreshes_at = None
            if qdata.get("type") != "story":
                is_weekly = qid.startswith("weekly_")
                delta = timedelta(weeks=1) if is_weekly else timedelta(days=1)
                refreshes_at = (datetime.now(timezone.utc) + delta).isoformat()

            await db.upsert_quest(
                user_id, qid,
                progress=new_prog,
                completed=True,
                refreshes_at=refreshes_at,
            )
            completed_titles.append((qdata["title"], qdata.get("rewards", {})))
        else:
            is_weekly = qid.startswith("weekly_")
            delta = timedelta(weeks=1) if is_weekly else timedelta(days=1)
            refreshes_at = (datetime.now(timezone.utc) + delta).isoformat()
            await db.upsert_quest(user_id, qid, progress=new_prog, refreshes_at=refreshes_at)

    return completed_titles


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_area(raw: str) -> str | None:
    raw_lower = raw.lower().strip()
    for area in AREA_ORDER:
        if area.lower() == raw_lower or area.lower().startswith(raw_lower):
            return area
    return None

def _format_rewards(rewards: dict) -> str:
    parts = []
    if rewards.get("coins"):
        parts.append(f"{rewards['coins']} 🪙")
    if rewards.get("diamonds"):
        parts.append(f"{rewards['diamonds']} 💎")
    for item_id, qty in rewards.get("items", {}).items():
        from src.utils.constants import ITEMS
        name = ITEMS.get(item_id, {}).get("name", item_id)
        parts.append(f"{qty}× {name}")
    return ", ".join(parts) if parts else "None"


async def setup(bot):
    await bot.add_cog(Exploration(bot))