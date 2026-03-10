"""
cogs/admin.py — Admin and owner commands
Commands: Sbless, Sannounce, Sdm, Smigrate, Sgivestand, Ssetcooldown
"""

import discord
import shutil
import os
import traceback
from discord.ext import commands
from bot.config import CURRENCY_HAMON, CURRENCY_DUST, CURRENCY_SHARDS


VALID_ITEMS = ["rareRoll", "epicRoll", "Requiem Arrow", "arrow_fragment", "actStone", "Dio's Diary"]
VALID_CURRENCIES = {"hamon": CURRENCY_HAMON, "dust": CURRENCY_DUST, "shards": CURRENCY_SHARDS}


class Admin(commands.Cog, name="Admin"):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────────
    # BLESS (give items)
    # ─────────────────────────────────────────────
    @commands.command(name="bless")
    @commands.is_owner()
    async def bless(self, ctx, member: discord.Member = None, item: str = "rareRoll", amount: int = 1):
        """Give items to a user (Owner Only). Usage: Sbless @user [item] [amount]"""
        if not member:
            return await ctx.send("Usage: `Sbless @user [item] [amount]`")
        if amount < 1:
            return await ctx.send("Amount must be at least 1.")
        user_id = str(member.id)
        await self.bot.db.ensure_player(user_id, member.name)

        matched = next((i for i in VALID_ITEMS if i.lower() == item.lower()), None)
        if not matched:
            return await ctx.send(f"❌ Invalid item! Valid: {', '.join(VALID_ITEMS)}")

        await self.bot.db.add_item(user_id, matched, amount)
        embed = discord.Embed(title="🌟 Blessing Bestowed!", description=f"{member.mention} received **{amount}× {matched}**!", color=0xF1C40F)
        embed.set_footer(text=f"From {ctx.author}")
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # GIVE CURRENCY
    # ─────────────────────────────────────────────
    @commands.command(name="givecurrency", aliases=["gc"])
    @commands.is_owner()
    async def give_currency(self, ctx, member: discord.Member = None, currency: str = "hamon", amount: int = 100):
        """Give currency to a user (Owner Only). Usage: Sgivecurrency @user [hamon|dust|shards] [amount]"""
        if not member:
            return await ctx.send("Usage: `Sgivecurrency @user [hamon|dust|shards] [amount]`")
        curr_key = VALID_CURRENCIES.get(currency.lower())
        if not curr_key:
            return await ctx.send(f"❌ Invalid currency. Use: {', '.join(VALID_CURRENCIES.keys())}")
        user_id = str(member.id)
        await self.bot.db.ensure_player(user_id, member.name)
        await self.bot.db.add_currency(user_id, curr_key, amount)
        await ctx.send(f"✅ Gave **{amount} {currency}** to {member.mention}.")

    # ─────────────────────────────────────────────
    # GIVE STAND
    # ─────────────────────────────────────────────
    @commands.command(name="givestand", aliases=["gs"])
    @commands.is_owner()
    async def give_stand(self, ctx, member: discord.Member = None, stars: int = 1, *, stand_name: str = None):
        """Give a stand to a user (Owner Only). Usage: Sgivestand @user [stars] <Stand Name>"""
        if not member or not stand_name:
            return await ctx.send("Usage: `Sgivestand @user [stars] <Stand Name>`")
        from bot.utils.helpers import find_stand
        canonical, data = find_stand(stand_name)
        if not canonical:
            return await ctx.send(f"❌ Stand **{stand_name}** not found.")
        user_id = str(member.id)
        await self.bot.db.ensure_player(user_id, member.name)
        await self.bot.db.add_stand(user_id, canonical, stars)
        await ctx.send(f"✅ Gave **{canonical} ★{stars}** to {member.mention}.")

    # ─────────────────────────────────────────────
    # ANNOUNCE
    # ─────────────────────────────────────────────
    @commands.command(name="announce")
    @commands.is_owner()
    async def announce(self, ctx, *, message: str = None):
        """Broadcast an announcement (Owner Only)."""
        if not message:
            return await ctx.send("Usage: `Sannounce <message>`")
        ANNOUNCE_CHANNELS = []  # ← Populate with channel IDs
        count = 0
        for cid in ANNOUNCE_CHANNELS:
            ch = self.bot.get_channel(cid)
            if ch:
                await ch.send(f"📢 **Announcement:**\n{message}")
                count += 1
        await ctx.send(f"✅ Sent to {count} channel(s).")

    # ─────────────────────────────────────────────
    # DM USER
    # ─────────────────────────────────────────────
    @commands.command(name="dm")
    @commands.has_permissions(administrator=True)
    async def send_dm(self, ctx, user: discord.User = None, *, message: str = None):
        """DM a user (Admin Only). Usage: Sdm @user <message>"""
        if not user or not message:
            return await ctx.send("Usage: `Sdm @user <message>`")
        try:
            await user.send(message)
            await ctx.send(f"✅ DM sent to {user.name}.")
        except discord.Forbidden:
            await ctx.send(f"❌ {user.name} has DMs disabled.")

    # ─────────────────────────────────────────────
    # MIGRATE from JSON
    # ─────────────────────────────────────────────
    @commands.command(name="migratejson")
    @commands.is_owner()
    async def migrate_json(self, ctx, inv_path: str = "user_inventories.json", items_path: str = "user_items.json"):
        """Migrate old JSON data to SQLite (Owner Only)."""
        await ctx.send("🔄 Starting JSON → SQLite migration...")
        try:
            await self.bot.db.migrate_from_json(inv_path, items_path)
            await ctx.send("✅ Migration complete! All old data has been imported.")
        except Exception as e:
            await ctx.send(f"❌ Migration failed: {e}")
            traceback.print_exc()

    # ─────────────────────────────────────────────
    # RELOAD COG
    # ─────────────────────────────────────────────
    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cog(self, ctx, cog: str = None):
        """Reload a cog (Owner Only). Usage: Sreload <cog_name>"""
        if not cog:
            return await ctx.send("Usage: `Sreload <cog name>` (e.g. `acquisition`)")
        try:
            await self.bot.reload_extension(f"bot.cogs.{cog}")
            await ctx.send(f"✅ Reloaded `{cog}`.")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload `{cog}`: {e}")

    # ─────────────────────────────────────────────
    # HELP
    # ─────────────────────────────────────────────
    @commands.command(name="help")
    async def help_cmd(self, ctx, category: str = None):
        """Show command help. Usage: Shelp [category]"""
        categories = {
            "roll":        ("🎲 Rolling", ["Sroll", "Sdaily", "Srollrare (rr)", "Srollepic (re)", "Scd"]),
            "stands":      ("⚔️ Stands",  ["Sstands [@user]", "Sprofile [@user]", "Sequip <stand>", "Sstat <stand>", "Smerge <stand> [stars]", "Sdismantle <stand>"]),
            "craft":       ("⚒️ Crafting", ["Scraft", "Scraft <recipe>", "Suse <item> <stand>"]),
            "combat":      ("🥊 Combat",  ["Sduel @user", "Sduel @user casual", "Sduel @user wager <amt>", "Sspar @user", "Srank", "Sleaderboard"]),
            "explore":     ("🗺️ Explore", ["Sexplore [location]", "Sdungeon [location]", "Smap", "Ssearch [location]"]),
            "economy":     ("💰 Economy", ["Sbalance", "Sshop", "Sbuy <item>", "Spay @user <amt>", "Srichlist"]),
            "progression": ("📈 Progress", ["Strain <stat>", "Sstandby", "Squests", "Sachievements", "Scompendium"]),
            "social":      ("👥 Social",  ["Sgang create <n>", "Sgang info", "Sgang invite @user", "Sgang leave", "Sgang donate <amt>", "Sslime @user", "Skiss @user", "Ssuggest <idea>"]),
            "items":       ("📦 Items",   ["Sitems", "Scraft requiemarrow", "Scraft actstone"]),
        }
        if category and category.lower() in categories:
            title, cmds = categories[category.lower()]
            embed = discord.Embed(title=title, color=0x3498DB)
            embed.description = "\n".join(f"`{c}`" for c in cmds)
            return await ctx.send(embed=embed)

        embed = discord.Embed(title="📖 Stand Arena — Help", description="Use `Shelp <category>` for details.", color=0x3498DB)
        for key, (title, _) in categories.items():
            embed.add_field(name=f"`{key}`", value=title, inline=True)
        embed.set_footer(text="Prefix: S | Example: Sroll, Sduel @user")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
