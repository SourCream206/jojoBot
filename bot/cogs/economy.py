"""
cogs/economy.py — Currency, shop, balance, pay, richlist, auctions (stub)
Commands: Sbalance, Sshop, Sbuy, Spay, Srichlist
"""

import discord
from discord.ext import commands
from bot.config import (
    CURRENCY_HAMON, CURRENCY_DUST, CURRENCY_SHARDS,
    BIZARRE_BAZAAR, BLACK_MARKET, VOID_SHOP, TRADE_TAX_PERCENT,
)


class Economy(commands.Cog, name="Economy"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx, member: discord.Member = None):
        """View your currency balances."""
        target = member or ctx.author
        uid = str(target.id)
        await self.bot.db.ensure_player(uid, target.name)
        player = await self.bot.db.get_player(uid)
        embed = discord.Embed(title=f"💰 {target.name}'s Wallet", color=0xF1C40F)
        embed.add_field(name="Hamon 🟡", value=f"{player['hamon']:,}", inline=True)
        embed.add_field(name="Stand Dust 🔥", value=f"{player['stand_dust']:,}", inline=True)
        embed.add_field(name="SOS Shards 💎", value=f"{player['sos_shards']:,}", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="shop")
    async def shop(self, ctx, shop_type: str = "bazaar"):
        """Browse shops. Types: bazaar, blackmarket, void. Usage: Sshop [type]"""
        shops = {
            "bazaar": ("🛍️ Bizarre Bazaar", BIZARRE_BAZAAR, "hamon"),
            "blackmarket": ("🖤 Black Market", BLACK_MARKET, "stand_dust"),
            "void": ("🌑 The Void Shop", VOID_SHOP, "sos_shards"),
        }
        key = shop_type.lower().replace(" ", "").replace("_", "")
        if key not in shops:
            return await ctx.send("❌ Unknown shop. Try `bazaar`, `blackmarket`, or `void`.")
        title, catalog, currency = shops[key]
        embed = discord.Embed(title=title, color=0x9B59B6)
        currency_emoji = {"hamon": "🟡 Hamon", "stand_dust": "🔥 Stand Dust", "sos_shards": "💎 SOS Shards"}[currency]
        for item_name, details in catalog.items():
            embed.add_field(
                name=item_name,
                value=f"**{details['cost']} {currency_emoji}**\nGives: {details['item']}",
                inline=True
            )
        embed.set_footer(text=f"Use `Sbuy <item name>` to purchase")
        await ctx.send(embed=embed)

    @commands.command(name="buy")
    async def buy(self, ctx, *, item_name: str = None):
        """Purchase from the shop. Usage: Sbuy <item name>"""
        if not item_name:
            return await ctx.send("Usage: `Sbuy <item name>` — Check `Sshop` for options.")
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)

        all_shops = {**BIZARRE_BAZAAR, **BLACK_MARKET, **VOID_SHOP}
        match = None
        for name, details in all_shops.items():
            if name.lower() == item_name.lower():
                match = (name, details)
                break
        if not match:
            return await ctx.send(f"❌ Item **{item_name}** not found. Check `Sshop` for the catalog.")

        name, details = match
        currency = details["currency"]
        cost = details["cost"]
        if not await self.bot.db.deduct_currency(user_id, currency, cost):
            return await ctx.send(f"❌ Insufficient funds! You need **{cost}** {currency.replace('_',' ').title()}.")

        await self.bot.db.add_item(user_id, details["item"], 1)
        await ctx.send(f"✅ Purchased **{name}** for {cost} {currency.replace('_',' ').title()}!")

    @commands.command(name="pay")
    async def pay(self, ctx, member: discord.Member = None, amount: int = 0):
        """Send Hamon to another player (5% tax). Usage: Spay @user <amount>"""
        if not member or amount <= 0:
            return await ctx.send("Usage: `Spay @user <amount>`")
        if member == ctx.author:
            return await ctx.send("❌ You can't pay yourself.")

        user_id = str(ctx.author.id)
        target_id = str(member.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        await self.bot.db.ensure_player(target_id, member.name)

        tax = max(1, int(amount * TRADE_TAX_PERCENT))
        total_cost = amount + tax

        if not await self.bot.db.deduct_currency(user_id, CURRENCY_HAMON, total_cost):
            return await ctx.send(f"❌ You need {total_cost} Hamon (including {tax} tax).")

        await self.bot.db.add_currency(target_id, CURRENCY_HAMON, amount)
        await ctx.send(f"✅ Sent **{amount} Hamon** to {member.mention} (tax: {tax} Hamon).")

    @commands.command(name="richlist", aliases=["economy"])
    async def richlist(self, ctx):
        """Top 20 wealthiest players."""
        rows = await self.bot.db.get_richlist(20)
        embed = discord.Embed(title="💰 Hamon Richlist", color=0xF1C40F)
        for i, row in enumerate(rows, 1):
            embed.add_field(name=f"#{i} {row['username']}", value=f"{row['hamon']:,} Hamon", inline=False)
        if not rows:
            embed.description = "No players yet!"
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))
