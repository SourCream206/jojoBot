import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["h", "commands"])
    async def help_cmd(self, ctx: commands.Context):
        """Displays categorized lists of commands."""
        embed = discord.Embed(
            title="🌟 Sroll RPG | Command List",
            description="Use `S<command>` to play! (e.g. `Sroll`)",
            color=0x2ECC71
        )
        
        embed.add_field(
            name="⚔️ Combat & Leaderboard",
            value="`Sbattle [user]` • Fight PvE enemies or mention a user for PvP!\n"
                  "`Schallenges` • View pending PvP challenges\n"
                  "`Saccept` / `Sdecline` • Respond to a PvP duel\n"
                  "`Sleaderboard` • View the top players globally",
            inline=False
        )
        embed.add_field(
            name="🎒 Profile & Inventory",
            value="`Sprofile` • View your stats, levels, and equipped Stands\n"
                  "`Sinv` • View your Stand collection\n"
                  "`Sinfo <stand>` • View detailed info on a specific Stand\n"
                  "`Sitems` • View your Backpack items\n"
                  "`Sequip <stand_name>` • Equip your Primary Stand\n"
                  "`Ssec <stand_name>` • Equip your Secondary Stand\n"
                  "`Suse <item>` • Consume an item from your bag\n"
                  "`Smerge <stand_name>` • Fuse duplicate stands for a star power upgrade",
            inline=False
        )
        embed.add_field(
            name="🎰 Rolls & Gacha",
            value="`Sroll` • Spend 100 coins to roll a random Stand!\n"
                  "`Srareroll` / `Sepicroll` • Consume items for guaranteed high tier pulls\n"
                  "`Spity` • Check your Legendary and Mythical pity counters",
            inline=False
        )
        embed.add_field(
            name="🌍 Exploration & Economy",
            value="`Sarea` • View your current location\n"
                  "`Stravel` • Travel to a new Area to unlock new Stand pools\n"
                  "`Squests` • View active story missions\n"
                  "`Sbalance` • Check your Coins and Diamonds\n"
                  "`Sdaily` • Claim your daily rewards\n"
                  "`Sshop` / `Sbuy <item>` • Browse and purchase items\n"
                  "`Sdarby <amount>` • Gamble your coins against D'Arby\n"
                  "`Scd` • View your active cooldown delays",
            inline=False
        )
        embed.add_field(
            name="⚙️ Admin & Utils",
            value="`Sbio <text>` • Set a custom profile bio\n"
                  "`Admin Commands` • `Sgivecoins`, `Sgivediamonds`, `Sgiveitem`, `Sgivestand`, `Sunlockarea`, etc.",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
