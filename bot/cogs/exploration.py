"""
cogs/exploration.py — World map exploration, dungeons, search
Commands: Sexplore, Sdungeon, Smap, Stravel, Ssearch
"""

import discord
import asyncio
import random
from discord.ext import commands

from bot.config import (
    COOLDOWN_EXPLORE, COOLDOWN_DUNGEON, COOLDOWN_SEARCH,
    WORLD_AREAS, CURRENCY_HAMON,
    RARITY_WEIGHTS,
)
from bot.utils.helpers import build_weighted_list, rarity_color, load_stands


ROOM_TYPES = ["combat", "treasure", "rest", "elite", "boss"]


async def run_dungeon(ctx, bot, area_key: str, rooms: int = 3):
    """Shared dungeon runner."""
    area = WORLD_AREAS[area_key]
    user_id = str(ctx.author.id)
    drops = area["drops"]
    hamon_min, hamon_max = area["hamon_range"]
    total_hamon = 0
    found_stands = []
    found_items = []

    embed = discord.Embed(
        title=f"🗺️ Entering {area['name']}...",
        description=area["description"],
        color=0x3498DB
    )
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(1.5)

    for room_num in range(1, rooms + 1):
        room_type = random.choice(ROOM_TYPES)
        if room_num == rooms:
            room_type = "boss"

        if room_type == "combat" or room_type == "elite":
            enemy = random.choice(["Stand User", "Zombie Horde", "Vampire Guard", "Stone Free Wielder"])
            hamon_gain = random.randint(hamon_min // rooms, hamon_max // rooms)
            total_hamon += hamon_gain
            embed = discord.Embed(
                title=f"⚔️ Room {room_num}/{rooms} — {room_type.title()} Encounter",
                description=f"You face a **{enemy}**!\nYou defeat them and claim **{hamon_gain} Hamon**.",
                color=0xE74C3C
            )
            if room_type == "elite" and random.random() < 0.5:
                rarity = random.choice(drops)
                pool = [(n, d) for n, d in sum([list(p.items()) for p in load_stands().values()], []) if d.get("rarity") == rarity]
                if pool:
                    sname, sdata = random.choice(pool)
                    found_stands.append((sname, sdata))
                    embed.add_field(name="💎 Rare Drop!", value=f"**{sname}** ({rarity})", inline=False)
            await msg.edit(embed=embed)
            await asyncio.sleep(1.5)

        elif room_type == "treasure":
            loot = random.choice(["arrow_fragment", "Hamon Cache", "rareRoll"])
            if loot == "Hamon Cache":
                bonus = random.randint(hamon_min // 2, hamon_max)
                total_hamon += bonus
                embed = discord.Embed(title=f"💰 Room {room_num}/{rooms} — Treasure!", description=f"You found a **Hamon Cache**: +{bonus} Hamon!", color=0xF1C40F)
            else:
                await bot.db.add_item(user_id, loot)
                found_items.append(loot)
                embed = discord.Embed(title=f"📦 Room {room_num}/{rooms} — Treasure!", description=f"You found: **{loot}**!", color=0xF1C40F)
            await msg.edit(embed=embed)
            await asyncio.sleep(1.5)

        elif room_type == "rest":
            embed = discord.Embed(title=f"😴 Room {room_num}/{rooms} — Rest Area", description="You rest and recover strength.", color=0x57F287)
            await msg.edit(embed=embed)
            await asyncio.sleep(1)

        elif room_type == "boss":
            boss_name = random.choice(["DIO", "Yoshikage Kira", "Diavolo", "Enrico Pucci", "Funny Valentine"])
            hamon_gain = random.randint(hamon_max // 2, hamon_max)
            total_hamon += hamon_gain
            rarity = drops[-1]  # Best rarity for this area
            pool = [(n, d) for n, d in sum([list(p.items()) for p in load_stands().values()], []) if d.get("rarity") == rarity]
            boss_drop_name = boss_drop_data = None
            if pool and random.random() < 0.6:
                boss_drop_name, boss_drop_data = random.choice(pool)
                found_stands.append((boss_drop_name, boss_drop_data))

            embed = discord.Embed(
                title=f"⚡ Room {room_num}/{rooms} — BOSS: {boss_name}!",
                description=f"A fierce battle ensues... You emerge victorious!\nEarned: **{hamon_gain} Hamon**",
                color=0xE74C3C
            )
            if boss_drop_name:
                embed.add_field(name="🏆 Boss Drop!", value=f"**{boss_drop_name}** ({rarity})", inline=False)
                img = boss_drop_data.get("stars", {}).get("1") or boss_drop_data.get("image", "")
                if img: embed.set_image(url=img)
            await msg.edit(embed=embed)
            await asyncio.sleep(2)

        # Arrow fragment chance per room
        if random.random() < area.get("arrow_fragment_chance", 0.01):
            await bot.db.add_item(user_id, "arrow_fragment")
            found_items.append("arrow_fragment")

        # Rokakaka (Part 8 only)
        if random.random() < area.get("rokakaka_chance", 0):
            await bot.db.add_item(user_id, "Rokakaka Fruit")
            found_items.append("Rokakaka Fruit")

    # Add all stand drops
    for sname, _ in found_stands:
        await bot.db.add_stand(user_id, sname, 1)
    await bot.db.add_currency(user_id, CURRENCY_HAMON, total_hamon)
    await bot.db.add_exp(user_id, 40 * rooms)
    await bot.db.update_quest_progress(user_id, "daily", "explore", 1)

    # Summary
    summary = discord.Embed(title="🗺️ Exploration Complete!", color=0x57F287)
    summary.add_field(name="💰 Hamon Earned", value=str(total_hamon), inline=True)
    summary.add_field(name="📦 Items Found", value=", ".join(found_items) if found_items else "None", inline=True)
    if found_stands:
        summary.add_field(name="⚡ Stands Found", value="\n".join(f"• {n}" for n, _ in found_stands), inline=False)
    await msg.edit(embed=summary)


class Exploration(commands.Cog, name="Exploration"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="explore")
    @commands.cooldown(1, COOLDOWN_EXPLORE, commands.BucketType.user)
    async def explore(self, ctx, *, location: str = "morioh"):
        """Explore a location (3-room dungeon). Usage: Sexplore [location]"""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        area_key = location.lower().replace(" ", "_").replace("'", "")
        if area_key not in WORLD_AREAS:
            areas = ", ".join(f"`{k}`" for k in WORLD_AREAS)
            return await ctx.send(f"❌ Unknown location! Available: {areas}")
        area = WORLD_AREAS[area_key]
        player = await self.bot.db.get_player(user_id)
        if player["level"] < area["min_level"]:
            return await ctx.send(f"❌ Need **Level {area['min_level']}** to explore {area['name']}! (You are Level {player['level']})")
        await run_dungeon(ctx, self.bot, area_key, rooms=3)

    @explore.error
    async def explore_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.send(f"⏳ Explore on cooldown! **{m}m {s}s** remaining.")

    @commands.command(name="dungeon")
    @commands.cooldown(1, COOLDOWN_DUNGEON, commands.BucketType.user)
    async def dungeon(self, ctx, *, location: str = "morioh"):
        """Full 10-room deep dungeon run. Usage: Sdungeon [location]"""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        area_key = location.lower().replace(" ", "_").replace("'", "")
        if area_key not in WORLD_AREAS:
            areas = ", ".join(f"`{k}`" for k in WORLD_AREAS)
            return await ctx.send(f"❌ Unknown location! Available: {areas}")
        area = WORLD_AREAS[area_key]
        player = await self.bot.db.get_player(user_id)
        if player["level"] < area["min_level"]:
            return await ctx.send(f"❌ Need **Level {area['min_level']}** to explore {area['name']}!")
        await run_dungeon(ctx, self.bot, area_key, rooms=10)

    @dungeon.error
    async def dungeon_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            h, rem = divmod(int(error.retry_after), 3600); m, s = divmod(rem, 60)
            await ctx.send(f"⏳ Deep dungeon cooldown: **{h}h {m}m {s}s**.")

    @commands.command(name="map")
    async def world_map(self, ctx):
        """View the world map and your exploration areas."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        player = await self.bot.db.get_player(user_id)
        embed = discord.Embed(title="🗺️ World Map — Stand Arena", color=0x3498DB)
        for key, area in WORLD_AREAS.items():
            unlocked = player["level"] >= area["min_level"]
            status = "✅" if unlocked else f"🔒 (Lv.{area['min_level']})"
            embed.add_field(
                name=f"{status} {area['name']} (Part {area['part']})",
                value=f"{area['description']}\nDrops: {', '.join(area['drops'])}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name="search")
    @commands.cooldown(1, COOLDOWN_SEARCH, commands.BucketType.user)
    async def search(self, ctx, *, location: str = "morioh"):
        """Quick 60-second area scan for items."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        area_key = location.lower().replace(" ", "_").replace("'", "")
        area = WORLD_AREAS.get(area_key, WORLD_AREAS["morioh"])
        await ctx.send(f"🔍 Searching **{area['name']}**...")
        await asyncio.sleep(2)

        found = []
        if random.random() < area.get("arrow_fragment_chance", 0.01):
            await self.bot.db.add_item(user_id, "arrow_fragment")
            found.append("Arrow Fragment")
        hamon = random.randint(10, 50)
        await self.bot.db.add_currency(user_id, CURRENCY_HAMON, hamon)
        found.append(f"{hamon} Hamon")

        await ctx.send(f"🔍 Search complete! Found: {', '.join(found)}")

    @search.error
    async def search_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.send(f"⏳ Search cooldown: **{m}m {s}s**.")


async def setup(bot):
    await bot.add_cog(Exploration(bot))
