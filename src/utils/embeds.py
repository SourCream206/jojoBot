"""
utils/embeds.py
Shared embed builders used across cogs.
"""

import discord
from src.utils.constants import RARITY_COLORS, RARITY_EMOJIS, META_PASSIVES
from src.utils.constants import xp_to_next_level
from src.utils.stands_data import get_image, get_emoji

# Shiny-specific color (bright gold)
SHINY_COLOR = 0xFFD700


class StandImageView(discord.ui.View):
    """Navigation view for cycling through stand images at different star levels."""

    def __init__(self, stand_name: str, max_stars: int = 5, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.stand_name = stand_name
        self.max_stars = min(max_stars, 5)  # Cap at 5 stars
        self.current_star = self.max_stars  # Start at current/max star level
        self.message = None  # Set by caller

        # Update button labels
        self._update_button_labels()

    def _update_button_labels(self):
        """Update button labels and disabled states based on current star."""
        prev_btn = None
        next_btn = None

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == "prev_star":
                    prev_btn = item
                elif item.custom_id == "next_star":
                    next_btn = item

        if prev_btn:
            prev_btn.label = f"⮜ ★{self.current_star - 1}"
            prev_btn.disabled = self.current_star <= 1

        if next_btn:
            next_btn.label = f"★{self.current_star + 1} ⮞"
            next_btn.disabled = self.current_star >= self.max_stars

    async def _update_message(self, interaction: discord.Interaction):
        """Update the message with the new star image."""
        image_url = get_image(self.stand_name, self.current_star)

        # Create a minimal embed just for the image
        embed = interaction.message.embeds[0]  # Get existing embed
        if image_url:
            embed.set_image(url=image_url)
        else:
            embed.set_image(url="")  # Clear image if none available

        # Update title to show current star level
        old_title = embed.title or ""
        # Remove star indicator if already present
        if " [★" in old_title:
            old_title = old_title[:old_title.index(" [★")]
        new_title = f"{old_title} [★{self.current_star}]"
        embed.title = new_title

        await interaction.response.defer()
        # Use interaction.message as fallback if self.message wasn't set
        message = self.message or interaction.message
        await message.edit(embed=embed, view=self)

    @discord.ui.button(label="⮜ ★1", style=discord.ButtonStyle.primary, custom_id="prev_star")
    async def prev_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_star > 1:
            self.current_star -= 1
            self._update_button_labels()
            await self._update_message(interaction)

    @discord.ui.button(label="★5 ⮞", style=discord.ButtonStyle.primary, custom_id="next_star")
    async def next_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_star < self.max_stars:
            self.current_star += 1
            self._update_button_labels()
            await self._update_message(interaction)


def get_active_synergies(primary: str, secondary: str) -> list[str]:
    if not primary or not secondary:
        return []
    
    synergies = []
    stands = {primary, secondary}
    
    if {"Star Platinum", "The World"}.issubset(stands):
        synergies.append("Time Stop Mastery (Bonus Damage in Time Stop)")
    elif "Star Platinum" in stands and ("Hierophant Green" in stands or "Silver Chariot" in stands):
        synergies.append("JoBro Buff (+5 HP, +5% Max HP)")
    elif {"Star Platinum", "Hermit Purple"}.issubset(stands):
        synergies.append("Joestar Bloodline (+10% Max HP)")
    elif primary in ("The Fool", "Horus", "Strength") and secondary in ("The Fool", "Horus", "Strength"):
        synergies.append("Animal Jam (+5 Base Power, +5% Damage)")
    elif {"Dark Blue Moon", "Strength"}.issubset(stands):
        synergies.append("Cruise Ship (+10% Defense)")
    elif {"Osiris", "Atum"}.issubset(stands):
        synergies.append("Darby Brothers (Highest Luck in Gacha Rolls)")
    elif {"The World", "Cream"}.issubset(stands):
        synergies.append("Vampiric Power (+8% Lifesteal)")
    elif {"Magician's Red", "The Sun"}.issubset(stands):
        synergies.append("Scorching Heat (Burn deals 1.5x Damage)")
    elif {"Tohth", "Khnum"}.issubset(stands):
        synergies.append("Fate Manipulation (10% Reflect Chance)")
    elif {"Anubis", "Silver Chariot"}.issubset(stands):
        synergies.append("Blade Master (+5% Speed, +6% Damage)")
    elif {"Hanged Man", "Emperor"}.issubset(stands):
        synergies.append("Perfect Execution (+20% Critical Damage)")
    elif {"Justice", "Lovers"}.issubset(stands):
        synergies.append("Undead Link (Take 10% less damage when under 50% HP)")
        
    return synergies


def stand_roll_embed(stand_name: str, rarity: str, stars: int, is_shiny: bool) -> discord.Embed:
    """Synchronous embed builder - use async version for shiny glow effect."""
    color        = SHINY_COLOR if is_shiny else RARITY_COLORS.get(rarity, 0xAAAAAA)
    rarity_emoji = RARITY_EMOJIS.get(rarity, "")
    stand_emoji  = get_emoji(stand_name)
    shiny_str    = " **SHINY!**" if is_shiny else ""
    star_str     = "" * stars

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


async def stand_roll_embed_async(stand_name: str, rarity: str, stars: int, is_shiny: bool) -> tuple[discord.Embed, discord.File | None]:
    """
    Async embed builder that adds glowing border for shiny stands.
    Returns (embed, file) where file is the shiny-processed image or None.
    """
    color        = SHINY_COLOR if is_shiny else RARITY_COLORS.get(rarity, 0xAAAAAA)
    rarity_emoji = RARITY_EMOJIS.get(rarity, "")
    stand_emoji  = get_emoji(stand_name)
    shiny_str    = " **SHINY!**" if is_shiny else ""
    star_str     = "" * stars

    embed = discord.Embed(
        title=f"{rarity_emoji} You obtained **{stand_name}**!{shiny_str}",
        color=color,
    )
    embed.add_field(name="Rarity", value=f"{rarity_emoji} {rarity}", inline=True)
    embed.add_field(name="Stars",  value=star_str,                   inline=True)
    if stand_emoji:
        embed.add_field(name="Stand", value=stand_emoji, inline=True)

    image_url = get_image(stand_name, stars)
    file = None

    if image_url:
        if is_shiny:
            # Apply glowing border effect
            from src.utils.image_effects import get_shiny_image
            import io
            shiny_bytes = await get_shiny_image(image_url)
            if shiny_bytes:
                file = discord.File(io.BytesIO(shiny_bytes), filename="shiny_stand.png")
                embed.set_image(url="attachment://shiny_stand.png")
            else:
                # Fallback to original if processing fails
                embed.set_image(url=image_url)
        else:
            embed.set_image(url=image_url)

    return embed, file


def stand_info_embed(stand_row: dict, catalog_entry: dict | None = None, stand_obj=None) -> discord.Embed:
    """Synchronous embed builder - use async version for shiny glow effect."""
    name   = stand_row["stand_name"]
    stars  = stand_row["stars"]
    level  = stand_row["level"]
    shiny  = stand_row.get("is_shiny", False)

    rarity    = catalog_entry["rarity"] if catalog_entry else "Common"
    color     = SHINY_COLOR if shiny else RARITY_COLORS.get(rarity, 0xAAAAAA)
    emoji     = get_emoji(name)
    image_url = get_image(name, stars)

    title = f"{emoji} {name}".strip() if emoji else name
    if shiny:
        title += " "

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Level",   value=str(level),                     inline=True)
    embed.add_field(name="Stars",   value="" * stars,                    inline=True)
    embed.add_field(name="Shiny",   value=" Yes" if shiny else "No",    inline=True)

    xp_needed = xp_to_next_level(level)
    embed.add_field(name="XP",     value=f"{stand_row['exp']}/{xp_needed}", inline=True)
    embed.add_field(name="Merges", value=str(stand_row["merge_count"]),      inline=True)
    embed.add_field(name="Primary",value=" Yes" if stand_row["is_primary"] else "No", inline=True)

    if stand_obj:
        stats_str = (
            f"HP: {stand_obj.max_hp} | ATK: {stand_obj.atk} | DEF: {stand_obj.defense}\n"
            f"SPA: {stand_obj.spa} | SPD: {stand_obj.spd} | RNG: {stand_obj.rng}"
        )
        embed.add_field(name=" Stats", value=stats_str, inline=False)

        unlock_levels = [1, 1, 15, 30]
        moves_lines = []
        for i, m in enumerate(stand_obj.moves):
            locked = f" *(unlocks Lv.{unlock_levels[i]})*" if level < unlock_levels[i] else ""
            moves_lines.append(
                f" **{m.name}** ({m.category}, Pwr {m.power}, Acc {int(m.accuracy*100)}%, PP {m.pp}){locked}"
            )
        embed.add_field(name=" Moves", value="\n".join(moves_lines), inline=False)

    if image_url:
        embed.set_image(url=image_url)

    return embed


async def stand_info_embed_async(stand_row: dict, catalog_entry: dict | None = None, stand_obj=None) -> tuple[discord.Embed, discord.File | None]:
    """
    Async embed builder that adds glowing border for shiny stands.
    Returns (embed, file) where file is the shiny-processed image or None.
    """
    name   = stand_row["stand_name"]
    stars  = stand_row["stars"]
    level  = stand_row["level"]
    shiny  = stand_row.get("is_shiny", False)

    rarity    = catalog_entry["rarity"] if catalog_entry else "Common"
    color     = SHINY_COLOR if shiny else RARITY_COLORS.get(rarity, 0xAAAAAA)
    emoji     = get_emoji(name)
    image_url = get_image(name, stars)

    title = f"{emoji} {name}".strip() if emoji else name
    if shiny:
        title += " "

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Level",   value=str(level),                     inline=True)
    embed.add_field(name="Stars",   value="" * stars,                    inline=True)
    embed.add_field(name="Shiny",   value=" Yes" if shiny else "No",    inline=True)

    xp_needed = xp_to_next_level(level)
    embed.add_field(name="XP",     value=f"{stand_row['exp']}/{xp_needed}", inline=True)
    embed.add_field(name="Merges", value=str(stand_row["merge_count"]),      inline=True)
    embed.add_field(name="Primary",value=" Yes" if stand_row["is_primary"] else "No", inline=True)

    if stand_obj:
        stats_str = (
            f"HP: {stand_obj.max_hp} | ATK: {stand_obj.atk} | DEF: {stand_obj.defense}\n"
            f"SPA: {stand_obj.spa} | SPD: {stand_obj.spd} | RNG: {stand_obj.rng}"
        )
        embed.add_field(name=" Stats", value=stats_str, inline=False)

        unlock_levels = [1, 1, 15, 30]
        moves_lines = []
        for i, m in enumerate(stand_obj.moves):
            locked = f" *(unlocks Lv.{unlock_levels[i]})*" if level < unlock_levels[i] else ""
            moves_lines.append(
                f" **{m.name}** ({m.category}, Pwr {m.power}, Acc {int(m.accuracy*100)}%, PP {m.pp}){locked}"
            )
        embed.add_field(name=" Moves", value="\n".join(moves_lines), inline=False)

    file = None
    if image_url:
        if shiny:
            from src.utils.image_effects import get_shiny_image
            import io
            shiny_bytes = await get_shiny_image(image_url)
            if shiny_bytes:
                file = discord.File(io.BytesIO(shiny_bytes), filename="shiny_stand.png")
                embed.set_image(url="attachment://shiny_stand.png")
            else:
                embed.set_image(url=image_url)
        else:
            embed.set_image(url=image_url)

    return embed, file


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