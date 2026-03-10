"""
cogs/combat.py — PvP duels (turn-based), D'Arby gambling, rank display
Commands: Sduel, Squadmatch (stub), Srank, Sleaderboard, Sdarby
"""

import discord
import asyncio
import random
from discord.ext import commands

from bot.config import (
    DARBY_STAND, DARBY_WEIGHTS, DARBY_WIN_CHANCE,
    COOLDOWN_DARBY, RARITY_COLORS, PVP_RANKS,
)
from bot.utils.helpers import (
    build_weighted_list, find_stand, normalize, rarity_color, get_pvp_rank, stand_embed
)


# ─────────────────────────────────────────────
# TURN-BASED DUEL
# ─────────────────────────────────────────────
class DuelView(discord.ui.View):
    """Interactive turn-based duel view."""
    ACTIONS = ["⚔️ Attack", "🛡️ Defend", "✨ Ability", "💊 Item"]

    def __init__(self, challenger, opponent, c_stand, o_stand, bot):
        super().__init__(timeout=120)
        self.challenger = challenger
        self.opponent = opponent
        self.c_stand = c_stand
        self.o_stand = o_stand
        self.bot = bot
        self.c_hp = 200
        self.o_hp = 200
        self.turn = 0
        self.choices = {}
        self.message = None

    def hp_bar(self, hp: int, max_hp: int = 200) -> str:
        filled = int((hp / max_hp) * 10)
        return "🟩" * filled + "⬛" * (10 - filled) + f" **{hp}/{max_hp}**"

    def status_embed(self, round_num: int, log_line: str = "") -> discord.Embed:
        embed = discord.Embed(title=f"⚔️ Duel — Round {round_num}", color=0xE74C3C)
        embed.add_field(name=f"{self.challenger.name} ({self.c_stand})", value=self.hp_bar(self.c_hp), inline=False)
        embed.add_field(name=f"{self.opponent.name} ({self.o_stand})", value=self.hp_bar(self.o_hp), inline=False)
        if log_line:
            embed.set_footer(text=log_line)
        return embed

    def action_buttons(self):
        self.clear_items()
        for action in self.ACTIONS:
            btn = discord.ui.Button(label=action, style=discord.ButtonStyle.primary)
            async def cb(interaction: discord.Interaction, a=action):
                uid = str(interaction.user.id)
                if uid not in [str(self.challenger.id), str(self.opponent.id)]:
                    return await interaction.response.send_message("Not your duel!", ephemeral=True)
                if uid in self.choices:
                    return await interaction.response.send_message("Already chose!", ephemeral=True)
                self.choices[uid] = a
                await interaction.response.send_message(f"You chose **{a}**!", ephemeral=True)
                if len(self.choices) == 2:
                    self.stop()
            btn.callback = cb
            self.add_item(btn)


