"""
battle/engine.py
Pokémon-style battle flow:
  - Move buttons are shown directly on the battle embed (no sub-menu)
  - Click move → your attack resolves immediately → embed updates showing damage
  - Then enemy attacks → embed updates again
  - No ephemeral popups, no two-step menus
"""

from __future__ import annotations
import discord
import random
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from src.battle.stand import Stand, Move
from src.battle.gimmicks import (
    apply_gimmick_on_turn_start,
    apply_gimmick_on_damage_received,
    try_time_stop,
)
from src.battle.ai import ai_choose_move, ai_use_time_stop
from src.utils.constants import coins_from_pve, coins_from_pvp, xp_from_pve, xp_from_pvp


# ════════════════════════════════════════════════════════════
# BATTLE SESSION
# ════════════════════════════════════════════════════════════

@dataclass
class BattleSession:
    attacker_id:    str
    defender_id:    Optional[str]
    attacker_stand: Stand
    defender_stand: Stand
    is_pvp:         bool = False
    is_boss:        bool = False

    skip_defender_turn: bool  = False
    bomb_active:        bool  = False
    round_number:       int   = 1
    last_action:        str   = ""   # Narrative text shown in embed
    finished:           bool  = False
    winner_is_attacker: Optional[bool] = None
    db_battle_id:       Optional[int]  = None

    def execute_move(self, move: Move, attacker: Stand, defender: Stand) -> str:
        """
        Executes one move. Returns a single narrative string summarising what happened.
        Mutates HP directly.
        """
        parts = []

        # Accuracy — Foresight adds +25%
        accuracy = move.accuracy
        if attacker.gimmick == "foresight":
            accuracy = min(1.0, accuracy + 0.25)

        if random.random() > accuracy:
            move.pp_remaining -= 1
            return f"💨 **{attacker.name}** used **{move.name}** — but it missed!"

        # Dodge
        if random.random() < defender.dodge_chance:
            move.pp_remaining -= 1
            return f"⚡ **{defender.name}** dodged **{move.name}**!"

        if move.category == "Status":
            move.pp_remaining -= 1
            return f"✨ **{attacker.name}** used **{move.name}**!"

        # Damage
        crit       = random.random() < attacker.crit_chance
        rand_roll  = random.uniform(0.85, 1.0)
        damage     = attacker.calc_damage(move, defender, crit=crit, random_roll=rand_roll)

        # Bomb modifier (Killer Queen)
        bomb_str = ""
        if self.bomb_active and move.category == "Physical":
            damage = int(damage * 1.5)
            self.bomb_active = False
            bomb_str = " 💥 **BOMB!** 1.5×!"

        eff_str = ""
        crit_str = " ⭐ *Critical hit!*" if crit else ""

        # Life reflection (Gold Experience)
        damage, reflect_log = apply_gimmick_on_damage_received(
            self,
            defender_is_attacker=(defender is self.attacker_stand),
            damage=damage,
        )

        defender.current_hp = max(0, defender.current_hp - damage)
        move.pp_remaining -= 1

        parts.append(
            f"**{attacker.name}** used **{move.name}**!{bomb_str}{crit_str}{eff_str}\n"
            f"➤ Dealt **{damage}** damage to **{defender.name}**!"
        )

        if reflect_log:
            parts.append(reflect_log)

        if defender.current_hp <= 0:
            self.finished = True
            self.winner_is_attacker = (attacker is self.attacker_stand)
            parts.append(f"💀 **{defender.name}** fainted!")

        return "\n".join(parts)

    def xp_reward(self) -> int:
        lvl = self.defender_stand.level
        return xp_from_pvp(lvl) if self.is_pvp else xp_from_pve(lvl)

    def coin_reward(self) -> int:
        if self.is_pvp:
            return coins_from_pvp(self.defender_stand.level, self.defender_stand.stars)
        return coins_from_pve(self.defender_stand.level)


# ════════════════════════════════════════════════════════════
# BATTLE VIEW  — move buttons live directly on the embed
# ════════════════════════════════════════════════════════════

