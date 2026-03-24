"""
cogs/battle.py
Sbattle — start a PvE or PvP battle.
Sleaderboard — show win count and power score leaderboards.
"""

import discord
from discord.ext import commands
import random

from src.db import client as db
from src.battle.engine import BattleSession, BattleView
from src.battle.stand_stats import make_stand, STAND_CATALOG
from src.battle.stand import compute_power_score


# ── PvE enemy definitions per area ────────────────────────────────────────────

PVE_ENEMIES = {
    "Cairo": [
        {"name": "DIO",           "stand": "The World",     "level": 15, "is_boss": True},
        {"name": "N'Doul",        "stand": "Geb",           "level": 8,  "is_boss": False},
        {"name": "Caravan Guard", "stand": "Hermit Purple",  "level": 4,  "is_boss": False},
    ],
    "Morioh Town": [
        {"name": "Yoshikage Kira", "stand": "Killer Queen",  "level": 25, "is_boss": True},
        {"name": "Akira Otoishi",  "stand": "Red Hot Chili Pepper", "level": 14, "is_boss": False},
        {"name": "Toshikazu Hazamada", "stand": "Surface",   "level": 10, "is_boss": False},
    ],
    "Italy": [
        {"name": "Diavolo",        "stand": "King Crimson",  "level": 35, "is_boss": True},
        {"name": "Ghiaccio",       "stand": "White Album",   "level": 22, "is_boss": False},
        {"name": "Illuso",         "stand": "Man in the Mirror", "level": 18, "is_boss": False},
    ],
    "Philadelphia": [
        {"name": "Funny Valentine", "stand": "D4C",          "level": 42, "is_boss": True},
        {"name": "Sandman",         "stand": "Sand Man's Stand", "level": 30, "is_boss": False},
        {"name": "Ringo Roadagain", "stand": "Mandom",       "level": 28, "is_boss": False},
    ],
    "Morioh SBR": [
        {"name": "Tooru",           "stand": "Wonder of U",  "level": 48, "is_boss": True},
        {"name": "Urban Guerrilla", "stand": "Doremifasolati Do", "level": 38, "is_boss": False},
        {"name": "Poor Tom",        "stand": "Tomb of the Boom", "level": 35, "is_boss": False},
    ],
}


