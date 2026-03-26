"""
cogs/profile.py
Sprofile, Sbio
"""

import discord
from discord.ext import commands
import asyncio

from src.db import client as db
from src.utils.embeds import profile_embed


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["prof", "me", "stats", "p", "status", "profil", "profl"])
    async def sprofile(self, ctx: commands.Context, member: discord.Member = None):
        """View your (or another player's) profile. Usage: Sprofile [@user]"""
        target = member or ctx.author
        # Fetch all data in parallel
        user, primary, secondary = await asyncio.gather(
            db.get_or_create_user(str(target.id), target.name),
            db.get_primary_stand(str(target.id)),
            db.get_secondary_stand(str(target.id))
        )
        embed  = profile_embed(user, primary, secondary)
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="bio", aliases=["setbio", "about"])
    async def sbio(self, ctx: commands.Context, *, bio: str):
        """Set your profile bio. Usage: Sbio <text>"""
        if len(bio) > 150:
            await ctx.reply("Bio must be 150 characters or fewer.", mention_author=False)
            return
        await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        await db.update_user(str(ctx.author.id), bio=bio)
        await ctx.reply("✅ Bio updated!", mention_author=False)


async def setup(bot):
    await bot.add_cog(Profile(bot))