"""
bot.py — Entry point for the JoJo Discord RPG bot.
"""

import discord
from discord.ext import commands
import os
import asyncio
import logging
import traceback
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jojo-rpg")

COGS = [
    "src.cogs.rolls",
    "src.cogs.inventory",
    "src.cogs.battle",
    "src.cogs.exploration",
    "src.cogs.profile",
    "src.cogs.economy",
    "src.cogs.admin",
]


def _prefix(bot, message):
    """Accept both S and s as prefix."""
    return commands.when_mentioned_or("S", "s")(bot, message)


class JojoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix=_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

    async def setup_hook(self):
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}")
                traceback.print_exc()

        from src.db.client import resolve_expired_battles, expire_battle_queue
        await resolve_expired_battles()
        await expire_battle_queue()

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Game(name="JoJo's Bizarre Adventure | Sroll")
        )

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"⏳ You're on cooldown! Try again in **{error.retry_after:.1f}s**.",
                mention_author=False,
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(
                f"❌ Missing argument: `{error.param.name}`.",
                mention_author=False,
            )
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            log.error(f"Unhandled error in command '{ctx.command}': {error}")
            raise error


async def main():
    bot = JojoBot()
    async with bot:
        await bot.start(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())