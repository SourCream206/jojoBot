"""
cogs/social.py — Gangs, fun commands (slime/kiss), suggest
Commands: Sgang, Sslime, Skiss, Ssuggest
"""

import discord
import asyncio
import random
from discord.ext import commands
from bot.config import CURRENCY_HAMON, COOLDOWN_SUGGEST


GANG_CREATE_COST = 500
MAX_GANG_SIZE = 10


class Social(commands.Cog, name="Social"):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────────
    # GANG
    # ─────────────────────────────────────────────
    @commands.group(name="gang", invoke_without_command=True)
    async def gang(self, ctx):
        """Gang commands. Use `Sgang help` for subcommands."""
        embed = discord.Embed(title="🎭 Gang Commands", color=0xE74C3C)
        cmds = [
            ("Sgang create <name>", "Create a new gang (costs 500 Hamon)"),
            ("Sgang info [@gang]", "View gang stats and members"),
            ("Sgang invite @user", "Invite a player to your gang"),
            ("Sgang leave", "Leave your current gang"),
            ("Sgang donate <amount>", "Donate Hamon to gang treasury"),
        ]
        for cmd, desc in cmds:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        await ctx.send(embed=embed)

    @gang.command(name="create")
    async def gang_create(self, ctx, *, name: str = None):
        if not name:
            return await ctx.send("Usage: `Sgang create <Gang Name>`")
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        existing = await self.bot.db.get_gang(user_id=user_id)
        if existing:
            return await ctx.send(f"❌ You're already in **{existing['name']}**! Leave first.")
        if not await self.bot.db.deduct_currency(user_id, CURRENCY_HAMON, GANG_CREATE_COST):
            return await ctx.send(f"❌ Need **{GANG_CREATE_COST} Hamon** to create a gang.")
        success = await self.bot.db.create_gang(name, user_id)
        if not success:
            await self.bot.db.add_currency(user_id, CURRENCY_HAMON, GANG_CREATE_COST)
            return await ctx.send(f"❌ Gang name **{name}** already taken!")
        await ctx.send(embed=discord.Embed(title="🎉 Gang Created!", description=f"**{name}** is now active! You are the leader.", color=0x57F287))

    @gang.command(name="info")
    async def gang_info(self, ctx, *, gang_name: str = None):
        if gang_name:
            gang = await self.bot.db.get_gang(gang_name=gang_name)
        else:
            gang = await self.bot.db.get_gang(user_id=str(ctx.author.id))
        if not gang:
            return await ctx.send("Gang not found. Create one with `Sgang create <name>`.")
        members = await self.bot.db.get_gang_members(gang["gang_id"])
        embed = discord.Embed(title=f"🎭 {gang['name']}", color=0xE74C3C)
        embed.add_field(name="Leader", value=gang["leader_id"], inline=True)
        embed.add_field(name="Treasury", value=f"{gang['treasury']:,} Hamon", inline=True)
        embed.add_field(name="Members", value="\n".join(m["username"] for m in members) or "None", inline=False)
        await ctx.send(embed=embed)

    @gang.command(name="invite")
    async def gang_invite(self, ctx, member: discord.Member = None):
        if not member:
            return await ctx.send("Usage: `Sgang invite @user`")
        user_id = str(ctx.author.id)
        gang = await self.bot.db.get_gang(user_id=user_id)
        if not gang or gang["leader_id"] != user_id:
            return await ctx.send("❌ You must be a gang leader to invite members.")
        members = await self.bot.db.get_gang_members(gang["gang_id"])
        if len(members) >= MAX_GANG_SIZE:
            return await ctx.send(f"❌ Gang is full! ({MAX_GANG_SIZE} max)")
        target_uid = str(member.id)
        existing = await self.bot.db.get_gang(user_id=target_uid)
        if existing:
            return await ctx.send(f"❌ {member.name} is already in a gang.")
        await self.bot.db.ensure_player(target_uid, member.name)
        await self.bot.db._conn.execute("INSERT OR IGNORE INTO gang_members(gang_id, user_id) VALUES(?,?)", (gang["gang_id"], target_uid))
        await self.bot.db._conn.commit()
        await ctx.send(f"✅ {member.mention} has been invited to **{gang['name']}**!")

    @gang.command(name="leave")
    async def gang_leave(self, ctx):
        user_id = str(ctx.author.id)
        gang = await self.bot.db.get_gang(user_id=user_id)
        if not gang:
            return await ctx.send("❌ You're not in a gang.")
        if gang["leader_id"] == user_id:
            return await ctx.send("❌ Leaders can't leave. Disband with `Sgang disband` first.")
        await self.bot.db._conn.execute("DELETE FROM gang_members WHERE gang_id=? AND user_id=?", (gang["gang_id"], user_id))
        await self.bot.db._conn.commit()
        await ctx.send(f"👋 Left **{gang['name']}**.")

    @gang.command(name="donate")
    async def gang_donate(self, ctx, amount: int = 0):
        if amount <= 0:
            return await ctx.send("Usage: `Sgang donate <amount>`")
        user_id = str(ctx.author.id)
        gang = await self.bot.db.get_gang(user_id=user_id)
        if not gang:
            return await ctx.send("❌ You're not in a gang.")
        if not await self.bot.db.deduct_currency(user_id, CURRENCY_HAMON, amount):
            return await ctx.send(f"❌ Insufficient Hamon.")
        await self.bot.db._conn.execute("UPDATE gangs SET treasury=treasury+? WHERE gang_id=?", (amount, gang["gang_id"]))
        await self.bot.db._conn.commit()
        await ctx.send(f"✅ Donated **{amount} Hamon** to **{gang['name']}** treasury!")

    # ─────────────────────────────────────────────
    # FUN
    # ─────────────────────────────────────────────
    @commands.command(name="slime")
    async def slime(self, ctx, user: discord.User = None):
        """Slime someone."""
        if not user:
            return await ctx.send("Usage: `Sslime @user`")
        if user == ctx.author:
            gifs = ["https://files.catbox.moe/bwv03g.gif"]
        else:
            gifs = [
                "https://tenor.com/view/jojo-gun-jojos-josuke-meme-gif-18019715",
                "https://tenor.com/view/mista-jojo-gun-regret-death-gif-17232016",
                "https://tenor.com/view/turles-piccolo-gif-24678501",
                "https://tenor.com/view/dragonball-super-broly-anime-movie-frieza-gif-27137981",
                "https://tenor.com/view/jjk-jjk-s2-jjk-season-2-jujutsu-kaisen-jujutsu-kaisen-s2-gif-7964484372484357392",
            ]
        await ctx.send(f"{user.mention} has been slimed by {ctx.author.mention}!\nbye bye")
        await ctx.send(random.choice(gifs))

    @commands.command(name="kiss")
    async def kiss(self, ctx, user: discord.User = None):
        """Kiss someone."""
        if not user:
            return await ctx.send("Usage: `Skiss @user`")
        gifs = [
            "https://tenor.com/view/goro-majima-kazuma-kiryu-yakuza-kiss-gay-love-gender-ryu-ga-gotoku-goro-majima-kiryu-kazuma-yakuza-gay-gif-22218833",
        ]
        await ctx.send(f"{user.mention} has been kissed by {ctx.author.mention}! 💗")
        await ctx.send(random.choice(gifs))

    # ─────────────────────────────────────────────
    # SUGGEST
    # ─────────────────────────────────────────────
    @commands.command(name="suggest", aliases=["suggestion"])
    @commands.cooldown(1, COOLDOWN_SUGGEST, commands.BucketType.user)
    async def suggest(self, ctx, *, suggestion: str = None):
        """Submit a suggestion. Usage: Ssuggest <your idea>"""
        if not suggestion:
            return await ctx.send("Usage: `Ssuggest <your suggestion>`")

        SUGGESTION_CHANNEL_ID = 0  # ← Set this to your suggestion channel ID

        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=0x57F287
        )
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"User ID: {ctx.author.id}")

        channel = self.bot.get_channel(SUGGESTION_CHANNEL_ID)
        if channel:
            msg = await channel.send(embed=embed)
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            await ctx.send("✅ Your suggestion has been submitted!")
        else:
            await ctx.send("⚠️ Suggestion channel not configured. Suggestion logged.")

    @suggest.error
    async def suggest_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.send(f"⌛ Suggestion cooldown: {m}m {s}s.")


async def setup(bot):
    await bot.add_cog(Social(bot))
