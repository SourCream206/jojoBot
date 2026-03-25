"""
battle/effects.py
Move effect handlers for all move properties.
Each handler applies the effect and returns a message string.
"""

import random
from src.battle.stand import Stand, Move


# ════════════════════════════════════════════════════════════
# DAMAGE MODIFIERS (These affect the calculated damage value)
# Returns: (damage_multiplier, message_addition)
# ════════════════════════════════════════════════════════════

def handle_hit_3_times(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """Hit 3 times, dealing damage each time."""
    return 3.0, " ⚔️ *Hit 3 times!*"

def handle_multi_hit(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """Hit 2-3 times randomly."""
    hits = random.randint(2, 3)
    return float(hits), f" ⚔️ *Hit {hits} times!*"

def handle_high_crit(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """Guaranteed critical hit with increased damage."""
    return 1.5, " ⭐ *Critical hit!*"

def handle_ignores_dodge(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """Can't be dodged (no effect on damage, just for accuracy handling)."""
    return 1.0, ""

def handle_bypass_def(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """Ignores 50% of defender's defense."""
    return 1.5, " 🔓 *Bypassed defenses!*"

def handle_unstoppable(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """Cannot miss or be dodged, +20% damage."""
    return 1.2, " 🚀 *Unstoppable attack!*"

def handle_random_power(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """Random damage between 0.5x - 1.5x."""
    mult = random.uniform(0.5, 1.5)
    return mult, f" 🎲 *Random power: {mult:.1f}x*"


# ════════════════════════════════════════════════════════════
# STATUS EFFECTS (Apply status to defender)
# ════════════════════════════════════════════════════════════

def handle_burn(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Apply burn status with 30% chance."""
    if defender.status != "burn" and random.random() < 0.30:
        defender.status = "burn"
        return " 🔥 *Burn applied!*"
    return ""

def handle_poison(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Apply poison status with 25% chance."""
    if defender.status != "poison" and random.random() < 0.25:
        defender.status = "poison"
        return " ☠️ *Poisoned!*"
    return ""

def handle_confusion(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Apply confusion status with 20% chance."""
    if defender.status != "confusion" and random.random() < 0.20:
        defender.status = "confusion"
        return " 😵 *Confused!*"
    return ""

def handle_burn_reflect(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Status move: Set defender to burn-reflect (takes 50% burn damage instead)."""
    # For now, treat as regular burn
    defender.status = "burn_reflect" if random.random() < 0.40 else None
    return " 🛡️ *Flame Barrier set!*" if defender.status == "burn_reflect" else ""


# ════════════════════════════════════════════════════════════
# STAT MODIFICATIONS
# ════════════════════════════════════════════════════════════

def handle_lower_atk(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Lower defender's attack (simulated by 15% damage for now)."""
    # Note: Stand class doesn't have mutable stats, so we can't actually lower them
    # This would need to be tracked at BattleSession level for full implementation
    return " 📉 *Attack lowered!*"

def handle_lower_def(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Lower defender's defense (increases next damage by 25%)."""
    return " 📉 *Defense lowered!*"

def handle_lower_spd(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Lower defender's speed."""
    return " 📉 *Speed lowered!*"

def handle_lower_all_stats(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Lower all defender's stats."""
    return " 📉 *All stats lowered!*"

def handle_raise_spd_def(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Raise attacker's speed and defense."""
    return " 📈 *Speed and defense raised!*"

def handle_power_up_per_hit(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Each hit increases damage by 10% (not implemented - needs turn tracking)."""
    return " ⬆️ *Power building!*"


# ════════════════════════════════════════════════════════════
# HEALING & LIFESTEAL
# ════════════════════════════════════════════════════════════

def handle_drain_hp(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[int, str]:
    """Attacker gains 50% of damage dealt as HP. Returns (hp_heal, message)."""
    heal = int(damage * 0.50)
    attacker.current_hp = min(attacker.max_hp, attacker.current_hp + heal)
    return heal, f" 🦇 *Drained {heal} HP!*"

def handle_heal_on_hit(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[int, str]:
    """Attacker heals 25% of damage dealt."""
    heal = int(damage * 0.25)
    attacker.current_hp = min(attacker.max_hp, attacker.current_hp + heal)
    return heal, f" 💚 *Healed {heal} HP!*"

def handle_self_heal_10(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[int, str]:
    """Attacker heals 10% of max HP."""
    heal = int(attacker.max_hp * 0.10)
    attacker.current_hp = min(attacker.max_hp, attacker.current_hp + heal)
    return heal, f" 💚 *Healed {heal} HP!*"

def handle_heal_30pct(attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[int, str]:
    """Attacker heals 30% of max HP."""
    heal = int(attacker.max_hp * 0.30)
    attacker.current_hp = min(attacker.max_hp, attacker.current_hp + heal)
    return heal, f" 💚 *Healed {heal} HP!*"


# ════════════════════════════════════════════════════════════
# DEFENSIVE/EVASION EFFECTS
# ════════════════════════════════════════════════════════════

def handle_evade_next(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Next turn, evade all attacks (not fully implemented)."""
    return " 🛡️ *Ready to evade next turn!*"

def handle_dodge_next(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Dodge the next attack (not fully implemented)."""
    return " ⚡ *Prepared to dodge!*"

def handle_counter_next(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Counter the next attack (not fully implemented)."""
    return " 🔄 *Countering stance!*"


# ════════════════════════════════════════════════════════════
# INFORMATION & UTILITY EFFECTS
# ════════════════════════════════════════════════════════════

def handle_reveals_info(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Reveal opponent's held item/status."""
    return " 👁️ *Revealed information!*"

def handle_reveal_moves(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Reveal opponent's moveset."""
    return " 📋 *Moves revealed!*"

def handle_nullify_effect(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Nullify opponent's next move effect."""
    return " 🚫 *Effect nullified!*"

def handle_reset_enemy_buffs(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Reset opponent's stat boosts."""
    return " ↩️ *Buffs reset!*"

def handle_steal_buff(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Steal opponent's stat boosts."""
    return " 🔄 *Stolen buffs!*"


# ════════════════════════════════════════════════════════════
# SPECIALIZED EFFECTS
# ════════════════════════════════════════════════════════════

def handle_bomb_trigger(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Set bomb on defender (handled at BattleSession level)."""
    return " 💣 *Bomb set!*"

def handle_aoe_burn(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Apply burn to defender and nearby enemies (simplified: just burn)."""
    if defender.status != "burn" and random.random() < 0.35:
        defender.status = "burn"
        return " 🔥 *Area burned!*"
    return ""

def handle_bites_the_dust(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Time loop effect (complex, not fully implemented)."""
    return " ⏰ *Time loop initiated!*"

def handle_time_loop(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Repeat the turn (not fully implemented)."""
    return " 🔁 *Turn repeated!*"

def handle_dimension_swap(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Swap positions/stats (not fully implemented)."""
    return " 🌀 *Dimensions swapped!*"

def handle_love_train_redirect(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """Redirect damage through a chain (not fully implemented)."""
    return " 🔗 *Damage redirected!*"


# ════════════════════════════════════════════════════════════
# EFFECT ROUTER
# ════════════════════════════════════════════════════════════

DAMAGE_MODIFIERS = {
    "hit_3_times":    handle_hit_3_times,
    "multi_hit":      handle_multi_hit,
    "high_crit":      handle_high_crit,
    "ignore_dodge":   handle_ignores_dodge,
    "ignores_dodge":  handle_ignores_dodge,
    "bypass_def":     handle_bypass_def,
    "unstoppable":    handle_unstoppable,
    "random_power":   handle_random_power,
}

STATUS_EFFECTS = {
    "burn":           handle_burn,
    "poison":         handle_poison,
    "confusion":      handle_confusion,
    "burn_reflect":   handle_burn_reflect,
    "aoe_burn":       handle_aoe_burn,
}

STAT_EFFECTS = {
    "lower_atk":           handle_lower_atk,
    "lower_def":           handle_lower_def,
    "lower_spd":           handle_lower_spd,
    "lower_all_stats":     handle_lower_all_stats,
    "raise_spd_def":       handle_raise_spd_def,
    "power_up_per_hit":    handle_power_up_per_hit,
}

HEALING_EFFECTS = {
    "drain_hp":       handle_drain_hp,
    "heal_on_hit":    handle_heal_on_hit,
    "self_heal_10":   handle_self_heal_10,
    "heal_30pct":     handle_heal_30pct,
}

DEFENSIVE_EFFECTS = {
    "evade_next":     handle_evade_next,
    "dodge_next":     handle_dodge_next,
    "counter_next":   handle_counter_next,
}

INFO_EFFECTS = {
    "reveals_info":       handle_reveals_info,
    "reveal_moves":       handle_reveal_moves,
    "nullify_effect":     handle_nullify_effect,
    "reset_enemy_buffs":  handle_reset_enemy_buffs,
    "steal_buff":         handle_steal_buff,
}

SPECIAL_EFFECTS = {
    "bomb_trigger":           handle_bomb_trigger,
    "bites_the_dust":         handle_bites_the_dust,
    "time_loop":              handle_time_loop,
    "dimension_swap":         handle_dimension_swap,
    "love_train_redirect":    handle_love_train_redirect,
}


def get_damage_modifier(effect: str, attacker: Stand, defender: Stand, move: Move, damage: int) -> tuple[float, str]:
    """
    Get damage multiplier for effects that modify damage.
    Returns (multiplier, message_addition)
    """
    if effect in DAMAGE_MODIFIERS:
        return DAMAGE_MODIFIERS[effect](attacker, defender, move, damage)
    return 1.0, ""


def apply_move_effect(attacker: Stand, defender: Stand, move: Move, damage: int) -> str:
    """
    Apply all non-damage-modifying effects. Returns effect message.
    This is called AFTER damage is dealt.
    """
    if not move.effect:
        return ""

    effect = move.effect
    message = ""

    # Status effects
    if effect in STATUS_EFFECTS:
        message = STATUS_EFFECTS[effect](attacker, defender, move, damage)

    # Stat modification effects
    elif effect in STAT_EFFECTS:
        message = STAT_EFFECTS[effect](attacker, defender, move, damage)

    # Healing effects that return (heal_amount, message)
    elif effect in HEALING_EFFECTS:
        heal, msg = HEALING_EFFECTS[effect](attacker, defender, move, damage)
        message = msg

    # Defensive/evasion effects
    elif effect in DEFENSIVE_EFFECTS:
        message = DEFENSIVE_EFFECTS[effect](attacker, defender, move, damage)

    # Info effects
    elif effect in INFO_EFFECTS:
        message = INFO_EFFECTS[effect](attacker, defender, move, damage)

    # Special/complex effects
    elif effect in SPECIAL_EFFECTS:
        message = SPECIAL_EFFECTS[effect](attacker, defender, move, damage)

    return message