class Battle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Sbattle ───────────────────────────────────────────────────────────────

    @commands.command(name="battle", aliases=["fight", "duel", "b"])
    async def sbattle(self, ctx: commands.Context, target: discord.Member = None):
        """
        Start a battle.
        - Sbattle         → fight a random PvE enemy in your area
        - Sbattle @user   → challenge another player (requires their acceptance)
        """
        user_id = str(ctx.author.id)
        user = await db.get_or_create_user(user_id, ctx.author.name)

        # Check if already in battle
        existing = await db.get_active_battle_for_user(user_id)
        if existing:
            await ctx.reply("You're already in a battle!", mention_author=False)
            return

        # PvE cooldown (3 minutes) — PvP has no cooldown
        if not target:
            from datetime import datetime, timezone
            expires = await db.get_cooldown(user_id, "sbattle")
            if expires:
                remaining = (expires - datetime.now(timezone.utc)).total_seconds()
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                await ctx.reply(
                    f"⏳ Battle cooldown! Try again in **{mins}m {secs}s**.",
                    mention_author=False,
                )
                return

        primary = await db.get_primary_stand(user_id)
        if not primary:
            await ctx.reply(
                "You don't have a primary stand equipped! Use `Sequip <stand name>` first.",
                mention_author=False,
            )
            return

        if primary["stand_name"] not in STAND_CATALOG:
            await ctx.reply(
                f"**{primary['stand_name']}** doesn't have battle data yet.",
                mention_author=False,
            )
            return

        # ── PvP ──
        if target:
            if target.bot or target.id == ctx.author.id:
                await ctx.reply("You can't challenge that user.", mention_author=False)
                return

            target_id = str(target.id)
            target_user = await db.get_user(target_id)
            if not target_user:
                await ctx.reply("That player hasn't registered yet.", mention_author=False)
                return

            # Check if target is in a battle
            target_battle = await db.get_active_battle_for_user(target_id)
            if target_battle:
                # Queue the challenge
                await db.queue_battle_challenge(user_id, target_id)
                await ctx.reply(
                    f"**{target.name}** is in a battle. Your challenge has been queued — "
                    f"they'll be notified when they're free!",
                    mention_author=False,
                )
                return

            # Send challenge embed with Accept/Decline
            view = ChallengeView(ctx, user_id, target_id, primary)
            embed = discord.Embed(
                title="⚔️ Battle Challenge!",
                description=(
                    f"{ctx.author.mention} challenges {target.mention} to a battle!\n"
                    f"Stand: **{primary['stand_name']}** Lv.{primary['level']} ★{primary['stars']}"
                ),
                color=0xFF4444,
            )
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            return

        # ── PvE ──
        area    = user["current_area"]
        enemies = PVE_ENEMIES.get(area, [])
        if not enemies:
            await ctx.reply("No enemies in this area yet!", mention_author=False)
            return

        enemy_data = random.choice(enemies)
        enemy_stand_name = enemy_data["stand"]

        if enemy_stand_name not in STAND_CATALOG:
            await ctx.reply(
                f"Enemy stand **{enemy_stand_name}** has no battle data yet.",
                mention_author=False,
            )
            return

        attacker_stand = make_stand(
            primary["stand_name"], primary["level"], primary["stars"], primary.get("is_shiny", False)
        )
        # PvE: scale enemy level slightly to player
        base_level = enemy_data["level"]
        enemy_level = base_level + max(0, (primary["level"] - base_level) // 4)
        defender_stand = make_stand(enemy_stand_name, enemy_level, 1)

        session = BattleSession(
            attacker_id    = user_id,
            defender_id    = None,
            attacker_stand = attacker_stand,
            defender_stand = defender_stand,
            is_pvp         = False,
            is_boss        = enemy_data["is_boss"],
        )

        # Snapshot to DB
        battle_row = await db.create_active_battle(
            attacker_id  = user_id,
            defender_id  = None,
            attacker_hp  = attacker_stand.current_hp,
            defender_hp  = defender_stand.current_hp,
            turn         = "attacker",
            state        = {},
            is_pvp       = False,
        )
        session.db_battle_id = battle_row["id"]

        view  = BattleView(session, ctx)
        embed = _battle_start_embed(
            attacker_name  = ctx.author.name,
            attacker_stand = attacker_stand,
            defender_name  = enemy_data["name"],
            defender_stand = defender_stand,
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ── Sleaderboard ──────────────────────────────────────────────────────────

    @commands.command(name="leaderboard", aliases=["lb", "top", "ranking"])
    async def sleaderboard(self, ctx: commands.Context, tab: str = "wins"):
        """
        View the leaderboard.
        - Sleaderboard wins   → top players by win count
        - Sleaderboard power  → top players by stand power score
        """
        tab = tab.lower()
        if tab not in ("wins", "power"):
            await ctx.reply("Usage: `Sleaderboard wins` or `Sleaderboard power`", mention_author=False)
            return

        if tab == "wins":
            rows = await db.get_win_leaderboard(10)
            embed = discord.Embed(title="🏆 Win Leaderboard", color=0xF1C40F)
            for i, row in enumerate(rows, 1):
                embed.add_field(
                    name=f"{i}. {row['username']}",
                    value=f"{row['win_count']}W / {row['loss_count']}L",
                    inline=False,
                )
        else:
            rows = await db.get_power_leaderboard(10)
            embed = discord.Embed(title="💪 Power Leaderboard", color=0xFF4444)
            for i, row in enumerate(rows, 1):
                score = compute_power_score(row)
                username = row.get("users", {}).get("username", "Unknown") if isinstance(row.get("users"), dict) else "Unknown"
                embed.add_field(
                    name=f"{i}. {username}",
                    value=f"**{row['stand_name']}** — Power: {score:,}",
                    inline=False,
                )

        await ctx.reply(embed=embed, mention_author=False)

    # ── Pending challenges notification ───────────────────────────────────────

    @commands.command(name="challenges", aliases=["pending", "inbox"])
    async def schallenges(self, ctx: commands.Context):
        """View pending PvP challenges against you."""
        user_id = str(ctx.author.id)
        await db.get_or_create_user(user_id, ctx.author.name)
        pending = await db.get_pending_challenges(user_id)

        if not pending:
            await ctx.reply("No pending challenges!", mention_author=False)
            return

        embed = discord.Embed(title="⚔️ Pending Challenges", color=0xFF4444)
        for c in pending:
            challenger = await ctx.bot.fetch_user(int(c["challenger_id"]))
            embed.add_field(
                name=f"From {challenger.name}",
                value=f"Challenge ID: `{c['id']}` | Use `Saccept {c['id']}` or `Sdecline {c['id']}`",
                inline=False,
            )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="accept")
    async def saccept(self, ctx: commands.Context, challenge_id: int):
        """Accept a pending PvP challenge. Usage: Saccept <id>"""
        # Full PvP acceptance flow — abbreviated here, mirrors sbattle PvP logic
        await db.update_challenge_status(challenge_id, "accepted")
        await ctx.reply(f"✅ Challenge {challenge_id} accepted! Starting battle...", mention_author=False)
        # TODO: instantiate full PvP BattleSession here (same as sbattle PvP branch)

    @commands.command(name="decline")
    async def sdecline(self, ctx: commands.Context, challenge_id: int):
        """Decline a pending PvP challenge. Usage: Sdecline <id>"""
        await db.update_challenge_status(challenge_id, "declined")
        await ctx.reply(f"❌ Challenge {challenge_id} declined.", mention_author=False)


# ── Challenge accept/decline view ─────────────────────────────────────────────

class ChallengeView(discord.ui.View):
    def __init__(self, ctx, challenger_id: str, target_id: str, challenger_primary: dict):
        super().__init__(timeout=120)
        self.ctx                = ctx
        self.challenger_id      = challenger_id
        self.target_id          = target_id
        self.challenger_primary = challenger_primary
        self.message            = None

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return

        target_primary = await db.get_primary_stand(self.target_id)
        if not target_primary:
            await interaction.response.send_message(
                "You don't have a primary stand! Use `Sequip <stand>` first.", ephemeral=True
            )
            return

        from src.battle.stand_stats import make_stand, STAND_CATALOG
        if (self.challenger_primary["stand_name"] not in STAND_CATALOG or
                target_primary["stand_name"] not in STAND_CATALOG):
            await interaction.response.send_message("One of the stands has no battle data!", ephemeral=True)
            return

        att_stand = make_stand(
            self.challenger_primary["stand_name"],
            self.challenger_primary["level"],
            self.challenger_primary["stars"],
            self.challenger_primary.get("is_shiny", False),
        )
        dfd_stand = make_stand(
            target_primary["stand_name"],
            target_primary["level"],
            target_primary["stars"],
            target_primary.get("is_shiny", False),
        )

        session = BattleSession(
            attacker_id    = self.challenger_id,
            defender_id    = self.target_id,
            attacker_stand = att_stand,
            defender_stand = dfd_stand,
            is_pvp         = True,
        )
        battle_row = await db.create_active_battle(
            attacker_id = self.challenger_id,
            defender_id = self.target_id,
            attacker_hp = att_stand.current_hp,
            defender_hp = dfd_stand.current_hp,
            turn        = "attacker",
            state       = {},
            is_pvp      = True,
        )
        session.db_battle_id = battle_row["id"]

        view  = BattleView(session, self.ctx)
        embed = _battle_start_embed(
            attacker_name  = (await self.ctx.bot.fetch_user(int(self.challenger_id))).name,
            attacker_stand = att_stand,
            defender_name  = interaction.user.name,
            defender_stand = dfd_stand,
        )
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        self.clear_items()
        await interaction.response.edit_message(
            embed=discord.Embed(description="❌ Challenge declined.", color=0x888888),
            view=None,
        )
        self.stop()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _battle_start_embed(attacker_name, attacker_stand, defender_name, defender_stand) -> discord.Embed:
    embed = discord.Embed(title="⚔️ Battle Start!", color=0xFF4444)
    embed.add_field(
        name=f"👤 {attacker_name}",
        value=f"**{attacker_stand.name}** Lv.{attacker_stand.level} ★{attacker_stand.stars}\nHP: {attacker_stand.max_hp}",
        inline=True,
    )
    embed.add_field(name="VS", value="⚔️", inline=True)
    embed.add_field(
        name=f"🤖 {defender_name}",
        value=f"**{defender_stand.name}** Lv.{defender_stand.level}\nHP: {defender_stand.max_hp}",
        inline=True,
    )
    return embed


async def setup(bot):
    await bot.add_cog(Battle(bot))