async def run_duel(ctx, challenger, opponent, bot, wager: int = 0):
    db = bot.db
    c_uid = str(challenger.id)
    o_uid = str(opponent.id)

    # Get equipped stand or fall back to any stand
    async def get_fighter_stand(uid):
        player = await db.get_player(uid)
        equipped = player["equipped_stand"] if player else None
        if equipped:
            _, data = find_stand(equipped)
            return equipped, data
        inv = await db.get_inventory(uid)
        stands = [e for e in inv]
        if stands:
            name = stands[0]["stand_name"]
            _, data = find_stand(name)
            return name, data
        return "Bare Fist", {"rarity": "Common", "stars": {"1": ""}, "image": ""}

    c_sname, c_sdata = await get_fighter_stand(c_uid)
    o_sname, o_sdata = await get_fighter_stand(o_uid)

    view = DuelView(challenger, opponent, c_sname, o_sname, bot)
    embed = view.status_embed(0, f"{challenger.name} vs {opponent.name} — Choose your action!")
    view.action_buttons()
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg

    round_num = 0
    winner = loser = None

    while view.c_hp > 0 and view.o_hp > 0:
        round_num += 1
        view.choices = {}
        view.action_buttons()
        await msg.edit(embed=view.status_embed(round_num, "Both players: choose your action!"), view=view)
        await view.wait()

        c_action = view.choices.get(c_uid, "⚔️ Attack")
        o_action = view.choices.get(o_uid, "⚔️ Attack")
        log = f"R{round_num}: {challenger.name} → {c_action} | {opponent.name} → {o_action}"

        # Resolve actions
        def calc_damage(attacker_action, defender_action, attacker_data):
            base = random.randint(25, 45)
            if attacker_action == "✨ Ability":
                base = random.randint(40, 70)
            if defender_action == "🛡️ Defend":
                base = max(5, base // 2)
            return base

        if c_action != "🛡️ Defend" and o_action != "🛡️ Defend":
            view.o_hp -= calc_damage(c_action, o_action, c_sdata)
            view.c_hp -= calc_damage(o_action, c_action, o_sdata)
        elif c_action == "🛡️ Defend":
            view.c_hp -= max(5, calc_damage(o_action, c_action, o_sdata) // 2)
        elif o_action == "🛡️ Defend":
            view.o_hp -= max(5, calc_damage(c_action, o_action, c_sdata) // 2)

        # Stand Rush if HP < 20%
        if view.c_hp < 40 and "Stand Rush" not in str(view.choices.get(c_uid, "")):
            log += " 🔥 STAND RUSH triggered!"
            view.o_hp -= random.randint(20, 40)

        view.c_hp = max(0, view.c_hp)
        view.o_hp = max(0, view.o_hp)

        await msg.edit(embed=view.status_embed(round_num, log), view=view)
        await asyncio.sleep(1.5)

    # Determine winner
    if view.c_hp <= 0 and view.o_hp <= 0:
        winner = random.choice([challenger, opponent])
        loser = opponent if winner == challenger else challenger
    elif view.c_hp <= 0:
        winner, loser = opponent, challenger
    else:
        winner, loser = challenger, opponent

    new_w_elo, new_l_elo = await db.record_duel(str(winner.id), str(loser.id), wager)
    await db.add_exp(str(winner.id), 75)
    await db.add_exp(str(loser.id), 25)
    await db.update_quest_progress(str(winner.id), "daily", "win_duels", 1)

    if wager > 0:
        await db.add_currency(str(winner.id), "hamon", wager)
        await db.deduct_currency(str(loser.id), "hamon", wager)

    result_embed = discord.Embed(
        title=f"🏆 {winner.name} Wins!",
        description=f"{loser.name} has been defeated!\n\n"
                    f"**{winner.name}** ELO: {new_w_elo} (+25)\n"
                    f"**{loser.name}** ELO: {new_l_elo} (-20)" +
                    (f"\n💰 Wager: **{wager} Hamon** transferred!" if wager else ""),
        color=0xF1C40F
    )
    view.clear_items()
    await msg.edit(embed=result_embed, view=view)
    return winner, loser


class Combat(commands.Cog, name="Combat"):
    def __init__(self, bot):
        self.bot = bot
        self._darby_cd = commands.CooldownMapping.from_cooldown(1, COOLDOWN_DARBY, commands.BucketType.user)

    # ─────────────────────────────────────────────
    # DUEL
    # ─────────────────────────────────────────────
    @commands.command(name="duel")
    async def duel(self, ctx, opponent: discord.Member = None, mode: str = "", wager_amount: int = 0):
        """Challenge someone to a duel. Modes: casual, wager <amount>. Usage: Sduel @user [casual|wager amount]"""
        if not opponent or opponent == ctx.author or opponent.bot:
            return await ctx.send("Please mention a valid opponent: `Sduel @user`")

        c_uid = str(ctx.author.id)
        o_uid = str(opponent.id)
        await self.bot.db.ensure_player(c_uid, ctx.author.name)
        await self.bot.db.ensure_player(o_uid, opponent.name)

        is_casual = mode.lower() == "casual"
        wager = wager_amount if mode.lower() == "wager" else 0

        if wager > 0:
            c_player = await self.bot.db.get_player(c_uid)
            if c_player["hamon"] < wager:
                return await ctx.send(f"❌ You don't have {wager} Hamon to wager!")

        # Challenge message
        embed = discord.Embed(
            title="⚔️ Duel Challenge!",
            description=f"{ctx.author.mention} challenges {opponent.mention}!\n"
                        + (f"Mode: **Casual** (no ELO)" if is_casual else f"Mode: **Ranked**")
                        + (f"\nWager: **{wager} Hamon**" if wager else "")
                        + "\n\nReact ✅ to accept or ❌ to decline.",
            color=0xE74C3C
        )
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅"); await msg.add_reaction("❌")

        def check(r, u): return u == opponent and r.message.id == msg.id and str(r.emoji) in ("✅","❌")
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("Duel challenge timed out.")
        if str(reaction.emoji) == "❌":
            return await ctx.send(f"{opponent.name} declined the duel.")

        if is_casual:
            await run_duel(ctx, ctx.author, opponent, self.bot, 0)
        else:
            await run_duel(ctx, ctx.author, opponent, self.bot, wager)

    # ─────────────────────────────────────────────
    # SPAR (no-stakes)
    # ─────────────────────────────────────────────
    @commands.command(name="spar")
    async def spar(self, ctx, opponent: discord.Member = None):
        """Friendly no-ELO spar for training EXP."""
        if not opponent or opponent == ctx.author or opponent.bot:
            return await ctx.send("Mention a valid opponent: `Sspar @user`")
        await self.bot.db.ensure_player(str(ctx.author.id), ctx.author.name)
        await self.bot.db.ensure_player(str(opponent.id), opponent.name)
        await ctx.send(f"🥊 Friendly spar: {ctx.author.mention} vs {opponent.mention}!")
        winner, loser = await run_duel(ctx, ctx.author, opponent, self.bot, 0)
        await self.bot.db.add_exp(str(ctx.author.id), 30)
        await self.bot.db.add_exp(str(opponent.id), 30)
        await ctx.send(f"💪 Both players earned training EXP from the spar!")

    # ─────────────────────────────────────────────
    # RANK
    # ─────────────────────────────────────────────
    @commands.command(name="rank")
    async def rank(self, ctx, member: discord.Member = None):
        """View your or another player's PvP rank."""
        target = member or ctx.author
        uid = str(target.id)
        await self.bot.db.ensure_player(uid, target.name)
        player = await self.bot.db.get_player(uid)
        tier, title = get_pvp_rank(player["elo"])
        embed = discord.Embed(title=f"🏅 {target.name}'s Rank", color=0xF1C40F)
        embed.add_field(name="Rank", value=f"**{tier} — {title}**", inline=True)
        embed.add_field(name="ELO", value=f"**{player['elo']}**", inline=True)
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # LEADERBOARD
    # ─────────────────────────────────────────────
    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx):
        """Show the top 20 PvP players."""
        rows = await self.bot.db.get_pvp_leaderboard(20)
        embed = discord.Embed(title="🏆 PvP Leaderboard", color=0xF1C40F)
        for i, row in enumerate(rows, 1):
            tier, title = get_pvp_rank(row["elo"])
            embed.add_field(name=f"#{i} {row['username']}", value=f"{tier} — {title} | ELO: {row['elo']}", inline=False)
        if not rows:
            embed.description = "No ranked players yet!"
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # D'ARBY GAMBLING
    # ─────────────────────────────────────────────
    @commands.command(name="darby")
    async def darbysoul(self, ctx, *, bet: str = None):
        """Gamble with D'Arby the Gambler (requires ★2 Osiris)."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)

        # Check Osiris requirement
        inv = await self.bot.db.get_inventory(user_id)
        has_osiris = any(
            normalize(e["stand_name"]) == normalize(DARBY_STAND) and e["stars"] >= 2
            for e in inv
        )
        if not has_osiris:
            embed = discord.Embed(title="🚫 Gambling Parlor Locked", description='*"You\'re not worthy to face me yet!"*\n\n**Requires:** ★2 Osiris', color=0xFF0000)
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1354650264916852736/1357902139539849306/toss-coin-flip-ezgif.com-optimize.gif")
            return await ctx.send(embed=embed)

        # Help / list
        if not bet or bet.lower() in ("help", "menu", "info"):
            embed = discord.Embed(title="🎴 D'Arby's HIGH-ROLLER Parlor", color=0x8B0000)
            embed.add_field(name="Win Rates", value="```diff\n+ Common:    30%\n+ Rare:      40%\n+ Epic:      50%\n+ Legendary: 60%\n+ Mythical:  80%\n```", inline=False)
            embed.add_field(name="Commands", value="`Sdarby <stand/item>` — Bet something\n`Sdarby random` — Random bet\n`Sdarby list` — View available bets", inline=False)
            return await ctx.send(embed=embed)

        if bet.lower() == "list":
            stands_list = [f"{e['stand_name']} ★{e['stars']}" for e in inv if e["stars"] == 1]
            items_list = [f"{r['item_name']} ×{r['quantity']}" for r in await self.bot.db.get_all_items(user_id)]
            all_bets = stands_list + items_list
            if not all_bets:
                return await ctx.send("You have nothing to bet!")
            embed = discord.Embed(title="Available Bets", description="\n".join(all_bets[:20]), color=0x4B0082)
            return await ctx.send(embed=embed)

        # Cooldown check
        bucket = self._darby_cd.get_bucket(ctx.message)
        retry = bucket.get_retry_after()
        if retry > 0:
            m, s = divmod(int(retry), 60)
            return await ctx.send(embed=discord.Embed(title="⏳ Cooldown", description=f"Try again in {m}m {s}s!", color=0xFFA500))

        # Random bet
        if bet.lower() == "random":
            confirm = await ctx.send("⚠️ This will bet a **random** stand or item! React ✅ to confirm or ❌ to cancel.")
            await confirm.add_reaction("✅"); await confirm.add_reaction("❌")
            def check(r, u): return u == ctx.author and r.message.id == confirm.id and str(r.emoji) in ("✅","❌")
            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=30, check=check)
            except asyncio.TimeoutError:
                await confirm.delete()
                return await ctx.send("Bet cancelled.")
            if str(reaction.emoji) == "❌":
                await confirm.delete()
                return await ctx.send("Bet cancelled.")
            await confirm.delete()

            possible = [(e["stand_name"], "stand", e) for e in inv if e["stars"] == 1]
            for r in await self.bot.db.get_all_items(user_id):
                possible.append((r["item_name"], "item", r))
            if not possible:
                return await ctx.send("You have nothing to bet!")
            bet_name, bet_type, bet_entry = random.choice(possible)
        else:
            # Specific bet
            bet_name, bet_type, bet_entry = None, None, None
            norm_bet = normalize(bet)
            for e in inv:
                if normalize(e["stand_name"]) == norm_bet and e["stars"] == 1:
                    bet_name, bet_type, bet_entry = e["stand_name"], "stand", e
                    break
            if not bet_name:
                for r in await self.bot.db.get_all_items(user_id):
                    if normalize(r["item_name"]) == norm_bet and r["quantity"] > 0:
                        bet_name, bet_type, bet_entry = r["item_name"], "item", r
                        break
            if not bet_name:
                return await ctx.send(f"❌ You don't have **{bet}** to bet (must be ★1 stand or item).")

        # Determine win chance
        from bot.utils.helpers import get_stand_rarity
        if bet_type == "stand":
            rarity = get_stand_rarity(bet_name) or "Common"
        else:
            rarity = "Epic"
        win_chance = DARBY_WIN_CHANCE.get(rarity, 0.50)

        embed = discord.Embed(title="🎲 D'Arby Accepts Your Bet!", description=f'*"{bet_name}... interesting choice."*', color=0x4B0082)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(2)

        player_wins = random.random() < win_chance

        if player_wins:
            pool = build_weighted_list(DARBY_WEIGHTS)
            won_name, won_data = random.choice(pool)
            await self.bot.db.add_stand(user_id, won_name, 1)
            embed = discord.Embed(title="✨ You Win!", description=f"You keep your **{bet_name}** and win:", color=0x00FF00)
            embed.add_field(name="Prize", value=f"{won_data.get('emoji','')} {won_name} ({won_data['rarity']})", inline=False)
            img = won_data.get("stars", {}).get("1") or won_data.get("image", "")
            if img: embed.set_image(url=img)
        else:
            if bet_type == "stand":
                await self.bot.db.remove_stand(bet_entry["id"])
            else:
                await self.bot.db.remove_item(user_id, bet_name, 1)
            embed = discord.Embed(title="💀 You Lose!", description=f"Your **{bet_name}** is now D'Arby's property!", color=0xFF0000)

        await msg.edit(embed=embed)
        bucket.update_rate_limit()


async def setup(bot):
    await bot.add_cog(Combat(bot))
