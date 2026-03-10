"""
cogs/events.py — Pucci/Dio quest chain, meteor shard event, raids
Commands: Sbone, Spucci, Smeteor, Sraid
"""

import discord
import asyncio
import random
import datetime
from discord.ext import commands

from bot.config import CURRENCY_HAMON, CURRENCY_DUST, CURRENCY_SHARDS
from bot.utils.helpers import build_weighted_list, RARITY_WEIGHTS


QUEST_RIDDLES = [
    {"riddle": "A void that swallows all, leaving nothing but darkness. What is it?", "answers": ["cream"]},
    {"riddle": "Time's master, the world bends to its will. What is it?", "answers": ["theworld"]},
    {"riddle": "A realm of dreams and terror, where the mind is bound. What is it?", "answers": ["deaththirteen", "death13"]},
    {"riddle": "A warrior's spirit bound to a blade, unstoppable in its path. What is it?", "answers": ["anubis"]},
    {"riddle": "Breaks time's chains with a punch. What is this power?", "answers": ["starplatinum"]},
    {"riddle": "Denies the cards it was dealt, erasing them. Who is it?", "answers": ["kingcrimson"]},
    {"riddle": "A coin, a bomb, and death in the air. What power is this?", "answers": ["killerqueen", "bitesthedust"]},
    {"riddle": "Weaves through time and fate with unseen threads. What is it?", "answers": ["hermitpurple"]},
    {"riddle": "Sky bends to its will, storm and wind obey. What is it?", "answers": ["weatherreport"]},
    {"riddle": "Space opens up like a jacket.", "answers": ["stickyfingers"]},
    {"riddle": "A dance of steel, swift and silent. What is it?", "answers": ["silverchariot"]},
    {"riddle": "A door to the mind, its secrets laid bare. What is it?", "answers": ["heavensdoor"]},
]


def normalize_ans(s: str) -> str:
    return s.lower().strip().replace(" ", "").replace("'", "").replace("-", "").replace(".", "")


