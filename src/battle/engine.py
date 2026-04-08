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
from src.battle.effects import get_damage_modifier, apply_move_effect
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
    defender_items:     Optional[dict] = None  # item_id -> quantity for reveals_info effect
    current_turn_user_id: Optional[str] = None  # Discord user ID of player whose turn it is (for PvP)

    def execute_move(self, move: Move, attacker: Stand, defender: Stand) -> str:
        """
        Executes one move. Returns a single narrative string summarising what happened.
        Mutates HP directly.
        """
        parts = []

        # Accuracy — Foresight adds +25%, unstoppable bypasses this check entirely
        accuracy = move.accuracy
        if attacker.gimmick == "foresight":
            accuracy = min(1.0, accuracy + 0.25)

        if move.effect != "unstoppable" and random.random() > accuracy:
            move.pp_remaining -= 1
            return f"💨 **{attacker.name}** used **{move.name}** — but it missed!"

        # Dodge (ignores_dodge effect bypasses this check)
        if random.random() < defender.dodge_chance and move.effect != "ignores_dodge":
            move.pp_remaining -= 1
            return f"⚡ **{defender.name}** dodged **{move.name}**!"

        if move.category == "Status":
            move.pp_remaining -= 1
            return f"✨ **{attacker.name}** used **{move.name}**!"

        # Damage
        crit       = random.random() < attacker.crit_chance
        rand_roll  = random.uniform(0.85, 1.0)
        damage     = attacker.calc_damage(move, defender, crit=crit, random_roll=rand_roll)

        # Apply damage modifier effects (hit_3_times, high_crit, bypass_def, etc.)
        damage_mult, effect_dmg_str = get_damage_modifier(move.effect, attacker, defender, move, damage)
        damage = int(damage * damage_mult)

        # Bomb modifier (Killer Queen)
        bomb_str = ""
        if self.bomb_active and move.category == "Physical":
            damage = int(damage * 1.5)
            self.bomb_active = False
            bomb_str = " 💥 **BOMB!** 1.5×!"

        eff_str = effect_dmg_str
        crit_str = " ⭐ *Critical hit!*" if crit else ""

        # Apply Move Effects (status, healing, debuffs, etc.)
        eff_str += apply_move_effect(attacker, defender, move, damage, session=self)

        # [SYNERGY] Time Stop Mastery: Star Platinum + The World
        att_stands = {attacker.name, attacker.secondary_stand_name}
        if {"Star Platinum", "The World"}.issubset(att_stands) and self.skip_defender_turn:
            damage = int(damage * 1.5)
            eff_str += " 🛑 *Time Stop Bonus!*"

        # Life reflection (Gold Experience)
        damage, reflect_log = apply_gimmick_on_damage_received(
            self,
            defender_is_attacker=(defender is self.attacker_stand),
            damage=damage,
        )

        # [SYNERGY] Fate Manipulation: Tohth + Khnum
        def_stands = {defender.name, defender.secondary_stand_name}
        if {"Tohth", "Khnum"}.issubset(def_stands) and damage > 0:
            if random.random() < 0.10:
                attacker.current_hp = max(0, attacker.current_hp - damage)
                move.pp_remaining -= 1
                return f"👁️ **{defender.name}** manipulated fate and reflected **{damage}** damage back to **{attacker.name}**!"

        defender.current_hp = max(0, defender.current_hp - damage)
        move.pp_remaining -= 1

        parts.append(
            f"**{attacker.name}** used **{move.name}**!{bomb_str}{crit_str}{eff_str}\n"
            f"➤ Dealt **{damage}** damage to **{defender.name}**!"
        )

        # [SYNERGY] Vampiric Power: The World + Cream
        if {"The World", "Cream"}.issubset(att_stands) and damage > 0:
            lifesteal = max(1, int(damage * 0.08))
            attacker.current_hp = min(attacker.max_hp, attacker.current_hp + lifesteal)
            parts.append(f"🦇 **{attacker.name}** absorbed **{lifesteal}** HP!")

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
            s = self.session
            # For PvP: check if it's this player's turn
            if s.is_pvp:
                if str(interaction.user.id) != s.current_turn_user_id:
                    await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
                    return
            else:
                # For PvE: only attacker can act
                if str(interaction.user.id) != s.attacker_id:
                    await interaction.response.send_message("This isn't your battle!", ephemeral=True)
                    return
            await interaction.response.defer()
            await self._process_full_turn(interaction, move)
        return callback

    # ── Core turn logic ───────────────────────────────────────────────────────

    async def _process_full_turn(self, interaction: discord.Interaction, move: Move):
        s = self.session
        
        # Determine who is attacking based on whose turn it is
        if s.is_pvp:
            # In PvP, determine attacker/defender based on current turn
            is_attacker_turn = (s.current_turn_user_id == s.attacker_id)
            if is_attacker_turn:
                active_stand = s.attacker_stand
                target_stand = s.defender_stand
                active_player_name = await self._get_player_name(s.attacker_id)
                target_player_name = await self._get_player_name(s.defender_id)
            else:
                active_stand = s.defender_stand
                target_stand = s.attacker_stand
                active_player_name = await self._get_player_name(s.defender_id)
                target_player_name = await self._get_player_name(s.attacker_id)
        else:
            # PvE: always attacker vs defender
            is_attacker_turn = True
            active_stand = s.attacker_stand
            target_stand = s.defender_stand
            active_player_name = None
            target_player_name = None

        # ── Active player's gimmick on turn start
        gimmick_log = apply_gimmick_on_turn_start(s, is_attacker=is_attacker_turn)

        # ── Active player attacks
        player_log = s.execute_move(move, active_stand, target_stand)

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

        # ── FOR PvP: Switch turn and wait for opponent ──
        if s.is_pvp:
            s.last_action = turn_text
            
            # Apply End of Turn DOT (Burn) before switching turns
            burn_text = await self._apply_burn_damage()
            if burn_text:
                s.last_action += burn_text
            
            if s.finished:
                self._rebuild_buttons()
                await interaction.message.edit(embed=self._build_embed(), view=self)
                await asyncio.sleep(1)
                await self._end_battle(interaction)
                return
            
            # Switch turn to opponent
            s.current_turn_user_id = s.defender_id if s.current_turn_user_id == s.attacker_id else s.attacker_id
            s.round_number += 1
            
            # Sync to DB
            await self._sync_to_db()
            self._rebuild_buttons()
            
            # Update embed and ping next player
            await interaction.message.edit(embed=self._build_embed(), view=self)
            
            # Send a follow-up message pinging the next player
            next_player = await self.ctx.bot.fetch_user(int(s.current_turn_user_id))
            await interaction.followup.send(
                f"{next_player.mention} It's your turn!",
                ephemeral=False
            )
            return

        # ── FOR PvE: Continue with AI turn ──
        # Show player's hit first, pause, then enemy attacks
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

        # ── Apply End of Turn DOT (Burn)
        burn_text = await self._apply_burn_damage()
        if burn_text:
            full_text += burn_text

        s.last_action = full_text
        s.round_number += 1

        if s.finished:
            self._rebuild_buttons()
            await interaction.message.edit(embed=self._build_embed(), view=self)
            await asyncio.sleep(1)
            await self._end_battle(interaction)
            return

        self._rebuild_buttons()
        await interaction.message.edit(embed=self._build_embed(), view=self)

    # ── Item callback ─────────────────────────────────────────────────────────

    async def _item_callback(self, interaction: discord.Interaction):
        s = self.session
        # For PvP: check if it's this player's turn
        if s.is_pvp:
            if str(interaction.user.id) != s.current_turn_user_id:
                await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
                return
            # Determine which stand is active
            if s.current_turn_user_id == s.attacker_id:
                stand = s.attacker_stand
                user_id = s.attacker_id
            else:
                stand = s.defender_stand
                user_id = s.defender_id
        else:
            # For PvE: only attacker can act
            if str(interaction.user.id) != s.attacker_id:
                await interaction.response.send_message("This isn't your battle!", ephemeral=True)
                return
            stand = s.attacker_stand
            user_id = s.attacker_id

        from src.db import client as db
        existing = await db.get_item(user_id, "healingItem")
        if not existing or existing["quantity"] <= 0:
            await interaction.response.send_message("You have no Healing Bandages!", ephemeral=True)
            return

        base_heal = int(stand.max_hp * 0.30)
        primary   = await db.get_primary_stand(user_id)
        if primary and primary["stand_name"] == "Crazy Diamond":
            base_heal = int(base_heal * 1.25)

        stand.current_hp = min(stand.max_hp, stand.current_hp + base_heal)
        await db.consume_item(user_id, "healingItem")

        s.last_action = f"🩹 Used **Healing Bandage** → restored **{base_heal} HP**!"
        await interaction.response.defer()
        
        # For PvP, switch turns after using item
        if s.is_pvp:
            s.current_turn_user_id = s.defender_id if s.current_turn_user_id == s.attacker_id else s.attacker_id
            await self._sync_to_db()
            self._rebuild_buttons()
            await interaction.message.edit(embed=self._build_embed(), view=self)
            
            # Ping next player
            next_player = await self.ctx.bot.fetch_user(int(s.current_turn_user_id))
            await interaction.followup.send(
                f"{next_player.mention} It's your turn!",
                ephemeral=False
            )
        else:
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
        
        # Determine color and title based on turn (for PvP)
        if s.is_pvp and s.current_turn_user_id:
            if s.current_turn_user_id == s.attacker_id:
                color = 0x00FF00  # Green for attacker's turn
                turn_indicator = f"<@{s.attacker_id}>'s Turn"
            else:
                color = 0x4169E1  # Blue for defender's turn
                turn_indicator = f"<@{s.defender_id}>'s Turn"
            title = f"⚔️ {att.name} vs {dfd.name} — {turn_indicator}"
        else:
            color = 0xFF4444  # Red for PvE
            title = f"⚔️ {att.name} vs {dfd.name}"

        embed = discord.Embed(
            title=title,
            color=color,
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

        # Footer with round and turn info
        if s.is_pvp:
            current_player = "<@" + s.current_turn_user_id + ">" if s.current_turn_user_id else "Player"
            footer_text = f"Round {s.round_number}  |  {current_player}'s turn to act!"
        else:
            footer_text = f"Round {s.round_number}  |  What will {att.name} do?"
        
        embed.set_footer(text=footer_text)
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

    # ── Helper methods ────────────────────────────────────────────────────────
    
    async def _get_player_name(self, user_id: str) -> str:
        """Get player display name from user ID."""
        try:
            user = await self.ctx.bot.fetch_user(int(user_id))
            return user.name
        except:
            return "Player"
    
    async def _apply_burn_damage(self) -> str:
        """Apply burn damage to both stands. Returns narrative text."""
        s = self.session
        burn_text = ""
        
        for st_obj, opponent in [(s.attacker_stand, s.defender_stand), (s.defender_stand, s.attacker_stand)]:
            if st_obj.current_hp > 0 and st_obj.status == "burn":
                burn_dmg = max(1, int(st_obj.max_hp / 16))
                
                # Magician's Red + Sun synergy: +50% burn damage
                opponent_stands = {opponent.name, opponent.secondary_stand_name}
                if {"Magician's Red", "The Sun"}.issubset(opponent_stands):
                    burn_dmg = int(burn_dmg * 1.5)

                st_obj.current_hp = max(0, st_obj.current_hp - burn_dmg)
                burn_text += f"\n🔥 **{st_obj.name}** took **{burn_dmg}** burn damage!"

                if st_obj.current_hp <= 0:
                    s.finished = True
                    s.winner_is_attacker = (st_obj is s.defender_stand)
                    burn_text += f"\n💀 **{st_obj.name}** fainted from Burn!"
                    break
        
        return burn_text

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
                current_turn_user_id = s.current_turn_user_id,
            )

    async def on_timeout(self):
        from src.db import client as db
        
        self.clear_items()
        try:
            await self.ctx.send("⏱️ Battle timed out. Winner determined by HP remaining.")
        except Exception:
            pass
        
        # Clean up the database record so user can start new battles
        if self.session.db_battle_id:
            await db.delete_active_battle(self.session.db_battle_id)
        
        self.stop()


# ── Utility ───────────────────────────────────────────────────────────────────

def hp_bar(current: int, maximum: int, length: int = 12) -> str:
    ratio  = current / maximum if maximum > 0 else 0
    filled = round(ratio * length)
    color  = "🟩" if ratio > 0.5 else "🟨" if ratio > 0.25 else "🟥"
    return color * filled + "⬛" * (length - filled)