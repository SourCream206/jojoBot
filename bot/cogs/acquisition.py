"""
cogs/acquisition.py — Rolling, crafting, merging/fusing, using items, trading
Commands: Sroll, Sdaily, Srollrare, Srollepic, Smerge/Sfuse, Scraft, Suse,
          Sitems, Sdismantle, Sbizarredrop (weekend drop)
"""

import discord
import random
import asyncio
import datetime
from discord.ext import commands

from bot.config import (
    RARITY_WEIGHTS, RARE_ROLL_WEIGHTS, EPIC_ROLL_WEIGHTS,
    COOLDOWN_ROLL, COOLDOWN_DAILY,
    RARITY_COLORS, PITY_THRESHOLD,
    DISMANTLE_DUST, CURRENCY_HAMON, CURRENCY_DUST,
    DAILY_HAMON_REWARD, ALL_BIZARRE_ITEMS, CRAFTING_RECIPES,
    ACT_UPGRADES, REQUIEM_UPGRADES, MERGE_COPIES_REQUIRED,
    DARBY_STAND,
)
from bot.utils.helpers import build_weighted_list, find_stand, normalize, rarity_color, stand_embed


class Acquisition(commands.Cog, name="Acquisition"):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────────
    # ROLL
    # ─────────────────────────────────────────────
    @commands.command(name="roll", aliases=["r", "rol"])
    @commands.cooldown(1, COOLDOWN_ROLL, commands.BucketType.user)
    async def roll_stand(self, ctx):
        """Roll for a random Stand."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)

        pool = build_weighted_list(RARITY_WEIGHTS)
        if not pool:
            return await ctx.send("❌ No rollable stands found!")

        # Pity check
        player = await self.bot.db.get_player(user_id)
        pity = player["pity_count"] + 1
        chosen_name, chosen_data = random.choice(pool)
        if pity >= PITY_THRESHOLD and chosen_data["rarity"] not in ("Legendary", "mythical"):
            # Force a legendary
            leg_pool = [(n, d) for n, d in pool if d["rarity"] in ("Legendary", "mythical")]
            if leg_pool:
                chosen_name, chosen_data = random.choice(leg_pool)
            pity = 0
        else:
            if chosen_data["rarity"] in ("Legendary", "mythical"):
                pity = 0

        await self.bot.db.update_player(user_id, pity_count=pity)

        # Animation
        embed = discord.Embed(title=f"{ctx.author.name} is rolling...", description="🔄 Rolling...", color=0x2C2F33)
        msg = await ctx.send(embed=embed)
        for stage, color in [("Common", 0x57F287), ("Rare", 0x3498DB), ("Epic", 0x9B59B6), ("Legendary", 0xF1C40F)]:
            embed.color = color
            embed.description = f"🎲 Rolling... **{stage}**"
            await msg.edit(embed=embed)
            await asyncio.sleep(0.6)

        # Add to inventory
        await self.bot.db.add_stand(user_id, chosen_name, 1)
        await self.bot.db.update_quest_progress(user_id, "daily", "roll", 1)

        final = stand_embed(chosen_name, chosen_data, title=f"{ctx.author.name} rolled **{chosen_name}**!")
        final.add_field(name="Pity Counter", value=f"{pity}/{PITY_THRESHOLD}", inline=True)

        # Requiem Arrow drop (1/350)
        if random.randint(1, 350) == 1:
            await self.bot.db.add_item(user_id, "Requiem Arrow")
            final.add_field(name="???", value="You found a **Requiem Arrow** on the ground! 🏹", inline=False)

        # Weekend bizarre drop (15%)
        today = datetime.datetime.today().weekday()
        if today >= 5 and random.randint(1, 100) <= 15:
            item = random.choice(ALL_BIZARRE_ITEMS)
            await self.bot.db.add_item(user_id, item)
            final.add_field(name="💥 Bizarre Find!", value=f"You also found **{item}**!", inline=False)

        # Flashy animation for high rarity
        rarity = chosen_data["rarity"]
        if rarity in ("Legendary", "mythical"):
            for i in range(3):
                mention = f"{ctx.author.mention} rolled **{chosen_name}** ({rarity})!"
                await msg.edit(content=mention if i % 2 == 0 else "", embed=final)
                await asyncio.sleep(0.5)

        await msg.edit(embed=final)

    @roll_stand.error
    async def roll_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Roll on cooldown! {int(error.retry_after // 60)}m {int(error.retry_after % 60)}s remaining.")

    # ─────────────────────────────────────────────
    # DAILY
    # ─────────────────────────────────────────────
    @commands.command(name="daily")
    @commands.cooldown(1, COOLDOWN_DAILY, commands.BucketType.user)
    async def daily_reward(self, ctx):
        """Claim your daily reward: Hamon + Rare Roll ticket."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        await self.bot.db.add_currency(user_id, CURRENCY_HAMON, DAILY_HAMON_REWARD)
        await self.bot.db.add_item(user_id, "rareRoll", 1)
        await self.bot.db.update_quest_progress(user_id, "daily", "daily", 1)

        # Refresh daily quests if none active
        from bot.config import DAILY_QUEST_POOL
        active = await self.bot.db.get_active_quests(user_id, "daily")
        if not active:
            sample = random.sample(DAILY_QUEST_POOL, min(3, len(DAILY_QUEST_POOL)))
            for q in sample:
                await self.bot.db.assign_quest(user_id, q["id"], "daily")

        embed = discord.Embed(
            title="✅ Daily Reward Claimed!",
            description=f"**+{DAILY_HAMON_REWARD} Hamon** and **1 Rare Roll** added to your inventory!\nNew daily quests are ready — check `Squests`.",
            color=0x57F287
        )
        await ctx.send(embed=embed)

    @daily_reward.error
    async def daily_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            r = int(error.retry_after)
            h, rem = divmod(r, 3600); m, s = divmod(rem, 60)
            embed = discord.Embed(title="⏳ Already Claimed!", description=f"Come back in **{h}h {m}m {s}s**.", color=0xE74C3C)
            await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # RARE ROLL
    # ─────────────────────────────────────────────
    @commands.command(name="rollrare", aliases=["rareroll", "rr"])
    async def roll_rare(self, ctx):
        """Use a Rare Roll ticket for a guaranteed Rare+ stand."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        if not await self.bot.db.remove_item(user_id, "rareRoll", 1):
            return await ctx.send("❌ You need a **Rare Roll** ticket! Earn one via `Sdaily`.")

        pool = build_weighted_list(RARE_ROLL_WEIGHTS)
        chosen_name, chosen_data = random.choice(pool)
        await self.bot.db.add_stand(user_id, chosen_name, 1)
        await self.bot.db.update_quest_progress(user_id, "daily", "roll", 1)

        embed = discord.Embed(title=f"🎲 {ctx.author.name} used a Rare Roll!", description=f"**Rarity:** {chosen_data['rarity']}", color=rarity_color(chosen_data["rarity"]))
        img = chosen_data.get("stars", {}).get("1") or chosen_data.get("image", "")
        if img: embed.set_image(url=img)
        embed.set_footer(text=f"{chosen_name} added to inventory.")
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # EPIC ROLL
    # ─────────────────────────────────────────────
    @commands.command(name="rollepic", aliases=["epicroll", "re", "er"])
    async def roll_epic(self, ctx):
        """Use an Epic Roll ticket for a guaranteed Epic+ stand."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        if not await self.bot.db.remove_item(user_id, "epicRoll", 1):
            return await ctx.send("❌ You need an **Epic Roll** ticket! Craft one via `Scraft epicroll`.")

        pool = build_weighted_list(EPIC_ROLL_WEIGHTS)
        chosen_name, chosen_data = random.choice(pool)
        await self.bot.db.add_stand(user_id, chosen_name, 1)
        await self.bot.db.update_quest_progress(user_id, "daily", "roll", 1)

        embed = discord.Embed(title=f"✨ {ctx.author.name} used an Epic Roll!", description=f"**Rarity:** {chosen_data['rarity']}", color=rarity_color(chosen_data["rarity"]))
        img = chosen_data.get("stars", {}).get("1") or chosen_data.get("image", "")
        if img: embed.set_image(url=img)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # MERGE / FUSE  (5-copy legacy + 3-copy new)
    # ─────────────────────────────────────────────
    @commands.command(name="merge", aliases=["m", "mer", "fuse"])
    async def merge(self, ctx, *, args: str = None):
        """Merge 5 copies of a stand to raise its star level. Usage: Smerge <Stand Name> [target_stars]"""
        if not args:
            return await ctx.send("Usage: `Smerge <Stand Name>` or `Smerge <Stand Name> <target_stars>`")

        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        parts = args.split()
        target_stars = None
        stand_parts = parts[:]
        if parts[-1].isdigit():
            target_stars = int(parts[-1])
            stand_parts = parts[:-1]

        stand_input = " ".join(stand_parts)
        canonical, stand_data = find_stand(stand_input)
        if not canonical:
            return await ctx.send(f"❌ Stand **{stand_input}** not found.")

        # Find all copies; determine current star counts
        inv = await self.bot.db.get_inventory(user_id)
        copies = [e for e in inv if normalize(e["stand_name"]) == normalize(canonical)]
        star_counts = {}
        for c in copies:
            star_counts[c["stars"]] = star_counts.get(c["stars"], 0) + 1

        if target_stars is None:
            # Find lowest mergeable level (5+ copies)
            possible = [s + 1 for s, cnt in star_counts.items() if cnt >= MERGE_COPIES_REQUIRED and s < 5]
            if not possible:
                return await ctx.send(f"❌ You need **{MERGE_COPIES_REQUIRED}** copies of the same star level to merge!")
            target_stars = min(possible)

        required_prev = target_stars - 1
        if required_prev < 1:
            return await ctx.send("❌ Cannot merge to ★1!")
        available = [c for c in copies if c["stars"] == required_prev]
        if len(available) < MERGE_COPIES_REQUIRED:
            return await ctx.send(f"❌ Need **{MERGE_COPIES_REQUIRED}x ★{required_prev} {canonical}** (have {len(available)}).")

        # Remove 5 copies
        for entry in available[:MERGE_COPIES_REQUIRED]:
            await self.bot.db.remove_stand(entry["id"])

        # Add merged copy
        await self.bot.db.add_stand(user_id, canonical, target_stars)

        # Darby unlock message
        if normalize(canonical) == normalize(DARBY_STAND) and target_stars == 2:
            await ctx.send(embed=discord.Embed(title="🎰 New Command Unlocked!", description="`Sdarby` gambling is now available!", color=0xFFD700))

        new_img = stand_data.get("stars", {}).get(str(target_stars), "")
        embed = discord.Embed(title=f"🌟 {canonical} Ascended!", description=f"Merged **{MERGE_COPIES_REQUIRED}x ★{required_prev}** → **★{target_stars}**!", color=0xF1C40F)
        if new_img: embed.set_image(url=new_img)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # DISMANTLE
    # ─────────────────────────────────────────────
    @commands.command(name="dismantle", aliases=["dis"])
    async def dismantle(self, ctx, *, stand_name: str = None):
        """Dismantle a stand for Stand Dust. Usage: Sdismantle <Stand Name>"""
        if not stand_name:
            return await ctx.send("Usage: `Sdismantle <Stand Name>`")
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        canonical, stand_data = find_stand(stand_name)
        if not canonical:
            return await ctx.send(f"❌ Stand **{stand_name}** not found.")
        entry = await self.bot.db.get_stand_entry(user_id, canonical)
        if not entry:
            return await ctx.send(f"❌ You don't have **{canonical}** in your inventory!")

        rarity = stand_data.get("rarity", "Common")
        dust = DISMANTLE_DUST.get(rarity, 10) * entry["stars"]

        # Confirm
        embed = discord.Embed(title="⚠️ Confirm Dismantle", description=f"Dismantle **{canonical} ★{entry['stars']}** for **{dust} Stand Dust**?\nReact ✅ to confirm or ❌ to cancel.", color=0xE67E22)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅"); await msg.add_reaction("❌")

        def check(r, u): return u == ctx.author and r.message.id == msg.id and str(r.emoji) in ("✅", "❌")
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("❌ Dismantle cancelled (timed out).")

        if str(reaction.emoji) == "❌":
            return await ctx.send("❌ Dismantle cancelled.")

        await self.bot.db.remove_stand(entry["id"])
        await self.bot.db.add_currency(user_id, CURRENCY_DUST, dust)
        await ctx.send(f"🔥 Dismantled **{canonical} ★{entry['stars']}** → **+{dust} Stand Dust**!")

    # ─────────────────────────────────────────────
    # CRAFT
    # ─────────────────────────────────────────────
    @commands.command(name="craft")
    async def craft(self, ctx, *, recipe_arg: str = None):
        """Craft items from components. Usage: Scraft [recipe] [auto] [amount]"""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)

        if not recipe_arg:
            embed = discord.Embed(title="⚒️ Crafting Recipes", color=0x3498DB)
            for key, recipe in CRAFTING_RECIPES.items():
                reqs = []
                if recipe.get("is_bizarre"):
                    reqs.append("5× Any Bizarre Items")
                else:
                    for r in recipe["requirements"]:
                        if "item" in r:
                            reqs.append(f"{r['amount']}× {r['item']}")
                        elif "stand" in r:
                            reqs.append(f"{r['amount']}× {r['stand']} ★{r.get('stars',1)}")
                        else:
                            reqs.append(f"{r['amount']}× {r['rarity']} ★{r.get('stars',1)}")
                reward = recipe["reward"]
                r_name = reward.get("item") or reward.get("stand")
                embed.add_field(
                    name=f"🔹 {key.upper()}",
                    value=f"{recipe['description']}\n**Requires:** {', '.join(reqs)}\n**Reward:** {reward['amount']}× {r_name}",
                    inline=False
                )
            return await ctx.send(embed=embed)

        args = recipe_arg.lower().split()
        recipe_name = args[0]
        if recipe_name not in CRAFTING_RECIPES:
            return await ctx.send("❌ Unknown recipe! Use `Scraft` to see options.")

        recipe = CRAFTING_RECIPES[recipe_name]
        amount = 1
        if len(args) > 1:
            try: amount = max(1, int(args[-1]))
            except ValueError: pass

        # ── Bizarre recipe ──
        if recipe.get("is_bizarre"):
            all_items = await self.bot.db.get_all_items(user_id)
            bizarre_total = sum(row["quantity"] for row in all_items if row["item_name"].strip() in [b.strip() for b in ALL_BIZARRE_ITEMS])
            needed = 5 * amount
            if bizarre_total < needed:
                return await ctx.send(f"❌ Need {needed} bizarre items (you have {bizarre_total}).")
            removed = 0
            for row in all_items:
                if row["item_name"].strip() in [b.strip() for b in ALL_BIZARRE_ITEMS]:
                    take = min(row["quantity"], needed - removed)
                    await self.bot.db.remove_item(user_id, row["item_name"], take)
                    removed += take
                    if removed >= needed: break
            await self.bot.db.add_item(user_id, "epicRoll", amount)
            await ctx.send(embed=discord.Embed(title="✨ Bizarre Recycling!", description=f"Converted {needed} junk items → **{amount}× Epic Roll**!", color=0x9B59B6))
            await self.bot.db.update_quest_progress(user_id, "daily", "craft", 1)
            return

        # ── Auto-craft (fixed stand requirements e.g. Bites the Dust) ──
        if recipe.get("auto_craft"):
            for req in recipe["requirements"]:
                if "stand" in req:
                    if not await self.bot.db.get_stand_entry(user_id, req["stand"], req.get("stars", 1)):
                        return await ctx.send(f"❌ Missing: **{req['stand']} ★{req.get('stars',1)}**")
            if "cutscene" in recipe and recipe["cutscene"]:
                cm = await ctx.send(recipe["cutscene"])
                await asyncio.sleep(3)
                await cm.delete()
            for req in recipe["requirements"]:
                if "stand" in req:
                    entry = await self.bot.db.get_stand_entry(user_id, req["stand"], req.get("stars", 1))
                    if entry: await self.bot.db.remove_stand(entry["id"])
            reward = recipe["reward"]
            if "stand" in reward:
                await self.bot.db.add_stand(user_id, reward["stand"], 1)
            else:
                await self.bot.db.add_item(user_id, reward["item"], reward["amount"])
            r_name = reward.get("item") or reward.get("stand")
            embed = discord.Embed(title="✨ Crafting Successful!", description=f"Created **{r_name}**!", color=0x57F287)
            if recipe.get("image_url"): embed.set_image(url=recipe["image_url"])
            await ctx.send(embed=embed)
            await self.bot.db.update_quest_progress(user_id, "daily", "craft", 1)
            return

        # ── Normal recipes (item/rarity-based) ──
        for req in recipe["requirements"]:
            need = req["amount"] * amount
            if "item" in req:
                have = await self.bot.db.get_item_count(user_id, req["item"])
                if have < need:
                    return await ctx.send(f"❌ Need {need}× **{req['item']}** (have {have}).")
            else:
                rarity = req.get("rarity")
                stars = req.get("stars", 1)
                entries = await self.bot.db.count_stands_by_rarity(user_id, rarity, stars)
                if len(entries) < need:
                    return await ctx.send(f"❌ Need {need}× **{rarity} ★{stars}** stands (have {len(entries)}).")

        # Remove materials
        for req in recipe["requirements"]:
            need = req["amount"] * amount
            if "item" in req:
                await self.bot.db.remove_item(user_id, req["item"], need)
            else:
                entries = await self.bot.db.count_stands_by_rarity(user_id, req.get("rarity"), req.get("stars", 1))
                for e in entries[:need]:
                    await self.bot.db.remove_stand(e["id"])

        reward = recipe["reward"]
        if "item" in reward:
            await self.bot.db.add_item(user_id, reward["item"], reward["amount"] * amount)
        else:
            for _ in range(reward["amount"] * amount):
                await self.bot.db.add_stand(user_id, reward["stand"], 1)

        r_name = reward.get("item") or reward.get("stand")
        await ctx.send(embed=discord.Embed(title="✨ Crafting Successful!", description=f"Created **{amount}× {r_name}**!", color=0x57F287))
        await self.bot.db.update_quest_progress(user_id, "daily", "craft", 1)

    # ─────────────────────────────────────────────
    # USE ITEM
    # ─────────────────────────────────────────────
    @commands.command(name="use")
    async def use_item(self, ctx, item_name: str = None, *stand_parts):
        """Use a special item on a stand. Usage: Suse <actstone|requiemarrow> <Stand Name>"""
        if not item_name:
            embed = discord.Embed(title="📦 Use Item", description=(
                "`Suse actstone <Stand>` — Evolve Acts (Echoes, Tusk)\n"
                "`Suse requiemarrow <Stand>` — Awaken Requiem"
            ), color=0x3498DB)
            return await ctx.send(embed=embed)

        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        item_norm = normalize(item_name)
        stand_input = " ".join(stand_parts).strip()
        stand_norm = normalize(stand_input)

        if item_norm == "actstone":
            if stand_norm not in ACT_UPGRADES:
                return await ctx.send(f"❌ **{stand_input}** cannot be upgraded with an Act Stone! Valid: {', '.join(ACT_UPGRADES.keys())}")
            if not await self.bot.db.remove_item(user_id, "actStone", 1):
                return await ctx.send("❌ You don't have an **Act Stone**!")
            entry = await self.bot.db.get_stand_entry(user_id, stand_input)
            if not entry: return await ctx.send(f"❌ You don't have **{stand_input}**!")
            info = ACT_UPGRADES[stand_norm]
            if info.get("gif_url"):
                gm = await ctx.send(info["gif_url"])
                await asyncio.sleep(5); await gm.delete()
            await self.bot.db.remove_stand(entry["id"])
            await self.bot.db.add_stand(user_id, info["new_stand"], 1)
            embed = discord.Embed(title=f"✨ {stand_input} Evolved!", description=f"→ **{info['new_stand']}**!", color=0xF1C40F)
            if info.get("image_url"): embed.set_image(url=info["image_url"])
            await ctx.send(embed=embed)

        elif item_norm == "requiemarrow":
            if stand_norm not in REQUIEM_UPGRADES:
                return await ctx.send(f"❌ **{stand_input}** cannot become Requiem! Valid: {', '.join(REQUIEM_UPGRADES.keys())}")
            if not await self.bot.db.remove_item(user_id, "Requiem Arrow", 1):
                return await ctx.send("❌ You don't have a **Requiem Arrow**!")
            entry = await self.bot.db.get_stand_entry(user_id, stand_input)
            if not entry: return await ctx.send(f"❌ You don't have **{stand_input}**!")
            info = REQUIEM_UPGRADES[stand_norm]
            if info.get("gif_url"):
                gm = await ctx.send(info["gif_url"])
                await asyncio.sleep(5); await gm.delete()
            await self.bot.db.remove_stand(entry["id"])
            await self.bot.db.add_stand(user_id, info["new_stand"], 1)
            embed = discord.Embed(title=f"🌟 {stand_input} Awakened!", description=f"**{info['new_stand']}** obtained!", color=0xF1C40F)
            if info.get("image_url"): embed.set_image(url=info["image_url"])
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Unknown item **{item_name}**. Use `actstone` or `requiemarrow`.")

    # ─────────────────────────────────────────────
    # ITEMS
    # ─────────────────────────────────────────────
    @commands.command(name="items", aliases=["inv", "inventory"])
    async def view_items(self, ctx):
        """View your item inventory."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        all_items = await self.bot.db.get_all_items(user_id)
        if not all_items:
            return await ctx.send("🎒 Your item bag is empty.")

        DESC = {
            "rareRoll":       "Use with `Srollrare` — guaranteed Rare+",
            "epicRoll":       "Use with `Srollepic` — guaranteed Epic+",
            "Requiem Arrow":  "Use with `Suse requiemarrow <Stand>`",
            "arrow_fragment": "Collect 5 → craft a Requiem Arrow (`Scraft requiemarrow`)",
            "actStone":       "Use with `Suse actstone <Stand>`",
        }
        embed = discord.Embed(title=f"🎒 {ctx.author.name}'s Items", color=0x3498DB)
        for row in all_items:
            embed.add_field(name=f"×{row['quantity']} {row['item_name']}", value=DESC.get(row["item_name"], "Bizarre collectible"), inline=False)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # COOLDOWN CHECK
    # ─────────────────────────────────────────────
    @commands.command(name="cd", aliases=["cooldown", "scd"])
    async def check_cooldown(self, ctx):
        """Check your current cooldowns."""
        lines = []
        for cmd_name, attr in [("Roll", "roll_stand"), ("Daily", "daily_reward")]:
            cmd = self.bot.get_command(attr.replace("_", ""))
            if cmd is None:
                cmd = self.bot.get_command(cmd_name.lower())
            if cmd and cmd.get_cooldown_retry_after:
                try:
                    cd = cmd.get_cooldown_retry_after(ctx)
                    if cd > 0:
                        h, rem = divmod(int(cd), 3600); m, s = divmod(rem, 60)
                        lines.append(f"**{cmd_name}:** {h}h {m}m {s}s")
                except Exception:
                    pass
        if lines:
            await ctx.send("\n".join(lines))
        else:
            await ctx.send("✅ No active cooldowns!")

    # ─────────────────────────────────────────────
    # BIZARRE DROP (admin trigger / weekend auto)
    # ─────────────────────────────────────────────
    @commands.command(name="bizarredrop")
    @commands.is_owner()
    async def bizarre_drop(self, ctx):
        """Manually trigger a bizarre item drop (owner only)."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        item = random.choice(ALL_BIZARRE_ITEMS)
        await self.bot.db.add_item(user_id, item)
        embed = discord.Embed(title="💥 A SPECIAL ITEM APPEARED!", description=f"You found **{item}**!\n*A relic of the bizarre world...*", color=discord.Color.random())
        embed.set_footer(text="Check your items with Sitems!")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Acquisition(bot))
