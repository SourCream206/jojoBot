"""
utils/embeds.py
Shared embed builders used across cogs.
"""

import discord
from src.utils.constants import RARITY_COLORS, RARITY_EMOJIS, META_PASSIVES
from src.utils.constants import xp_to_next_level
from src.utils.stands_data import get_image, get_emoji


def get_active_synergies(primary: str, secondary: str) -> list[str]:
    if not primary or not secondary:
        return []
    
    synergies = []
    
    if primary == "Star Platinum" and secondary == "The World":
        synergies.append("Time Stop Mastery (Bonus Damage in Time Stop)")
    elif primary == "Star Platinum" and secondary in ("Hierophant Green", "Silver Chariot"):
        synergies.append("JoBro Buff (+5 HP, +5% Max HP)")
    elif primary == "Star Platinum" and secondary == "Hermit Purple":
        synergies.append("Joestar Bloodline (+10% Max HP)")
    elif primary in ("The Fool", "Horus", "Strength") and secondary in ("The Fool", "Horus", "Strength"):
        synergies.append("Animal Jam (+5 Base Power, +5% Damage)")
    elif primary == "Dark Blue Moon" and secondary == "Strength":
        synergies.append("Cruise Ship (+10% Defense)")
    elif primary == "Osiris" and secondary == "Atum":
        synergies.append("Darby Brothers (Highest Luck in Gacha Rolls)")
    elif primary == "The World" and secondary == "Cream":
        synergies.append("Vampiric Power (+8% Lifesteal)")
    elif primary == "Magician's Red" and secondary == "The Sun":
        synergies.append("Scorching Heat (Burn deals 1.5x Damage)")
    elif primary == "Tohth" and secondary == "Khnum":
        synergies.append("Fate Manipulation (10% Reflect Chance)")
    elif primary == "Anubis" and secondary == "Silver Chariot":
        synergies.append("Blade Master (+5% Speed, +6% Damage)")
    elif primary == "Hanged Man" and secondary == "Emperor":
        synergies.append("Perfect Execution (+20% Critical Damage)")
    elif primary == "Justice" and secondary == "Lovers":
        synergies.append("Undead Link (Take 10% less damage when under 50% HP)")
        
    return synergies


def stand_roll_embed(stand_name: str, rarity: str, stars: int, is_shiny: bool) -> discord.Embed:
    color        = RARITY_COLORS.get(rarity, 0xAAAAAA)
    rarity_emoji = RARITY_EMOJIS.get(rarity, "⚪")
    stand_emoji  = get_emoji(stand_name)
    shiny_str    = " ✨ **SHINY!**" if is_shiny else ""
    star_str     = "★" * stars

    embed = discord.Embed(
        title=f"{rarity_emoji} You obtained **{stand_name}**!{shiny_str}",
        color=color,
    )
    embed.add_field(name="Rarity", value=f"{rarity_emoji} {rarity}", inline=True)
    embed.add_field(name="Stars",  value=star_str,                   inline=True)
    if stand_emoji:
        embed.add_field(name="Stand", value=stand_emoji, inline=True)

    image_url = get_image(stand_name, stars)
    if image_url:
        embed.set_image(url=image_url)

    return embed


def stand_info_embed(stand_row: dict, catalog_entry: dict | None = None, stand_obj=None) -> discord.Embed:
    """Rich embed for Sinfo — shows star-correct image."""
    name   = stand_row["stand_name"]
    stars  = stand_row["stars"]
    level  = stand_row["level"]
    shiny  = stand_row.get("is_shiny", False)

    rarity    = catalog_entry["rarity"] if catalog_entry else "Common"
    color     = RARITY_COLORS.get(rarity, 0xAAAAAA)
    emoji     = get_emoji(name)
    image_url = get_image(name, stars)

    title = f"{emoji} {name}".strip() if emoji else name
    if shiny:
        title += " ✨"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Level",   value=str(level),                     inline=True)
    embed.add_field(name="Stars",   value="★" * stars,                    inline=True)
    embed.add_field(name="Shiny",   value="✨ Yes" if shiny else "No",    inline=True)

    xp_needed = xp_to_next_level(level)
    embed.add_field(name="XP",     value=f"{stand_row['exp']}/{xp_needed}", inline=True)
    embed.add_field(name="Merges", value=str(stand_row["merge_count"]),      inline=True)
    embed.add_field(name="Primary",value="⭐ Yes" if stand_row["is_primary"] else "No", inline=True)

    if stand_obj:
        stats_str = (
            f"HP: {stand_obj.max_hp} | ATK: {stand_obj.atk} | DEF: {stand_obj.defense}\n"
            f"SPA: {stand_obj.spa} | SPD: {stand_obj.spd} | RNG: {stand_obj.rng}"
        )
        embed.add_field(name="📊 Stats", value=stats_str, inline=False)

        unlock_levels = [1, 1, 15, 30]
        moves_lines = []
        for i, m in enumerate(stand_obj.moves):
            locked = f" *(unlocks Lv.{unlock_levels[i]})*" if level < unlock_levels[i] else ""
            moves_lines.append(
                f"• **{m.name}** ({m.category}, Pwr {m.power}, Acc {int(m.accuracy*100)}%, PP {m.pp}){locked}"
            )
        embed.add_field(name="🥊 Moves", value="\n".join(moves_lines), inline=False)

    if image_url:
        embed.set_image(url=image_url)

    return embed


