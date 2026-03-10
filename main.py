"""
STAND ARENA - Main Entry Point
JoJo's Bizarre Adventure Discord Bot v2.0
"""

import os
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db.manager import DatabaseManager

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("standarena.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("standarena")

COGS = [
    "bot.cogs.acquisition",
    "bot.cogs.combat",
    "bot.cogs.progression",
    "bot.cogs.economy",
    "bot.cogs.exploration",
    "bot.cogs.social",
    "bot.cogs.events",
    "bot.cogs.admin",
]

class StandArena(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix="S",
            intents=intents,
            case_insensitive=True,
            help_command=None
        )
        self.db: DatabaseManager = None

    async def setup_hook(self):
        self.db = DatabaseManager()
        await self.db.initialize()

        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}", exc_info=True)

    async def on_ready(self):
        await self.change_presence(activity=discord.Game(name="Sroll | Stand Arena v2.0"))
        log.info(f"Stand Arena online as {self.user} (ID: {self.user.id})")

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            remaining = round(error.retry_after)
            h, rem = divmod(remaining, 3600)
            m, s = divmod(rem, 60)
            parts = []
            if h: parts.append(f"{h}h")
            if m: parts.append(f"{m}m")
            if s or not parts: parts.append(f"{s}s")
            await ctx.send(f"⏳ Cooldown active! Try again in **{' '.join(parts)}**.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
        elif isinstance(error, commands.UserNotFound):
            await ctx.send("❌ User not found.")
        elif isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.CommandInvokeError):
            log.error(f"Command error in {ctx.command}: {error.original}", exc_info=True)
            await ctx.send("❌ An error occurred. Please try again.")
        else:
            log.warning(f"Unhandled error: {type(error).__name__}: {error}")

def main():
    bot = StandArena()
    bot.run(TOKEN, log_handler=None)

if __name__ == "__main__":
    main()
