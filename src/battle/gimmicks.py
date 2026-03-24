"""
battle/gimmicks.py
Gimmick (passive trait) handlers.
Each function receives the BattleSession and mutates state, returning a log string.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.battle.engine import BattleSession


def apply_gimmick_on_turn_start(session: "BattleSession", is_attacker: bool) -> str | None:
    """
    Called at the start of each combatant's turn.
    Returns a flavour string if the gimmick triggered, else None.
    """
    stand = session.attacker_stand if is_attacker else session.defender_stand

    if stand.gimmick == "restoration" and not stand.gimmick_used:
        # Crazy Diamond: heal 10% HP each turn (passive, always active — no gimmick_used flag)
        heal = max(1, int(stand.max_hp * 0.10))
        stand.current_hp = min(stand.max_hp, stand.current_hp + heal)
        return f"💎 **Crazy Diamond** restored {heal} HP!"

    if stand.gimmick == "scavenge":
        # Harvest: handled in reward calculation, nothing to do here
        pass

    return None


def apply_gimmick_on_damage_received(session: "BattleSession", defender_is_attacker: bool, damage: int) -> tuple[int, str | None]:
    """
    Called after damage is calculated but before it's applied.
    Returns (modified_damage, log_string | None).
    """
    stand = session.attacker_stand if defender_is_attacker else session.defender_stand
    attacker = session.defender_stand if defender_is_attacker else session.attacker_stand

    if stand.gimmick == "life_reflection":
        # Gold Experience: reflect 20% of physical damage received back to attacker
        reflect = int(damage * 0.20)
        if reflect > 0:
            attacker.current_hp = max(0, attacker.current_hp - reflect)
            return damage, f"✨ **Life Reflection** reflected {reflect} damage back!"

    return damage, None


def try_time_stop(session: "BattleSession") -> bool:
    """
    The World: once per battle, skip opponent's next turn.
    Returns True if time stop was triggered.
    """
    stand = session.attacker_stand  # Only called when attacker has The World
    if stand.gimmick == "time_stop" and not stand.gimmick_used:
        stand.gimmick_used = True
        session.skip_defender_turn = True
        return True
    return False


def apply_bomb_set(session: "BattleSession") -> str | None:
    """
    Killer Queen: next physical hit on opponent deals 1.5x on contact.
    Set the bomb flag; the damage formula checks for it.
    """
    stand = session.attacker_stand
    if stand.gimmick == "bomb_set" and not stand.gimmick_used:
        stand.gimmick_used = True
        session.bomb_active = True
        return "💣 **Bomb Set!** The next physical hit will detonate for 1.5x!"
    return None


GIMMICK_DESCRIPTIONS = {
    "time_stop":        "⏱️ **Time Stop**: Once per battle, skip the opponent's next turn",
    "life_reflection":  "✨ **Life Reflection**: Reflect 20% of received physical damage",
    "restoration":      "💎 **Restoration**: Heal 10% HP at the start of each turn",
    "bomb_set":         "💣 **Bomb Set**: Next physical hit placed on opponent deals 1.5×",
    "precision_strike": "🎯 **Precision Strike**: +15% critical hit chance",
    "foresight":        "👁️ **Foresight**: +25% accuracy on all moves",
    "scavenge":         "🌾 **Scavenge**: Gain bonus Coins after winning a battle",
}
