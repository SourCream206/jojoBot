"""
cogs/rolls.py
Sroll — rolls a random stand from the current area's pool.
"""

import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime, timezone

from src.db import client as db
from src.utils.constants import (
    STAND_POOLS, RARITY_WEIGHTS_STANDARD, RARITY_WEIGHTS_PREMIUM,
    PITY_LEGENDARY_THRESHOLD, PITY_MYTHICAL_THRESHOLD, SHINY_RATE, RARITY_EMOJIS, RARITY_COLORS,
)
from src.utils.passives import get_sroll_cooldown
from src.utils.embeds import stand_roll_embed


class Rolls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Sroll ──────────────────────────────────────────────────────────────────

    @commands.command(name="roll", aliases=["r", "gacha", "summon", "rol", "rool", "pull", "wish", "draw", "rl"])
    async def sroll(self, ctx: commands.Context):
        """Roll a random stand from your current area."""
        user = await db.get_or_create_user(str(ctx.author.id), ctx.author.name)

        # Cooldown check
        cooldown_secs = await get_sroll_cooldown(str(ctx.author.id))
        expires = await db.get_cooldown(str(ctx.author.id), "sroll")
        if expires:
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            await ctx.reply(
                f"⏳ You're on cooldown! Try again in **{int(remaining // 60)}m {int(remaining % 60)}s**.",
                mention_author=False,
            )
            return

        await db.set_cooldown(str(ctx.author.id), "sroll", cooldown_secs)

        # Build pool for current area - fetch unlocked stands, primary, and secondary in parallel
        area   = user["current_area"]
        pool   = STAND_POOLS.get(area, [])
        unlocked, primary, secondary = await asyncio.gather(
            db.get_unlocked_stands(str(ctx.author.id)),
            db.get_primary_stand(str(ctx.author.id)),
            db.get_secondary_stand(str(ctx.author.id))
        )

        # Filter out special_unlock stands unless player has unlocked them
        eligible = [
            s for s in pool
            if not s.get("special_unlock") or s["name"] in unlocked
        ]

        if not eligible:
            await ctx.reply("No stands available in this area!", mention_author=False)
            return

        # Osiris + Atum synergy (Better luck in rolling)
        weights = dict(RARITY_WEIGHTS_STANDARD)

        # [SYNERGY] Darby Brothers: Osiris + Atum -> Doubled rates for Epic+
        if primary and secondary:
            stands = {primary["stand_name"], secondary["stand_name"]}
            if {"Osiris", "Atum"}.issubset(stands):
                weights["Epic"] = weights.get("Epic", 0) * 2
                weights["Legendary"] = weights.get("Legendary", 0) * 2
                weights["Mythical"] = weights.get("Mythical", 0) * 2

        # Determine rarity (with pity)
        rarity = _roll_rarity(user["pity_counter"], user["mythical_pity_counter"], weights)

        # Pity update
        if rarity == "Legendary":
            await db.reset_pity(str(ctx.author.id), "legendary")
        elif rarity == "Mythical":
            await db.reset_pity(str(ctx.author.id), "mythical")
        else:
            # Increment both pity counters in a single DB call
            await db.increment_both_pity_counters(str(ctx.author.id))

        # Filter by rarity; fall back to any rarity if none available
        rarity_pool = [s for s in eligible if s["rarity"] == rarity]
        if not rarity_pool:
            rarity_pool = eligible

        stand_data = random.choice(rarity_pool)
        stand_name = stand_data["name"]
        is_shiny   = random.random() < SHINY_RATE

        # Save to DB
        await db.add_stand(str(ctx.author.id), stand_name, stars=1, is_shiny=is_shiny)

        # Advance roll quests and notify on completion
        from src.cogs.exploration import _advance_quest
        from src.utils.embeds import quest_complete_embed
        completed = await _advance_quest(str(ctx.author.id), "rolls")
        for quest_title, rewards in completed:
            await ctx.send(embed=quest_complete_embed(quest_title, rewards))

        embed = stand_roll_embed(stand_name, rarity, 1, is_shiny)
        embed.set_footer(text=f"Area: {area} | Pity: {user['pity_counter'] + 1}/{PITY_LEGENDARY_THRESHOLD}")
        await ctx.reply(embed=embed, mention_author=False)

    # ── Item Rolls ─────────────────────────────────────────────────────────────

    @commands.command(name="rareroll")
    async def rareroll(self, ctx: commands.Context):
        """Consume a Rare Roll to get a guaranteed Rare or better stand."""
        user = await db.get_or_create_user(str(ctx.author.id), ctx.author.name)

        has_item = await db.consume_item(str(ctx.author.id), "rareRoll")
        if not has_item:
            await ctx.reply("You don't have a **Rare Roll** item in your bag!", mention_author=False)
            return

        area   = user["current_area"]
        pool   = STAND_POOLS.get(area, [])

        # Fetch unlocked stands, primary, and secondary in parallel
        unlocked, primary, secondary = await asyncio.gather(
            db.get_unlocked_stands(str(ctx.author.id)),
            db.get_primary_stand(str(ctx.author.id)),
            db.get_secondary_stand(str(ctx.author.id))
        )

        eligible = [s for s in pool if not s.get("special_unlock") or s["name"] in unlocked]

        if not eligible:
            await db.add_item(str(ctx.author.id), "rareRoll", 1) # Refund
            await ctx.reply("No stands available in this area!", mention_author=False)
            return

        weights = {"Common": 0.0, "Rare": 0.55, "Epic": 0.30, "Legendary": 0.15, "Mythical": 0.0}

        if primary and secondary:
            stands = {primary["stand_name"], secondary["stand_name"]}
            if {"Osiris", "Atum"}.issubset(stands):
                weights["Epic"] *= 2
                weights["Legendary"] *= 2

        rarity = _roll_rarity(user["pity_counter"], user["mythical_pity_counter"], weights)

        if rarity == "Legendary":
            await db.reset_pity(str(ctx.author.id), "legendary")
        elif rarity == "Mythical":
            await db.reset_pity(str(ctx.author.id), "mythical")
        else:
            await db.increment_both_pity_counters(str(ctx.author.id))

        rarity_pool = [s for s in eligible if s["rarity"] == rarity]
        if not rarity_pool: rarity_pool = eligible

        stand_data = random.choice(rarity_pool)
        stand_name = stand_data["name"]
        is_shiny   = random.random() < SHINY_RATE

        await db.add_stand(str(ctx.author.id), stand_name, stars=1, is_shiny=is_shiny)

        embed = stand_roll_embed(stand_name, rarity, 1, is_shiny)
        embed.set_footer(text=f"🎰 Used a Rare Roll! | Area: {area}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="epicroll")
    async def epicroll(self, ctx: commands.Context):
        """Consume an Epic Roll to get a guaranteed Epic or better stand."""
        user = await db.get_or_create_user(str(ctx.author.id), ctx.author.name)

        has_item = await db.consume_item(str(ctx.author.id), "epicRoll")
        if not has_item:
            await ctx.reply("You don't have an **Epic Roll** item in your bag!", mention_author=False)
            return

        area   = user["current_area"]
        pool   = STAND_POOLS.get(area, [])

        # Fetch unlocked stands, primary, and secondary in parallel
        unlocked, primary, secondary = await asyncio.gather(
            db.get_unlocked_stands(str(ctx.author.id)),
            db.get_primary_stand(str(ctx.author.id)),
            db.get_secondary_stand(str(ctx.author.id))
        )

        eligible = [s for s in pool if not s.get("special_unlock") or s["name"] in unlocked]

        if not eligible:
            await db.add_item(str(ctx.author.id), "epicRoll", 1) # Refund
            await ctx.reply("No stands available in this area!", mention_author=False)
            return

        weights = {"Common": 0.0, "Rare": 0.0, "Epic": 0.70, "Legendary": 0.30, "Mythical": 0.0}

        if primary and secondary:
            stands = {primary["stand_name"], secondary["stand_name"]}
            if {"Osiris", "Atum"}.issubset(stands):
                weights["Legendary"] *= 2

        rarity = _roll_rarity(user["pity_counter"], user["mythical_pity_counter"], weights)

        if rarity == "Legendary":
            await db.reset_pity(str(ctx.author.id), "legendary")
        elif rarity == "Mythical":
            await db.reset_pity(str(ctx.author.id), "mythical")
        else:
            await db.increment_both_pity_counters(str(ctx.author.id))

        rarity_pool = [s for s in eligible if s["rarity"] == rarity]
        if not rarity_pool: rarity_pool = eligible

        stand_data = random.choice(rarity_pool)
        stand_name = stand_data["name"]
        is_shiny   = random.random() < SHINY_RATE

        await db.add_stand(str(ctx.author.id), stand_name, stars=1, is_shiny=is_shiny)

        embed = stand_roll_embed(stand_name, rarity, 1, is_shiny)
        embed.set_footer(text=f"🎲 Used an Epic Roll! | Area: {area}")
        await ctx.reply(embed=embed, mention_author=False)

    # ── Spity ──────────────────────────────────────────────────────────────────

    @commands.command(name="pity", aliases=["p", "counter"])
    async def spity(self, ctx: commands.Context):
        """Check your current pity counters."""
        user = await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        embed = discord.Embed(title="🎲 Pity Counters", color=0x9B59B6)
        embed.add_field(
            name="🟡 Legendary Pity",
            value=f"{user['pity_counter']}/{PITY_LEGENDARY_THRESHOLD} rolls",
            inline=True,
        )
        embed.add_field(
            name="🔴 Mythical Pity",
            value=f"{user['mythical_pity_counter']}/{PITY_MYTHICAL_THRESHOLD} rolls",
            inline=True,
        )
        await ctx.reply(embed=embed, mention_author=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _roll_rarity(pity: int, mythical_pity: int, weights: dict) -> str:
    # Pity override
    if mythical_pity >= PITY_MYTHICAL_THRESHOLD:
        return "Mythical"
    if pity >= PITY_LEGENDARY_THRESHOLD:
        return "Legendary"

    rarities = list(weights.keys())
    wts      = list(weights.values())
    return random.choices(rarities, weights=wts, k=1)[0]


async def setup(bot):
    await bot.add_cog(Rolls(bot))