class BattleView(discord.ui.View):
    def __init__(self, session: BattleSession, ctx):
        super().__init__(timeout=900)
        self.session = session
        self.ctx     = ctx
        self._rebuild_buttons()

    # ── Button management ─────────────────────────────────────────────────────

    def _rebuild_buttons(self):
        """Clears and re-adds move buttons + utility buttons based on current PP."""
        self.clear_items()
        s = self.session

        # Move buttons — one per available move (up to 4)
        unlock_levels = [1, 1, 15, 30]
        for i, move in enumerate(s.attacker_stand.moves):
            if s.attacker_stand.level < unlock_levels[i]:
                continue  # not unlocked yet
            disabled = move.pp_remaining <= 0
            style = (
                discord.ButtonStyle.danger   if move.category == "Physical" else
                discord.ButtonStyle.primary  if move.category == "Special"  else
                discord.ButtonStyle.secondary
            )
            btn = discord.ui.Button(
                label=f"{move.name} [{move.pp_remaining}/{move.pp}]",
                style=style,
                disabled=disabled,
                row=0 if i < 2 else 1,
                custom_id=f"move_{i}",
            )
            btn.callback = self._make_move_callback(move)
            self.add_item(btn)

        # Utility row
        item_btn = discord.ui.Button(
            label="🩹 Item", style=discord.ButtonStyle.success,
            row=2, custom_id="item_btn"
        )
        item_btn.callback = self._item_callback
        self.add_item(item_btn)

        if not s.is_pvp:
            flee_btn = discord.ui.Button(
                label="🏃 Flee", style=discord.ButtonStyle.secondary,
                row=2, custom_id="flee_btn"
            )
            flee_btn.callback = self._flee_callback
            self.add_item(flee_btn)

    def _make_move_callback(self, move: Move):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.session.attacker_id:
                await interaction.response.send_message("This isn't your battle!", ephemeral=True)
                return
            await interaction.response.defer()
            await self._process_full_turn(interaction, move)
        return callback

    # ── Core turn logic ───────────────────────────────────────────────────────

    async def _process_full_turn(self, interaction: discord.Interaction, move: Move):
        s = self.session

        # ── Player's gimmick on turn start (Restoration heals etc.)
        gimmick_log = apply_gimmick_on_turn_start(s, is_attacker=True)

        # ── Player attacks
        player_log = s.execute_move(move, s.attacker_stand, s.defender_stand)

        # Build narrative
        turn_text = ""
        if gimmick_log:
            turn_text += f"{gimmick_log}\n"
        turn_text += player_log

        if s.finished:
            s.last_action = turn_text
            self._rebuild_buttons()
            await interaction.message.edit(embed=self._build_embed(), view=self)
            await asyncio.sleep(1)
            await self._end_battle(interaction)
            return

        # ── Show player's hit first, pause, then enemy attacks
        s.last_action = turn_text + "\n\n*⏳ Enemy is thinking...*"
        self._rebuild_buttons()
        await interaction.message.edit(embed=self._build_embed(), view=self)
        await asyncio.sleep(1.5)

        # ── Enemy gimmick on turn start
        enemy_gimmick = apply_gimmick_on_turn_start(s, is_attacker=False)

        enemy_log = ""
        if s.skip_defender_turn:
            s.skip_defender_turn = False
            enemy_log = f"⏱️ **{s.defender_stand.name}** is frozen in time — can't move!"
        else:
            enemy_move = ai_choose_move(s.defender_stand, is_boss=s.is_boss)
            # Swap attacker/defender perspective for AI turn
            enemy_log = s.execute_move(enemy_move, s.defender_stand, s.attacker_stand)

        full_text = player_log
        if enemy_gimmick:
            full_text += f"\n{enemy_gimmick}"
        full_text += f"\n\n{enemy_log}"

        s.last_action = full_text
        s.round_number += 1

        if s.finished:
            self._rebuild_buttons()
            await interaction.message.edit(embed=self._build_embed(), view=self)
            await asyncio.sleep(1)
            await self._end_battle(interaction)
            return

        # Sync DB snapshot
        await self._sync_to_db()
        self._rebuild_buttons()
        await interaction.message.edit(embed=self._build_embed(), view=self)

    # ── Item callback ─────────────────────────────────────────────────────────

    async def _item_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.session.attacker_id:
            await interaction.response.send_message("This isn't your battle!", ephemeral=True)
            return

        from src.db import client as db
        stand = self.session.attacker_stand
        existing = await db.get_item(self.session.attacker_id, "healingItem")
        if not existing or existing["quantity"] <= 0:
            await interaction.response.send_message("You have no Healing Bandages!", ephemeral=True)
            return

        base_heal = int(stand.max_hp * 0.30)
        primary   = await db.get_primary_stand(self.session.attacker_id)
        if primary and primary["stand_name"] == "Crazy Diamond":
            base_heal = int(base_heal * 1.25)

        stand.current_hp = min(stand.max_hp, stand.current_hp + base_heal)
        await db.consume_item(self.session.attacker_id, "healingItem")

        self.session.last_action = f"🩹 Used **Healing Bandage** → restored **{base_heal} HP**!"
        await interaction.response.defer()
        self._rebuild_buttons()
        await interaction.message.edit(embed=self._build_embed(), view=self)

    # ── Flee callback ─────────────────────────────────────────────────────────

    async def _flee_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.session.attacker_id:
            await interaction.response.send_message("This isn't your battle!", ephemeral=True)
            return

        await interaction.response.defer()

        if random.random() < 0.50:
            from src.db import client as db
            if self.session.db_battle_id:
                await db.delete_active_battle(self.session.db_battle_id)
            self.clear_items()
            embed = discord.Embed(
                title="🏃 Got away safely!",
                description="You fled the battle. No rewards.",
                color=0x888888,
            )
            await interaction.message.edit(embed=embed, view=None)
            self.stop()
        else:
            self.session.last_action = "🏃 Tried to flee — but couldn't escape!"
            self._rebuild_buttons()
            await interaction.message.edit(embed=self._build_embed(), view=self)

    # ── Embed builder ─────────────────────────────────────────────────────────

    def _build_embed(self) -> discord.Embed:
        s   = self.session
        att = s.attacker_stand
        dfd = s.defender_stand

        embed = discord.Embed(
            title=f"⚔️ {att.name}  vs  {dfd.name}",
            color=0xFF4444,
        )

        # Enemy HP bar (top — Pokémon shows enemy first)
        embed.add_field(
            name=f"🤖 {dfd.name}  Lv.{dfd.level}",
            value=f"{hp_bar(dfd.current_hp, dfd.max_hp)}  {dfd.current_hp}/{dfd.max_hp} HP",
            inline=False,
        )

        # Player HP bar
        star_str = "★" * att.stars
        embed.add_field(
            name=f"👤 {att.name}  Lv.{att.level} {star_str}",
            value=f"{hp_bar(att.current_hp, att.max_hp)}  {att.current_hp}/{att.max_hp} HP",
            inline=False,
        )

        # Last action log
        if s.last_action:
            embed.add_field(
                name="📋 What happened",
                value=s.last_action,
                inline=False,
            )

        embed.set_footer(text=f"Round {s.round_number}  |  What will {att.name} do?")
        return embed

    # ── End battle ────────────────────────────────────────────────────────────

    async def _end_battle(self, interaction: discord.Interaction):
        from src.db import client as db
        import random as _r
        s = self.session
        self.clear_items()

        if s.winner_is_attacker:
            xp    = s.xp_reward()
            coins = s.coin_reward()

            primary = await db.get_primary_stand(s.attacker_id)
            if primary and primary["stand_name"] == "Harvest":
                coins = int(coins * 1.25)
            if primary and primary["stand_name"] == "Gold Experience" and _r.random() < 0.05:
                xp *= 2

            user = await db.get_user(s.attacker_id)
            await db.add_coins(s.attacker_id, coins)
            await db.update_user(s.attacker_id, win_count=user["win_count"] + 1)

            # Advance win quests
            from src.cogs.exploration import _advance_quest
            from src.utils.embeds import quest_complete_embed
            completed = await _advance_quest(s.attacker_id, "wins")
            if s.is_pvp:
                completed += await _advance_quest(s.attacker_id, "pvp_wins")
            for quest_title, rewards in completed:
                try:
                    await interaction.channel.send(embed=quest_complete_embed(quest_title, rewards))
                except Exception:
                    pass

            if primary:
                updated    = await db.add_stand_xp(primary["id"], xp)
                fired_evos = await db.check_pending_evolutions(
                    s.attacker_id, primary["id"], updated["level"]
                )

            await db.log_battle(
                attacker_id  = s.attacker_id,
                defender_id  = s.defender_id,
                winner_id    = s.attacker_id,
                stand_used   = s.attacker_stand.name,
                xp_gained    = xp,
                coins_gained = coins,
                is_pvp       = s.is_pvp,
            )

            evo_str = ""
            if fired_evos if 'fired_evos' in dir() else False:
                evo_str = "\n🌟 **Your stand evolved!**"

            embed = discord.Embed(
                title="🏆 Victory!",
                description=(
                    f"**{s.defender_stand.name}** was defeated!\n\n"
                    f"+**{xp}** XP  |  +**{coins}** 🪙{evo_str}"
                ),
                color=0x00FF88,
            )
        else:
            user = await db.get_user(s.attacker_id)
            await db.update_user(s.attacker_id, loss_count=user["loss_count"] + 1)
            await db.log_battle(
                attacker_id  = s.attacker_id,
                defender_id  = s.defender_id,
                winner_id    = s.defender_id or "pve",
                stand_used   = s.attacker_stand.name,
                xp_gained    = 0,
                coins_gained = 0,
                is_pvp       = s.is_pvp,
            )
            embed = discord.Embed(
                title="💀 Defeated!",
                description=f"**{s.attacker_stand.name}** fainted. No rewards.",
                color=0xFF4444,
            )

        if s.db_battle_id:
            await db.delete_active_battle(s.db_battle_id)

        # Set PvE battle cooldown (3 min). No cooldown for PvP.
        if not s.is_pvp:
            await db.set_cooldown(s.attacker_id, "sbattle", 180)

        await interaction.message.edit(embed=embed, view=None)
        self.stop()

    async def _sync_to_db(self):
        from src.db import client as db
        s = self.session
        if s.db_battle_id:
            await db.update_active_battle(
                battle_id    = s.db_battle_id,
                attacker_hp  = s.attacker_stand.current_hp,
                defender_hp  = s.defender_stand.current_hp,
                turn         = "attacker",
                state        = {},
            )

    async def on_timeout(self):
        self.clear_items()
        try:
            await self.ctx.send("⏱️ Battle timed out. Winner determined by HP remaining.")
        except Exception:
            pass
        self.stop()


# ── Utility ───────────────────────────────────────────────────────────────────

def hp_bar(current: int, maximum: int, length: int = 12) -> str:
    ratio  = current / maximum if maximum > 0 else 0
    filled = round(ratio * length)
    color  = "🟩" if ratio > 0.5 else "🟨" if ratio > 0.25 else "🟥"
    return color * filled + "⬛" * (length - filled)