"""
cogs/economy.py
Sdaily, Sbalance, Sshop, Sdarby (Blackjack)
"""

import discord
from discord.ext import commands
import random
from datetime import datetime, timezone, timedelta

from src.db import client as db
from src.utils.constants import get_daily_reward, ITEMS


# ════════════════════════════════════════════════════════════
# SHOP DATA  (rotates daily / weekly — seeded by date)
# ════════════════════════════════════════════════════════════

DAILY_SHOP_POOL = [
    {"item_id": "xpPotion",   "price_coins": 300},
    {"item_id": "healingItem","price_coins": 150},
    {"item_id": "rareRoll",   "price_coins": 800},
]

WEEKLY_SHOP_POOL = [
    {"item_id": "actStone",      "price_coins": 3000},
    {"item_id": "epicRoll",      "price_coins": 1500},
    {"item_id": "requiemArrow",  "price_diamonds": 50},
    {"item_id": "xpPotion",      "price_coins": 250},
]

def _get_daily_shop():
    seed = datetime.now(timezone.utc).toordinal()
    rng  = random.Random(seed)
    return rng.sample(DAILY_SHOP_POOL, min(3, len(DAILY_SHOP_POOL)))

def _get_weekly_shop():
    # Week number as seed
    today = datetime.now(timezone.utc)
    seed  = today.isocalendar()[1] + today.year * 100
    rng   = random.Random(seed)
    return rng.sample(WEEKLY_SHOP_POOL, min(3, len(WEEKLY_SHOP_POOL)))


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Sbalance ──────────────────────────────────────────────────────────────

    @commands.command(name="balance", aliases=["bal", "coins", "wallet", "money", "coin", "cash", "gold", "balanc", "ballance", "bl"])
    async def sbalance(self, ctx: commands.Context):
        """Check your coin and diamond balance."""
        user = await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        embed = discord.Embed(title=f"💰 {ctx.author.name}'s Balance", color=0xF1C40F)
        embed.add_field(name="🪙 Coins",   value=str(user["coins"]),   inline=True)
        embed.add_field(name="💎 Diamonds",value=str(user["diamonds"]),inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    # ── Sdaily ────────────────────────────────────────────────────────────────

    @commands.command(name="daily", aliases=["claim", "daly", "dailly", "dayly", "clam", "claym", "d"])
    async def sdaily(self, ctx: commands.Context):
        """Claim your daily reward."""
        user_id = str(ctx.author.id)
        user    = await db.get_or_create_user(user_id, ctx.author.name)

        now       = datetime.now(timezone.utc)
        last_daily = user.get("last_daily")

        if last_daily:
            if isinstance(last_daily, str):
                last_daily = datetime.fromisoformat(last_daily)
            if last_daily.tzinfo is None:
                last_daily = last_daily.replace(tzinfo=timezone.utc)

            hours_since = (now - last_daily).total_seconds() / 3600

            if hours_since < 20:
                next_claim = last_daily + timedelta(hours=20)
                remaining  = next_claim - now
                hrs        = int(remaining.total_seconds() // 3600)
                mins       = int((remaining.total_seconds() % 3600) // 60)
                await ctx.reply(
                    f"⏳ Daily already claimed! Come back in **{hrs}h {mins}m**.",
                    mention_author=False,
                )
                return

            # Streak: reset if more than 48 hours have passed
            streak = user["daily_streak"] + 1 if hours_since < 48 else 1
        else:
            streak = 1

        reward = get_daily_reward(streak)
        await db.add_coins(user_id, reward["coins"])
        if reward.get("diamonds"):
            await db.add_diamonds(user_id, reward["diamonds"])
        for item_id, qty in reward.get("items", {}).items():
            await db.add_item(user_id, item_id, qty)

        await db.update_user(user_id, daily_streak=streak, last_daily=now.isoformat())

        embed = discord.Embed(
            title="🎁 Daily Reward!",
            color=0xF1C40F,
        )
        embed.add_field(name="🪙 Coins",    value=str(reward["coins"]),            inline=True)
        embed.add_field(name="💎 Diamonds", value=str(reward.get("diamonds", 0)),  inline=True)
        embed.add_field(name="🔥 Streak",   value=f"Day {streak}",                 inline=True)

        if reward.get("items"):
            items_str = ", ".join(
                f"{qty}× {ITEMS.get(iid, {}).get('name', iid)}"
                for iid, qty in reward["items"].items()
            )
            embed.add_field(name="📦 Items", value=items_str, inline=False)

        if streak in (5, 10, 25, 50, 100, 250, 500):
            embed.description = f"🎉 **Milestone Day {streak}!** Big rewards!"

        await ctx.reply(embed=embed, mention_author=False)

    # ── Sshop ─────────────────────────────────────────────────────────────────

    @commands.command(name="cd", aliases=["cooldown", "cooldowns", "cds", "cld", "cooldwn", "timer", "timers"])
    async def scd(self, ctx: commands.Context):
        """Check all your active cooldowns."""
        user_id = str(ctx.author.id)
        user    = await db.get_or_create_user(user_id, ctx.author.name)
        now     = datetime.now(timezone.utc)

        active = []

        # ── Cooldowns table (sroll, sbattle, sdarby etc.) ──
        from src.db.client import db as get_db, _run_sync
        res = await _run_sync(lambda: get_db().table("cooldowns").select("command, expires_at").eq("user_id", user_id).execute())
        for row in (res.data or []):
            expires = datetime.fromisoformat(row["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            remaining = (expires - now).total_seconds()
            if remaining > 0:
                active.append((row["command"], remaining))

        # ── Daily reward (tracked on users row, not cooldowns table) ──
        last_daily = user.get("last_daily")
        if last_daily:
            if isinstance(last_daily, str):
                last_daily = datetime.fromisoformat(last_daily)
            if last_daily.tzinfo is None:
                last_daily = last_daily.replace(tzinfo=timezone.utc)
            next_daily = last_daily + timedelta(hours=20)
            remaining  = (next_daily - now).total_seconds()
            if remaining > 0:
                active.append(("daily", remaining))

        if not active:
            await ctx.reply("✅ No active cooldowns!", mention_author=False)
            return

        # Format nicely
        def fmt(secs: float) -> str:
            secs = int(secs)
            h = secs // 3600
            m = (secs % 3600) // 60
            s = secs % 60
            if h:
                return f"{h}h {m}m"
            if m:
                return f"{m}m {s}s"
            return f"{s}s"

        # Friendly display names
        names = {
            "sroll":   "🎲 Roll",
            "sbattle": "⚔️ Battle",
            "sdarby":  "🃏 D'Arby",
            "daily":   "🎁 Daily",
        }

        embed = discord.Embed(title="⏳ Your Cooldowns", color=0xFF4444)
        for command, remaining in sorted(active, key=lambda x: x[1]):
            label = names.get(command, f"S{command}")
            embed.add_field(name=label, value=fmt(remaining), inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="shop", aliases=["store", "shopdaily", "dailyshop", "shopweekly", "weeklyshop", "shopweek", "weekshop"])
    async def sshop(self, ctx: commands.Context, tab: str = "daily"):
        """
        View the rotating shop.
        - Sshop daily   → today's daily shop
        - Sshop weekly  → this week's weekly shop
        - Or use: Sshopdaily, Sshopweekly, etc.
        """
        # Handle compound command names
        cmd_name = ctx.invoked_with.lower()
        if "weekly" in cmd_name or "week" in cmd_name:
            tab = "weekly"
        elif "daily" in cmd_name:
            tab = "daily"

        tab  = tab.lower()
        pool = _get_weekly_shop() if tab == "weekly" else _get_daily_shop()
        label = "Weekly Shop 🗓️" if tab == "weekly" else "Daily Shop 🏪"

        embed = discord.Embed(title=label, color=0x00FF88)
        for i, listing in enumerate(pool, 1):
            item_def = ITEMS.get(listing["item_id"], {})
            name     = item_def.get("name", listing["item_id"])
            emoji    = item_def.get("emoji", "📦")
            if "price_coins" in listing:
                price = f"{listing['price_coins']} 🪙"
            else:
                price = f"{listing['price_diamonds']} 💎"
            embed.add_field(
                name=f"{i}. {emoji} {name}",
                value=f"Price: **{price}**\nBuy: `Sbuy {listing['item_id']}`",
                inline=False,
            )

        refresh_str = "Resets in <24 hours" if tab == "daily" else "Resets weekly on Monday"
        embed.set_footer(text=refresh_str)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="buy", aliases=["purchase", "get", "buyitem", "purchaseitem", "by"])
    async def sbuy(self, ctx: commands.Context, item_id: str):
        """Buy an item from the current shop. Usage: Sbuy <item_id>"""
        user_id = str(ctx.author.id)
        user    = await db.get_or_create_user(user_id, ctx.author.name)

        # Check both shops
        all_listings = _get_daily_shop() + _get_weekly_shop()
        listing = next((l for l in all_listings if l["item_id"] == item_id), None)

        if not listing:
            await ctx.reply(f"`{item_id}` is not in the current shop.", mention_author=False)
            return

        if "price_coins" in listing:
            price = listing["price_coins"]
            if user["coins"] < price:
                await ctx.reply(f"Not enough coins! Need **{price} 🪙** (you have {user['coins']}).", mention_author=False)
                return
            await db.add_coins(user_id, -price)
        else:
            price = listing["price_diamonds"]
            if user["diamonds"] < price:
                await ctx.reply(f"Not enough diamonds! Need **{price} 💎** (you have {user['diamonds']}).", mention_author=False)
                return
            await db.add_diamonds(user_id, -price)

        await db.add_item(user_id, item_id, 1)
        item_name = ITEMS.get(item_id, {}).get("name", item_id)
        await ctx.reply(f"✅ Purchased **{item_name}**!", mention_author=False)

    # ── Sdarby (Blackjack) ────────────────────────────────────────────────────

    @commands.command(name="darby", aliases=["gamble", "blackjack", "casino", "bet", "bj", "darbey", "darb", "gambling", "gambl", "game"])
    async def sdarby(self, ctx: commands.Context, bet: int = 0):
        """
        Challenge D'Arby to a game of Blackjack.
        Usage: Sdarby <bet amount>
        Requires a 2-star Osiris.
        Osiris equipped gives +10% win chance.
        """
        user_id = str(ctx.author.id)
        user    = await db.get_or_create_user(user_id, ctx.author.name)

        # Check if user has a 2-star Osiris
        user_stands = await db.get_user_stands(user_id)
        osiris = next(
            (s for s in user_stands if s["stand_name"] == "Osiris" and s["stars"] >= 2),
            None
        )
        if not osiris:
            await ctx.reply(
                "🃏 You need a **2-star Osiris** to challenge D'Arby!",
                mention_author=False
            )
            return

        # Cooldown check (45 minutes)
        expires = await db.get_cooldown(user_id, "sdarby")
        if expires:
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            secs = int(remaining % 60)
            mins = int(remaining // 60)
            await ctx.reply(
                f"⏳ D'Arby needs a break! Try again in **{mins}m {secs}s**.",
                mention_author=False,
            )
            return

        if bet <= 0:
            await ctx.reply("You must bet at least 1 coin! Usage: `Sdarby <bet>`", mention_author=False)
            return

        if user["coins"] < bet:
            await ctx.reply(
                f"Not enough coins! You have **{user['coins']} 🪙**.",
                mention_author=False,
            )
            return

        await db.set_cooldown(user_id, "sdarby", 2700)  # 45 minute cooldown

        # Check Osiris passive for win bonus
        primary = await db.get_primary_stand(user_id)
        win_bonus = 0.10 if (primary and primary["stand_name"] == "Osiris") else 0.0

        view = BlackjackView(ctx, user_id, bet, win_bonus)
        embed = view.build_embed()
        msg   = await ctx.reply(embed=embed, view=view, mention_author=False)
        view.message = msg


# ════════════════════════════════════════════════════════════
# BLACKJACK VIEW
# ════════════════════════════════════════════════════════════

SUITS  = ["♠", "♥", "♦", "♣"]
RANKS  = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
VALUES = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"J":10,"Q":10,"K":10,"A":11}

def _new_deck():
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck

def _hand_value(hand: list) -> int:
    total = sum(VALUES[r] for r, _ in hand)
    aces  = sum(1 for r, _ in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces  -= 1
    return total

def _fmt_hand(hand: list) -> str:
    return " ".join(f"{r}{s}" for r, s in hand)


class BlackjackView(discord.ui.View):
    def __init__(self, ctx, user_id: str, bet: int, win_bonus: float):
        super().__init__(timeout=120)
        self.ctx       = ctx
        self.user_id   = user_id
        self.bet       = bet
        self.win_bonus = win_bonus
        self.message   = None
        self.finished  = False

        self.deck         = _new_deck()
        self.player_hand  = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand  = [self.deck.pop(), self.deck.pop()]

        # Auto-resolve blackjack
        if _hand_value(self.player_hand) == 21:
            self.finished = True

    def build_embed(self, reveal_dealer: bool = False) -> discord.Embed:
        pv = _hand_value(self.player_hand)
        embed = discord.Embed(title="🃏 D'Arby's Casino — Blackjack", color=0x2ECC71)
        embed.add_field(
            name="Your Hand",
            value=f"{_fmt_hand(self.player_hand)} — **{pv}**",
            inline=False,
        )
        if reveal_dealer:
            dv = _hand_value(self.dealer_hand)
            embed.add_field(
                name="D'Arby's Hand",
                value=f"{_fmt_hand(self.dealer_hand)} — **{dv}**",
                inline=False,
            )
        else:
            embed.add_field(
                name="D'Arby's Hand",
                value=f"{self.dealer_hand[0][0]}{self.dealer_hand[0][1]} 🂠",
                inline=False,
            )
        embed.set_footer(text=f"Bet: {self.bet} 🪙 | +10% win bonus: {'✅' if self.win_bonus else '❌'}")
        return embed

    async def _end_game(self, interaction: discord.Interaction, player_val: int):
        # Dealer plays
        while _hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        dealer_val = _hand_value(self.dealer_hand)
        self.clear_items()

        # Determine result
        player_bust = player_val > 21
        dealer_bust = dealer_val > 21

        # Apply Osiris win bonus: increase player "effective" value slightly
        effective_player = player_val + (2 if self.win_bonus and not player_bust else 0)

        if player_bust:
            result = "lose"
        elif dealer_bust:
            result = "win"
        elif effective_player > dealer_val:
            result = "win"
        elif effective_player < dealer_val:
            result = "lose"
        else:
            result = "tie"

        embed = self.build_embed(reveal_dealer=True)

        if result == "win":
            await db.add_coins(self.user_id, self.bet)   # Net gain = bet (they keep theirs + win dealer's)
            embed.colour = 0x00FF88
            embed.add_field(name="Result", value=f"🏆 **You win! +{self.bet} 🪙**", inline=False)
        elif result == "lose":
            await db.add_coins(self.user_id, -self.bet)
            embed.colour = 0xFF4444
            embed.add_field(name="Result", value=f"💀 **D'Arby wins! -{self.bet} 🪙**", inline=False)
        else:
            embed.colour = 0x888888
            embed.add_field(name="Result", value="🤝 **Tie! Bets returned.**", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        self.player_hand.append(self.deck.pop())
        pv = _hand_value(self.player_hand)
        if pv >= 21:
            await self._end_game(interaction, pv)
        else:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        await self._end_game(interaction, _hand_value(self.player_hand))

    async def on_timeout(self):
        # Auto-stand on timeout
        self.clear_items()
        if self.message:
            await self.message.edit(
                embed=discord.Embed(description="⏱️ Game timed out. Bet returned.", color=0x888888),
                view=None,
            )


async def setup(bot):
    await bot.add_cog(Economy(bot))