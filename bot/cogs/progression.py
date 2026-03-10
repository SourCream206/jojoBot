"""
cogs/progression.py — Stand inventory, profiles, training, stands command
Commands: Sstands, Sprofile, Sstat, Sequip, Strain, Sstandby, Squests, Sachievements
"""

import discord
import asyncio
import random
from discord.ext import commands

from bot.config import (
    COOLDOWN_TRAIN, COOLDOWN_STANDBY,
    TRAIN_HAMON_COST, TRAIN_STAT_GAIN, STAT_DISPLAY, MAX_TRAIN_BY_POTENTIAL,
    STAT_NAMES, CURRENCY_HAMON, DAILY_QUEST_POOL, WEEKLY_QUEST_POOL,
    RARITY_COLORS,
)
from bot.utils.helpers import find_stand, normalize, get_pvp_rank, rarity_color, load_stands


# ─────────────────────────────────────────────
# Stand Collection Dropdown / View
# ─────────────────────────────────────────────
class StandSelect(discord.ui.Select):
    def __init__(self, options, db, user_id):
        super().__init__(placeholder="Select a stand to view...", options=options[:25])
        self.db = db
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        stand_name = self.values[0]
        canonical, data = find_stand(stand_name)
        if not data:
            return await interaction.response.send_message("Stand not found.", ephemeral=True)
        inv = await self.db.get_inventory(self.user_id)
        copies = [e for e in inv if normalize(e["stand_name"]) == normalize(stand_name)]
        stars_owned = sorted(set(e["stars"] for e in copies))

        embed = discord.Embed(title=f"{canonical}", description=f"**Rarity:** {data.get('rarity','?')}", color=rarity_color(data.get("rarity", "Common")))
        img = data.get("stars", {}).get(str(stars_owned[-1] if stars_owned else 1), "") or data.get("image","")
        if img: embed.set_image(url=img)
        star_text = " | ".join([f"★{s} ×{sum(1 for e in copies if e['stars']==s)}" for s in stars_owned])
        embed.add_field(name="Owned", value=star_text or "None")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class StandCollectionView(discord.ui.View):
    def __init__(self, pages, db, user_id):
        super().__init__(timeout=180)
        self.pages = pages
        self.db = db
        self.user_id = user_id
        self.current = 0
        self._build()

    def _build(self):
        self.clear_items()
        page_data = self.pages[self.current]
        if page_data.get("stands"):
            opts = []
            for name, data, star_counts in page_data["stands"][:25]:
                opts.append(discord.SelectOption(label=name[:100], description=f"{data.get('rarity','?')} Stand"))
            if opts:
                self.add_item(StandSelect(opts, self.db, self.user_id))

        if self.current > 0:
            prev_btn = discord.ui.Button(label="◄ Prev", style=discord.ButtonStyle.grey, row=1)
            async def prev_cb(interaction):
                self.current -= 1
                self._build()
                await interaction.response.edit_message(embed=self.pages[self.current]["embed"], view=self)
            prev_btn.callback = prev_cb
            self.add_item(prev_btn)

        if self.current < len(self.pages) - 1:
            next_btn = discord.ui.Button(label="Next ►", style=discord.ButtonStyle.grey, row=1)
            async def next_cb(interaction):
                self.current += 1
                self._build()
                await interaction.response.edit_message(embed=self.pages[self.current]["embed"], view=self)
            next_btn.callback = next_cb
            self.add_item(next_btn)