class Events(commands.Cog, name="Events"):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────────
    # DIO'S BONE QUEST
    # ─────────────────────────────────────────────
    @commands.command(name="bone")
    @commands.is_owner()
    async def dio_bone_quest(self, ctx, channel: discord.TextChannel = None):
        """Initiate Dio's Bone quest event (Owner Only)."""
        if not channel:
            channel = ctx.channel
        if hasattr(self.bot, "active_quest") and self.bot.active_quest:
            return await ctx.send("A quest is already active!")

        quest_state = {
            "active": True,
            "channel_id": channel.id,
            "message_id": None,
            "participants": {},
            "start_time": datetime.datetime.now().isoformat()
        }

        embed = discord.Embed(
            title="The Earth Trembles...",
            description="A cold wind blows through the air...\nSomething ancient stirs beneath your feet...\n\n*React with ❓ to investigate*",
            color=discord.Color.dark_red()
        )
        embed.set_footer(text="This event will vanish in 1 hour...")
        message = await channel.send(embed=embed)
        await message.add_reaction("❓")
        quest_state["message_id"] = message.id
        self.bot.active_quest = quest_state
        asyncio.create_task(self._quest_timeout(channel))
        await ctx.send(f"✅ Dio's Bone quest initiated in {channel.mention}", delete_after=10)

    async def _quest_timeout(self, channel):
        await asyncio.sleep(3600)
        if hasattr(self.bot, "active_quest"):
            try:
                msg = await channel.fetch_message(self.bot.active_quest["message_id"])
                await msg.delete()
            except Exception:
                pass
            embed = discord.Embed(title="The Presence Fades...", description="The opportunity has passed...", color=discord.Color.dark_purple())
            await channel.send(embed=embed)
            del self.bot.active_quest

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or not hasattr(self.bot, "active_quest"):
            return
        quest = self.bot.active_quest
        if reaction.message.id != quest["message_id"] or str(reaction.emoji) != "❓":
            return
        uid = str(user.id)
        if uid in quest["participants"]:
            return
        quest["participants"][uid] = {"current_riddle": 0, "selected_riddles": None, "start_time": datetime.datetime.now().isoformat()}
        try:
            await reaction.message.remove_reaction("❓", user)
            await self._handle_riddle_start(user)
        except Exception as e:
            print(f"Quest error: {e}")
            del quest["participants"][uid]

    async def _handle_riddle_start(self, user):
        uid = str(user.id)
        if not hasattr(self.bot, "active_quest") or uid not in self.bot.active_quest["participants"]:
            return
        state = self.bot.active_quest["participants"][uid]
        try:
            dm = await user.create_dm()
            if state["current_riddle"] == 0:
                intro = discord.Embed(
                    title="👁️ A Dark Figure Emerges...",
                    description="*'I am Enrico Pucci... You seek the bone of He Who is Beyond, do you not?'*\n\n*'Answer my riddles to prove your knowledge...'*\n\nDo you understand? (yes/no)",
                    color=discord.Color.dark_purple()
                )
                await dm.send(embed=intro)
                def ck(m): return m.author == user and isinstance(m.channel, discord.DMChannel) and m.content.lower().strip() in ['yes','y','no','n']
                try:
                    resp = await self.bot.wait_for('message', timeout=60, check=ck)
                    if resp.content.lower().strip() in ['no','n']:
                        del self.bot.active_quest["participants"][uid]
                        return await dm.send("*Pucci disappears into the shadows...*")
                except asyncio.TimeoutError:
                    del self.bot.active_quest["participants"][uid]
                    return await dm.send("*Pucci fades away...*")
                state["selected_riddles"] = random.sample(QUEST_RIDDLES, 5)
            riddle = state["selected_riddles"][state["current_riddle"]]
            embed = discord.Embed(title=f"『Trial {state['current_riddle'] + 1}』", description=riddle["riddle"], color=discord.Color.dark_red())
            embed.set_footer(text="You have 5 minutes to respond.")
            await dm.send(embed=embed)
        except discord.Forbidden:
            del self.bot.active_quest["participants"][uid]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if not isinstance(message.channel, discord.DMChannel) or not hasattr(self.bot, "active_quest"):
            return
        uid = str(message.author.id)
        if uid not in self.bot.active_quest["participants"]:
            return
        await self._handle_riddle_response(message.author, message.content)

    async def _handle_riddle_response(self, user, answer):
        uid = str(user.id)
        if not hasattr(self.bot, "active_quest") or uid not in self.bot.active_quest["participants"]:
            return
        state = self.bot.active_quest["participants"][uid]
        if not state.get("selected_riddles"):
            return
        riddle = state["selected_riddles"][state["current_riddle"]]
        norm = normalize_ans(answer)
        if norm in [normalize_ans(a) for a in riddle["answers"]]:
            state["current_riddle"] += 1
            if state["current_riddle"] >= len(state["selected_riddles"]):
                await self._complete_quest(user)
            else:
                dm = await user.create_dm()
                await dm.send("✅ Correct! *Pucci nods slowly...*")
                await self._handle_riddle_start(user)
        else:
            del self.bot.active_quest["participants"][uid]
            dm = await user.create_dm()
            await dm.send("❌ *'Wrong... You were useless after all.'*")

    async def _complete_quest(self, user):
        uid = str(user.id)
        await self.bot.db.ensure_player(uid, user.name)
        await self.bot.db.add_item(uid, "Dio's Diary")
        dm = await user.create_dm()
        await dm.send(embed=discord.Embed(title="📔 Dio's Diary", description="Pucci hands you an ancient journal...\nThe command `Spucci` is now available!", color=discord.Color.dark_gold()))
        channel = self.bot.get_channel(self.bot.active_quest["channel_id"])
        if channel:
            await channel.send(f"🌑 {user.mention} has obtained **[Dio's Diary]**!")
        del self.bot.active_quest["participants"][uid]

    # ─────────────────────────────────────────────
    # PUCCI
    # ─────────────────────────────────────────────
    @commands.command(name="pucci")
    async def pucci(self, ctx):
        """Talk to Pucci (requires Dio's Diary)."""
        user_id = str(ctx.author.id)
        await self.bot.db.ensure_player(user_id, ctx.author.name)
        if await self.bot.db.get_item_count(user_id, "Dio's Diary") < 1:
            embed = discord.Embed(title="Pucci is not interested...", description="*'You haven't proven yourself worthy.'*", color=discord.Color.dark_red())
            return await ctx.send(embed=embed)
        embed = discord.Embed(title="Pucci's Update", description="*'The path to Heaven is being prepared... come back soon.'*", color=discord.Color.dark_magenta())
        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # METEOR EVENT
    # ─────────────────────────────────────────────
    @commands.command(name="meteor", aliases=["Smeteor"])
    @commands.is_owner()
    async def meteor(self, ctx, channel_id: int = None):
        """Trigger meteor shard event (Owner Only). Usage: Smeteor <channel_id>"""
        if channel_id:
            target = self.bot.get_channel(channel_id)
        else:
            target = ctx.channel
        if not target:
            return await ctx.send("❌ Invalid channel.")

        embed = discord.Embed(title="☄️ A Meteor Has Dropped!", description="5 shards have emerged!\nQuick — grab a shard!\n*(Event ends in 1 minute)*", color=discord.Color.red())
        embed.set_image(url="https://cdn.discordapp.com/attachments/1346247038576361502/1354628118509387957/latest.png")
        message = await target.send(embed=embed)
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for e in emojis:
            await message.add_reaction(e)

        shard_claims = {}
        claimed = set()

        def check(r, u):
            shard_num = emojis.index(r.emoji) + 1 if r.emoji in emojis else -1
            return (r.message.id == message.id and r.emoji in emojis and
                    str(u.id) not in shard_claims and shard_num not in claimed and not u.bot)

        end_time = asyncio.get_event_loop().time() + 60
        while len(shard_claims) < 5:
            timeout = max(1, end_time - asyncio.get_event_loop().time())
            try:
                r, u = await self.bot.wait_for("reaction_add", timeout=timeout, check=check)
                shard_num = emojis.index(r.emoji) + 1
                shard_claims[str(u.id)] = shard_num
                claimed.add(shard_num)
                await target.send(f"{u.mention} grabbed shard {shard_num}!")
            except asyncio.TimeoutError:
                break

        correct = random.choice(emojis)
        correct_num = emojis.index(correct) + 1
        winner_id = next((uid for uid, num in shard_claims.items() if num == correct_num), None)

        if winner_id:
            winner = await self.bot.fetch_user(int(winner_id))
            await self.bot.db.ensure_player(winner_id, winner.name)
            await self.bot.db.add_item(winner_id, "arrow_fragment", 1)
            count = await self.bot.db.get_item_count(winner_id, "arrow_fragment")
            embed = discord.Embed(
                title="✨ Arrow Fragment Revealed!",
                description=f"Shard {correct_num} contained an **Arrow Fragment**!\n{winner.mention} now has **{count}/5 fragments**!",
                color=discord.Color.gold()
            )
            await target.send(embed=embed)
        else:
            await target.send("None of the claimed shards contained the Arrow Fragment.")

    # ─────────────────────────────────────────────
    # RAIDS (Basic implementation)
    # ─────────────────────────────────────────────
    @commands.command(name="raid")
    async def raid(self, ctx, action: str = "list", *, raid_name: str = ""):
        """Raid commands. Usage: Sraid [list|join|create|status]"""
        if action == "list":
            embed = discord.Embed(title="⚡ Available Raids", color=0xE74C3C)
            embed.add_field(name="🔥 Skirmish Raid", value="2-5 players | Daily | Drops: Common raid currency", inline=False)
            embed.add_field(name="⚔️ Strike Raid", value="5-15 players | 3x/week | Drops: Rare items + Stand Dust", inline=False)
            embed.add_field(name="🌌 Omega Raid", value="10-30 players | Weekly | Drops: Heaven-tier materials", inline=False)
            embed.set_footer(text="Use `Sraid join <raid name>` to participate")
            await ctx.send(embed=embed)
        elif action == "join":
            user_id = str(ctx.author.id)
            await self.bot.db.ensure_player(user_id, ctx.author.name)
            await ctx.send(f"⚔️ {ctx.author.mention} has joined the raid! The battle begins when enough players assemble.")
        elif action == "create":
            if not await ctx.bot.is_owner(ctx.author):
                return await ctx.send("❌ Only admins can create raids.")
            embed = discord.Embed(title="🌌 Raid Lobby Created!", description=f"**{raid_name or 'DIO Boss Fight'}** is now open!\nUse `Sraid join` to participate.", color=0xE74C3C)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Usage: `Sraid [list|join|create]`")


async def setup(bot):
    await bot.add_cog(Events(bot))