def profile_embed(user: dict, primary_stand: dict | None, secondary_stand: dict | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"🧿 {user['username']}'s Profile",
        color=0x9B59B6,
    )
    embed.add_field(name="📍 Area",     value=user["current_area"],  inline=True)
    embed.add_field(name="⚔️ W/L",     value=f"{user['win_count']}W / {user['loss_count']}L", inline=True)
    embed.add_field(name="🪙 Coins",   value=str(user["coins"]),    inline=True)
    embed.add_field(name="💎 Diamonds",value=str(user["diamonds"]), inline=True)

    if primary_stand:
        name   = primary_stand["stand_name"]
        lvl    = primary_stand["level"]
        stars  = primary_stand["stars"]
        exp    = primary_stand["exp"]
        needed = xp_to_next_level(lvl)
        xp_bar = _xp_bar(exp, needed)
        shiny  = " ✨" if primary_stand.get("is_shiny") else ""
        emoji  = get_emoji(name)
        name_display = f"{emoji} {name}".strip() if emoji else name

        passive     = META_PASSIVES.get(name)
        passive_str = passive["description"] if passive else "None"

        embed.add_field(
            name="🌟 Equipped Stand",
            value=f"**{name_display}**{shiny}\nLv.{lvl} {'★' * stars}\n{xp_bar} {exp}/{needed} XP",
            inline=False,
        )
        embed.add_field(name="💫 Active Passive", value=passive_str, inline=True)

        # Synergy string
        if secondary_stand:
            syn_list = get_active_synergies(name, secondary_stand["stand_name"])
            if syn_list:
                synergy_str = "\n".join(f"• {s}" for s in syn_list)
                embed.add_field(name="🧬 Active Synergy", value=synergy_str, inline=True)

        # Thumbnail = current star image of primary stand
        image_url = get_image(name, stars)
        if image_url:
            embed.set_thumbnail(url=image_url)

    if secondary_stand:
        name2   = secondary_stand["stand_name"]
        lvl2    = secondary_stand["level"]
        stars2  = secondary_stand["stars"]
        shiny2  = " ✨" if secondary_stand.get("is_shiny") else ""
        emoji2  = get_emoji(name2)
        name2_display = f"{emoji2} {name2}".strip() if emoji2 else name2

        embed.add_field(
            name="🌙 Secondary Stand",
            value=f"**{name2_display}**{shiny2}\nLv.{lvl2} {'★' * stars2}",
            inline=False,
        )

    if user.get("bio"):
        embed.add_field(name="📝 Bio", value=user["bio"], inline=False)

    embed.set_footer(text=f"Daily Streak: {user.get('daily_streak', 0)} days")
    return embed


def quest_complete_embed(title: str, rewards: dict) -> discord.Embed:
    """Small embed shown when a quest is completed."""
    from src.utils.constants import ITEMS
    embed = discord.Embed(
        title="✅ Quest Complete!",
        description=f"**{title}**",
        color=0x00FF88,
    )
    parts = []
    if rewards.get("coins"):
        parts.append(f"🪙 {rewards['coins']} Coins")
    if rewards.get("diamonds"):
        parts.append(f"💎 {rewards['diamonds']} Diamonds")
    for item_id, qty in rewards.get("items", {}).items():
        name = ITEMS.get(item_id, {}).get("name", item_id)
        parts.append(f"📦 {qty}× {name}")
    if parts:
        embed.add_field(name="Rewards", value="\n".join(parts), inline=False)
    return embed


def _xp_bar(current: int, total: int, length: int = 8) -> str:
    filled = round((current / total) * length) if total > 0 else 0
    return "`" + "█" * filled + "░" * (length - filled) + "`"