class Progression(commands.Cog, name="Progression"):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────────
    # STANDS / INVENTORY
    # ─────────────────────────────────────────────
    @commands.command(name="stands", aliases=["stand", "standinv", "si"])
    async def view_stands(self, ctx, member: discord.Member = None):
        """View your stand collection."""
        target = member or ctx.author
        uid = str(target.id)
        await self.bot.db.ensure_player(uid, target.name)
        inv = await self.bot.db.get_inventory(uid)
        if not inv:
            return await ctx.send(f"{target.name} has no stands yet. Use `Sroll` to get started!")

        # Group stands
        stand_records = {}
        for e in inv:
            name = e["stand_name"]
            s = e["stars"]
            if name not in stand_records:
                stand_records[name] = {}
            stand_records[name][s] = stand_records[name].get(s, 0) + 1

        part_stands = load_stands()
        pages = []

        for part_name, part_data in part_stands.items():
            if "skags" in part_name.lower():
                has = any(normalize(k) in [normalize(s) for s in stand_records] for k in part_data)
                if not has:
                    continue

            premium, common = [], []
            for sname, sdata in part_data.items():
                if sname in stand_records:
                    entry = (sname, sdata, stand_records[sname])
                    (common if sdata["rarity"] == "Common" else premium).append(entry)

            if not premium and not common:
                continue

            for label, group, color in [("Premium", premium, 0x9B59B6), ("Common", common, 0x57F287)]:
                if not group:
                    continue
                embed = discord.Embed(title=f"{target.name}'s {part_name.split(':')[0]} — {label}", color=color)
                for rarity in (["mythical", "Legendary", "Epic", "Rare"] if label == "Premium" else ["Common"]):
                    stands = [(n, d, sc) for n, d, sc in group if d["rarity"] == rarity]
                    if stands:
                        lines = []
                        for sname, sdata, star_counts in stands:
                            star_text = " ".join(f"★{lv}×{cnt}" for lv, cnt in sorted(star_counts.items()))
                            lines.append(f"{sdata.get('emoji','')}{sname} {star_text}")
                        embed.add_field(name=f"**{rarity}**", value="\n".join(lines[:15]), inline=False)
                pages.append({"embed": embed, "stands": group})

        if not pages:
            return await ctx.send("No stand data available.")

        view = StandCollectionView(pages, self.bot.db, uid)
        await ctx.send(embed=pages[0]["embed"], view=view)

    # ─────────────────────────────────────────────
    # PROFILE
    # ─────────────────────────────────────────────
    @commands.command(name="profile", aliases=["prof", "p"])
    async def profile(self, ctx, member: discord.Member = None):
        """View your or another player's full profile."""
        target = member or ctx.author
        uid = str(target.id)
        await self.bot.db.ensure_player(uid, target.name)
        player = await self.bot.db.get_player(uid)
        tier, title = get_pvp_rank(player["elo"])
        inv = await self.bot.db.get_inventory(uid)
        achievements = await self.bot.db.get_achievements(uid)

        embed = discord.Embed(title=f"👤 {target.name}'s Profile", color=0x3498DB)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{player['level']}** | {player['exp']} EXP", inline=True)
        embed.add_field(name="Rank", value=f"**{tier} — {title}** | {player['elo']} ELO", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="💰 Hamon", value=str(player["hamon"]), inline=True)
        embed.add_field(name="🔥 Stand Dust", value=str(player["stand_dust"]), inline=True)
        embed.add_field(name="💎 SOS Shards", value=str(player["sos_shards"]), inline=True)
        embed.add_field(name="📦 Stands", value=str(len(inv)), inline=True)
        embed.add_field(name="🏅 Achievements", value=str(len(achievements)), inline=True)
        embed.add_field(name="🎯 Pity Counter", value=f"{player['pity_count']}/50", inline=True)

        equipped = player.get("equipped_stand")
        if equipped:
            embed.add_field(name="⚔️ Equipped Stand", value=f"**{equipped}**", inline=False)

        if achievements:
            embed.add_field(name="Recent Achievements", value="\n".join(f"🏅 {a['achievement_id']}" for a in achievements[-3:]), inline=False)

        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # EQUIP
    # ─────────────────────────────────────────────
    @commands.command(name="equip")
    async def equip(self, ctx, *, stand_name: str = None):
        """Equip a stand as your active combat stand."""
        if not stand_name:
            return await ctx.send("Usage: `Sequip <Stand Name>`")
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        canonical, data = find_stand(stand_name)
        if not canonical:
            return await ctx.send(f"❌ Stand **{stand_name}** not found.")
        entry = await self.bot.db.get_stand_entry(user_id, canonical)
        if not entry:
            return await ctx.send(f"❌ You don't own **{canonical}**!")
        await self.bot.db.update_player(user_id, equipped_stand=canonical)
        await ctx.send(f"✅ **{canonical}** is now your equipped stand!")

    # ─────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────
    @commands.command(name="stat", aliases=["stats", "standstats"])
    async def stand_stats(self, ctx, *, stand_name: str = None):
        """View a stand's stat card (persistent, seeded once per stand). Usage: Sstat <Stand Name>"""
        if not stand_name:
            return await ctx.send("Usage: `Sstat <Stand Name>`")
        user_id = str(ctx.author.id)
        canonical, data = find_stand(stand_name)
        if not canonical:
            return await ctx.send(f"❌ Stand **{stand_name}** not found.")

        rarity = data.get("rarity", "Common")

        # Try to get the player's specific copy so we can show trained bonuses too
        entry = await self.bot.db.get_stand_entry(user_id, canonical)

        if entry:
            stats = await self.bot.db.get_full_stats(entry["id"], canonical, rarity)
            base  = await self.bot.db.get_base_stats(canonical)
            owned = True
        else:
            # Still seed + show archetype stats even if the viewer doesn't own it
            stats = await self.bot.db.seed_base_stats(canonical, rarity)
            base  = stats
            owned = False

        grades = ["E", "D", "C", "B", "A"]
        embed = discord.Embed(
            title=f"📊 {canonical} — Stat Card",
            description=f"**Rarity:** {rarity}" + ("" if owned else "\n*(showing archetype stats — you don't own this stand)*"),
            color=rarity_color(rarity)
        )

        for stat in STAT_NAMES:
            total = min(5, stats[stat])
            base_val = min(5, base[stat])
            trained_bonus = total - base_val
            grade = grades[total - 1] if total >= 1 else "E"
            bonus_text = f" *(+{trained_bonus} trained)*" if trained_bonus > 0 else ""
            embed.add_field(
                name=STAT_DISPLAY[stat],
                value=f"**{grade}**{bonus_text}",
                inline=True
            )

        if owned:
            pot = base.get("development_potential", 1)
            from bot.config import MAX_TRAIN_BY_POTENTIAL
            cap = MAX_TRAIN_BY_POTENTIAL.get(pot, 1)
            embed.set_footer(text=f"Train cap: {cap} sessions per stat | Use Strain <stat> to improve")

        img = data.get("stars", {}).get("1") or data.get("image", "")
        if img:
            embed.set_image(url=img)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # TRAIN
    # ─────────────────────────────────────────────
    @commands.command(name="train")
    @commands.cooldown(1, COOLDOWN_TRAIN, commands.BucketType.user)
    async def train(self, ctx, stat: str = None):
        """Train your equipped stand's stats. Usage: Strain <stat_name>"""
        # Build a lowercase alias map  e.g. "dp" → "destructive_power"
        stat_aliases = {
            "dp": "destructive_power", "power": "destructive_power", "destructive_power": "destructive_power",
            "sp": "speed", "speed": "speed",
            "rng": "range", "range": "range",
            "sta": "stamina", "stamina": "stamina",
            "pre": "precision", "precision": "precision",
            "pot": "development_potential", "potential": "development_potential", "development_potential": "development_potential",
        }

        if not stat:
            lines = "\n".join(f"`{alias}` → {STAT_DISPLAY[full]}" for alias, full in stat_aliases.items() if alias == full)
            return await ctx.send(
                f"Usage: `Strain <stat>`\n\nStats you can train:\n"
                + "\n".join(f"• `{alias}` — {STAT_DISPLAY[full]}" for alias, full in [
                    ("dp","destructive_power"),("speed","speed"),("range","range"),
                    ("stamina","stamina"),("precision","precision"),("pot","development_potential")
                ])
            )

        stat_key = stat_aliases.get(stat.lower().replace(" ","_").replace("-","_"))
        if not stat_key:
            return await ctx.send(f"❌ Unknown stat `{stat}`. Use: dp, speed, range, stamina, precision, pot")

        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        player = await self.bot.db.get_player(user_id)

        if not player["equipped_stand"]:
            return await ctx.send("❌ Equip a stand first with `Sequip <Stand Name>`.")
        if player["hamon"] < TRAIN_HAMON_COST:
            return await ctx.send(f"❌ Need **{TRAIN_HAMON_COST} Hamon** to train! You have {player['hamon']}.")

        stand_name = player["equipped_stand"]
        _, stand_data = find_stand(stand_name)
        if not stand_data:
            return await ctx.send(f"❌ Stand **{stand_name}** not found in the stand roster.")

        rarity = stand_data.get("rarity", "Common")
        entry = await self.bot.db.get_stand_entry(user_id, stand_name)
        if not entry:
            return await ctx.send(f"❌ You no longer have **{stand_name}** in your inventory!")

        result = await self.bot.db.train_stand_stat(entry["id"], stand_name, rarity, stat_key)

        if not result["success"]:
            if result["reason"] == "cap_reached":
                return await ctx.send(
                    f"🚫 **{stand_name}**'s `{STAT_DISPLAY[stat_key]}` is maxed out! "
                    f"(Cap: {result['cap']} training sessions, total: {result['total']})"
                )
            return await ctx.send(f"❌ Training failed: {result['reason']}")

        await self.bot.db.deduct_currency(user_id, CURRENCY_HAMON, TRAIN_HAMON_COST)
        await self.bot.db.add_exp(user_id, 35)
        await self.bot.db.update_quest_progress(user_id, "daily", "train", 1)

        grades = ["E", "D", "C", "B", "A"]
        new_grade = grades[min(4, result["new_val"] - 1)]

        embed = discord.Embed(
            title="💪 Training Complete!",
            description=(
                f"**{stand_name}** trained **{STAT_DISPLAY[stat_key]}**!\n"
                f"New grade: **{new_grade}** (total: {result['new_val']})\n"
                f"Sessions used: {result['trained']}/{result['cap']}\n\n"
                f"Spent: **{TRAIN_HAMON_COST} Hamon** | Gained: **+35 EXP**"
            ),
            color=0x57F287
        )
        await ctx.send(embed=embed)

    @train.error
    async def train_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            h, rem = divmod(int(error.retry_after), 3600); m, s = divmod(rem, 60)
            await ctx.send(f"⏳ Training cooldown: **{h}h {m}m {s}s** remaining.")

    # ─────────────────────────────────────────────
    # STANDBY
    # ─────────────────────────────────────────────
    @commands.command(name="standby")
    @commands.cooldown(1, COOLDOWN_STANDBY, commands.BucketType.user)
    async def standby(self, ctx):
        """Put your stand on 8-hour passive training."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        player = await self.bot.db.get_player(user_id)
        if not player["equipped_stand"]:
            return await ctx.send("❌ No stand equipped! Use `Sequip <Stand Name>`")
        await self.bot.db.add_exp(user_id, 50)
        embed = discord.Embed(
            title="💤 Stand on Standby",
            description=f"**{player['equipped_stand']}** is passively training for 8 hours.\nYou'll gain **+50 EXP** when training completes.",
            color=0x3498DB
        )
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # QUESTS
    # ─────────────────────────────────────────────
    @commands.command(name="quests", aliases=["quest", "q"])
    async def quests(self, ctx, mode: str = "daily"):
        """View your active quests. Usage: Squests [daily|weekly|story]"""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)

        pool = DAILY_QUEST_POOL if mode.lower() == "daily" else WEEKLY_QUEST_POOL
        rows = await self.bot.db.get_active_quests(user_id, mode.lower())

        if not rows:
            # Auto-assign if empty
            sample = random.sample(pool, min(3, len(pool)))
            for q in sample:
                await self.bot.db.assign_quest(user_id, q["id"], mode.lower())
            rows = await self.bot.db.get_active_quests(user_id, mode.lower())

        embed = discord.Embed(title=f"📋 {mode.title()} Quests", color=0x3498DB)
        for row in rows:
            quest_def = next((q for q in pool if q["id"] == row["quest_id"]), None)
            if not quest_def:
                continue
            target = quest_def["target"]
            prog = row["progress"]
            done = "✅" if row["completed"] else f"({prog}/{target})"
            reward_parts = []
            if quest_def.get("reward_hamon"): reward_parts.append(f"{quest_def['reward_hamon']} Hamon")
            if quest_def.get("reward_exp"): reward_parts.append(f"{quest_def['reward_exp']} EXP")
            if quest_def.get("reward_dust"): reward_parts.append(f"{quest_def['reward_dust']} Dust")
            embed.add_field(
                name=f"{done} {quest_def['title']}",
                value=f"{quest_def['desc']}\nReward: {', '.join(reward_parts)}",
                inline=False
            )
        if not embed.fields:
            embed.description = "No active quests! Use `Sdaily` to refresh."
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # ACHIEVEMENTS
    # ─────────────────────────────────────────────
    @commands.command(name="achievements", aliases=["ach"])
    async def achievements(self, ctx, member: discord.Member = None):
        """View your achievements."""
        target = member or ctx.author
        uid = str(target.id)
        await self.bot.db.ensure_player(uid, target.name)
        ach = await self.bot.db.get_achievements(uid)
        embed = discord.Embed(title=f"🏅 {target.name}'s Achievements", color=0xF1C40F)
        if not ach:
            embed.description = "No achievements yet — keep playing to earn them!"
        else:
            for a in ach:
                embed.add_field(name=f"🏅 {a['achievement_id']}", value=f"Earned: {str(a['earned_at'])[:10]}", inline=True)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # COMPENDIUM
    # ─────────────────────────────────────────────
    @commands.command(name="compendium", aliases=["comp"])
    async def compendium(self, ctx):
        """View your stand collection completion progress."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        inv = await self.bot.db.get_inventory(user_id)
        owned = set(normalize(e["stand_name"]) for e in inv)

        part_stands = load_stands()
        total = sum(len(v) for v in part_stands.values())
        found = sum(1 for part in part_stands.values() for sname in part if normalize(sname) in owned)
        pct = int(found / total * 100) if total else 0

        embed = discord.Embed(title="📖 Stand Compendium", description=f"**{found}/{total} stands** discovered ({pct}%)", color=0x3498DB)
        bar = "🟩" * (pct // 10) + "⬛" * (10 - pct // 10)
        embed.add_field(name="Progress", value=bar, inline=False)
        if pct >= 100:
            embed.add_field(name="🌟 Title Unlocked!", value="**Bizarre Encyclopedia** — +10% roll luck!", inline=False)
        elif pct >= 50:
            embed.add_field(name="🌟 Title Unlocked!", value="**Stand Fan** — Keep going!", inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Progression(bot))
