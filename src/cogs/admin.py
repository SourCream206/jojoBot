"""
cogs/admin.py
Admin-only commands. Restricted to the bot owner only.
"""

import discord
from discord.ext import commands
import os

from src.db import client as db
from src.utils.constants import ITEMS


def is_owner():
    """Check if the command user is the bot owner."""
    async def predicate(ctx: commands.Context):
        owner_id = os.getenv("OWNER_ID")
        if not owner_id:
            return False
        return str(ctx.author.id) == owner_id
    return commands.check(predicate)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Give coins ────────────────────────────────────────────────────────────

    @commands.command(name="givecoins")
    @is_owner()
    async def givecoins(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Give coins to a user. Usage: Sgivecoins @user <amount>"""
        await db.get_or_create_user(str(member.id), member.name)
        new_total = await db.add_coins(str(member.id), amount)
        await ctx.reply(
            f"✅ Gave **{amount} 🪙** to {member.name}. New total: {new_total}",
            mention_author=False,
        )

    # ── Give diamonds ─────────────────────────────────────────────────────────

    @commands.command(name="givediamonds")
    @is_owner()
    async def givediamonds(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Give diamonds to a user. Usage: Sgivediamonds @user <amount>"""
        await db.get_or_create_user(str(member.id), member.name)
        new_total = await db.add_diamonds(str(member.id), amount)
        await ctx.reply(
            f"✅ Gave **{amount} 💎** to {member.name}. New total: {new_total}",
            mention_author=False,
        )

    # ── Give item ─────────────────────────────────────────────────────────────

    @commands.command(name="giveitem")
    @is_owner()
    async def giveitem(self, ctx: commands.Context, member: discord.Member, item_id: str, quantity: int = 1):
        """Give an item to a user. Usage: Sgiveitem @user <item_id> [quantity]"""
        if item_id not in ITEMS:
            await ctx.reply(
                f"Unknown item `{item_id}`. Valid items: {', '.join(ITEMS.keys())}",
                mention_author=False,
            )
            return
        await db.get_or_create_user(str(member.id), member.name)
        await db.add_item(str(member.id), item_id, quantity)
        item_name = ITEMS[item_id]["name"]
        await ctx.reply(
            f"✅ Gave **{quantity}× {item_name}** to {member.name}.",
            mention_author=False,
        )

    # ── Give stand ────────────────────────────────────────────────────────────

    @commands.command(name="givestand")
    @is_owner()
    async def givestand(self, ctx: commands.Context, member: discord.Member, *, stand_name: str):
        """Give a stand to a user. Usage: Sgivestand @user <stand name>"""
        from src.battle.stand_stats import STAND_CATALOG
        if stand_name not in STAND_CATALOG:
            await ctx.reply(f"Unknown stand `{stand_name}`.", mention_author=False)
            return
        await db.get_or_create_user(str(member.id), member.name)
        await db.add_stand(str(member.id), stand_name)
        await ctx.reply(
            f"✅ Gave **{stand_name}** to {member.name}.",
            mention_author=False,
        )

    # ── Force unlock area ─────────────────────────────────────────────────────

    @commands.command(name="unlockarea")
    @is_owner()
    async def unlockarea(self, ctx: commands.Context, member: discord.Member, *, area_name: str):
        """Force-unlock an area for a user. Usage: Sunlockarea @user <area>"""
        from src.utils.constants import AREA_ORDER
        from src.cogs.exploration import _normalise_area
        normalised = _normalise_area(area_name)
        if not normalised:
            await ctx.reply(f"Unknown area `{area_name}`.", mention_author=False)
            return
        await db.get_or_create_user(str(member.id), member.name)
        await db.unlock_area(str(member.id), normalised)
        await ctx.reply(
            f"✅ Unlocked **{normalised}** for {member.name}.",
            mention_author=False,
        )

    # ── Reset cooldown ────────────────────────────────────────────────────────

    @commands.command(name="resetcd")
    @is_owner()
    async def resetcd(self, ctx: commands.Context, member: discord.Member, command: str):
        """Reset a cooldown for a user. Usage: Sresetcd @user <command>"""
        await db.clear_cooldown(str(member.id), command)
        await ctx.reply(
            f"✅ Cleared `{command}` cooldown for {member.name}.",
            mention_author=False,
        )

    # ── Wipe user ─────────────────────────────────────────────────────────────

    @commands.command(name="wipeuser")
    @is_owner()
    async def wipeuser(self, ctx: commands.Context, member: discord.Member):
        """
        Completely wipe a user's data (all stands, items, quests).
        Does NOT delete the users row — resets it to defaults.
        Usage: Swipeuser @user
        """
        user_id = str(member.id)
        # Confirm prompt
        confirm_view = ConfirmView(ctx, user_id, member.name)
        await ctx.reply(
            f"⚠️ Are you sure you want to wipe all data for **{member.name}**? This cannot be undone.",
            view=confirm_view,
            mention_author=False,
        )

    # ── Error handler ─────────────────────────────────────────────────────────

    @givecoins.error
    @givediamonds.error
    @giveitem.error
    @givestand.error
    @unlockarea.error
    @resetcd.error
    @wipeuser.error
    async def admin_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.reply("❌ You don't have permission to use this command.", mention_author=False)
        else:
            raise error


class ConfirmView(discord.ui.View):
    def __init__(self, ctx, user_id: str, username: str):
        super().__init__(timeout=30)
        self.ctx      = ctx
        self.user_id  = user_id
        self.username = username

    @discord.ui.button(label="✅ Confirm Wipe", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Only the admin who triggered this can confirm.", ephemeral=True)
            return

        db_client = db.db()
        db_client.table("user_stands").delete().eq("user_id", self.user_id).execute()
        db_client.table("items").delete().eq("user_id", self.user_id).execute()
        db_client.table("user_quests").delete().eq("user_id", self.user_id).execute()
        db_client.table("cooldowns").delete().eq("user_id", self.user_id).execute()
        db_client.table("pending_evolutions").delete().eq("user_id", self.user_id).execute()
        db_client.table("player_unlocked_stands").delete().eq("user_id", self.user_id).execute()
        db_client.table("battle_queue").delete().eq("challenger_id", self.user_id).execute()
        db_client.table("battle_queue").delete().eq("target_id", self.user_id).execute()

        await db.update_user(self.user_id,
            coins=0, diamonds=0, current_area="Cairo", level=1, exp=0,
            pity_counter=0, mythical_pity_counter=0,
            win_count=0, loss_count=0, daily_streak=0, last_daily=None, bio="",
        )

        self.clear_items()
        await interaction.response.edit_message(
            content=f"✅ **{self.username}**'s data has been wiped and reset.",
            view=None,
        )
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.clear_items()
        await interaction.response.edit_message(content="Wipe cancelled.", view=None)
        self.stop()


async def setup(bot):
    await bot.add_cog(Admin(bot))
