"""
cogs/inventory.py
Sinv, Sinfo, Smerge, Suse, Sequip
"""

import discord
from discord.ext import commands

from src.db import client as db
from src.utils.constants import (
    ITEMS, ACT_EVOLUTIONS, REQUIEM_EVOLUTIONS, RARITY_COLORS,
    xp_to_next_level, AREA_ORDER, STAND_POOLS,
)
from src.utils.stands_data import get_emoji

# How many stand entries to show per sub-page within an area
PAGE_SIZE = 10


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Sinv ──────────────────────────────────────────────────────────────────

    @commands.command(name="inv", aliases=["inventory", "stands", "collection", "i", "inventorry", "inventry", "mystand", "mystands", "box"])
    async def sinv(self, ctx: commands.Context):
        """View your stand inventory, paginated by area."""
        await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        stands = await db.get_user_stands(str(ctx.author.id))

        if not stands:
            await ctx.reply("You have no stands yet! Use `Sroll` to get one.", mention_author=False)
            return

        # Build name → area lookup from pools
        name_to_area: dict[str, str] = {}
        for area, pool in STAND_POOLS.items():
            for s in pool:
                name_to_area[s["name"]] = area

        # Group: area → stand_name → [copies]
        area_groups: dict[str, dict[str, list]] = {area: {} for area in AREA_ORDER}
        area_groups["Other"] = {}

        for s in stands:
            area = name_to_area.get(s["stand_name"], "Other")
            if area not in area_groups:
                area_groups[area] = {}
            area_groups[area].setdefault(s["stand_name"], []).append(s)

        # Drop empty areas
        populated = {k: v for k, v in area_groups.items() if v}

        view = InventoryView(ctx.author, populated, len(stands))
        await ctx.reply(embed=view.build_embed(), view=view, mention_author=False)

    # ── Sinfo ─────────────────────────────────────────────────────────────────

    @commands.command(name="info", aliases=["lookup", "stand", "details", "inf", "check", "view", "show", "standinfo", "infor", "infp"])
    async def sinfo(self, ctx: commands.Context, *, stand_name: str):
        """View detailed info on one of your stands. Usage: Sinfo <stand name>"""
        await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        copies = await db.get_stands_by_name(str(ctx.author.id), stand_name)

        if not copies:
            await ctx.reply(f"You don't own **{stand_name}**.", mention_author=False)
            return

        # If only one copy, show info directly
        if len(copies) == 1:
            await self._show_stand_info(ctx, copies[0], copies)
            return

        # Multiple copies - show dropdown
        view = InfoSelectView(ctx.author, copies, self)
        embed = discord.Embed(
            title=f"📋 Stand Info: {stand_name}",
            description=f"You have **{len(copies)}** copies of this stand.\nSelect which one to view:",
            color=0x3498DB,
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    async def _show_stand_info(self, ctx: commands.Context, stand: dict, all_copies: list):
        """Helper to display stand info embed."""
        max_star_level = max(s["stars"] for s in all_copies) if all_copies else 1

        from src.battle.stand_stats import STAND_CATALOG, make_stand
        from src.utils.embeds import stand_info_embed, StandImageView

        catalog   = STAND_CATALOG.get(stand["stand_name"])
        stand_obj = make_stand(stand["stand_name"], stand["level"], stand["stars"], stand["is_shiny"]) if catalog else None
        embed     = stand_info_embed(stand, catalog, stand_obj)

        # Create view for star navigation
        view = StandImageView(stand["stand_name"], max_stars=max_star_level)
        view.current_star = stand["stars"]  # Start at this copy's star level
        view._update_button_labels()
        message = await ctx.reply(embed=embed, view=view, mention_author=False)
        view.message = message

    # ── Sitems ────────────────────────────────────────────────────────────────

    @commands.command(name="items", aliases=["bag", "backpack", "item", "itm", "itms", "backpak", "bak"])
    async def sitems(self, ctx: commands.Context):
        """View your items (xpPotions, rolls, etc.)."""
        await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        items = await db.get_items(str(ctx.author.id))
        
        if not items:
            await ctx.reply("Your bag is empty!", mention_author=False)
            return
            
        embed = discord.Embed(
            title=f"🎒 {ctx.author.name}'s Bag",
            color=0x3498DB
        )
        
        lines = []
        for row in items:
            item_id = row["item_id"]
            qty = row["quantity"]
            if qty <= 0:
                continue
            item_def = ITEMS.get(item_id)
            if item_def:
                name = item_def.get("name", item_id)
                desc = item_def.get("description", "")
                emoji = item_def.get("emoji", "📦")
                lines.append(f"{emoji} **{name}** ×{qty}\n└ *{desc}*")
            else:
                lines.append(f"📦 **{item_id}** ×{qty}")
                
        if not lines:
            await ctx.reply("Your bag is empty!", mention_author=False)
            return
            
        embed.description = "\n\n".join(lines)
        await ctx.reply(embed=embed, mention_author=False)

    # ── Sequip ────────────────────────────────────────────────────────────────

    @commands.command(name="equip", aliases=["eq", "set", "primary", "setprimary", "equipstand", "eqp", "equp", "equipt", "setstand"])
    async def sequip(self, ctx: commands.Context, *, stand_name: str):
        """Set a stand as your primary (equipped) stand. Usage: Sequip <stand name>"""
        await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        copies = await db.get_stands_by_name(str(ctx.author.id), stand_name)

        if not copies:
            await ctx.reply(f"You don't own **{stand_name}**.", mention_author=False)
            return

        # If only one copy, equip it directly
        if len(copies) == 1:
            stand = copies[0]
            secondary = await db.get_secondary_stand(str(ctx.author.id))
            if secondary and secondary["id"] == stand["id"]:
                await ctx.reply(f"**{stand['stand_name']}** is already equipped as your secondary stand! Equip a different primary.", mention_author=False)
                return
            await db.set_primary_stand(str(ctx.author.id), stand["id"])
            await ctx.reply(
                f"⭐ **{stand['stand_name']}** is now your primary stand!",
                mention_author=False,
            )
            return

        # Multiple copies - show dropdown
        view = EquipSelectView(ctx.author, copies, "primary")
        embed = discord.Embed(
            title=f"⭐ Equip Primary Stand: {stand_name}",
            description=f"You have **{len(copies)}** copies of this stand.\nSelect which one to equip:",
            color=0xF1C40F,
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="equipsecondary", aliases=["eqsec", "setsecondary", "sec", "secondary", "equipsec", "equipseondary", "equipseconday", "equip2", "eq2", "setsec"])
    async def sequipsecondary(self, ctx: commands.Context, *, stand_name: str):
        """Set a stand as your secondary (equipped) stand. Usage: Seqsec <stand name>"""
        await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        copies = await db.get_stands_by_name(str(ctx.author.id), stand_name)

        if not copies:
            await ctx.reply(f"You don't own **{stand_name}**.", mention_author=False)
            return

        # If only one copy, equip it directly
        if len(copies) == 1:
            stand = copies[0]
            primary = await db.get_primary_stand(str(ctx.author.id))
            if primary and primary["id"] == stand["id"]:
                await ctx.reply(f"**{stand['stand_name']}** is already equipped as your primary stand! Equip a different secondary.", mention_author=False)
                return
            await db.set_secondary_stand(str(ctx.author.id), stand["id"])
            await ctx.reply(
                f"🌟 **{stand['stand_name']}** is now your secondary stand!",
                mention_author=False,
            )
            return

        # Multiple copies - show dropdown
        view = EquipSelectView(ctx.author, copies, "secondary")
        embed = discord.Embed(
            title=f"🌟 Equip Secondary Stand: {stand_name}",
            description=f"You have **{len(copies)}** copies of this stand.\nSelect which one to equip:",
            color=0x3498DB,
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ── Smerge ────────────────────────────────────────────────────────────────

    @commands.command(name="merge", aliases=["fuse", "combine", "upgrade", "mrg", "merge5", "fuze", "kombine", "upgrd"])
    async def smerge(self, ctx: commands.Context, *, stand_name: str):
        """Merge 5 copies of the same stand (same star level) into one copy at the next star."""
        await db.get_or_create_user(str(ctx.author.id), ctx.author.name)
        copies = await db.get_stands_by_name(str(ctx.author.id), stand_name)

        if not copies:
            await ctx.reply(f"You don't own **{stand_name}**.", mention_author=False)
            return

        by_stars: dict[int, list] = {}
        for c in copies:
            by_stars.setdefault(c["stars"], []).append(c)

        merge_group = None
        for star_level, group in sorted(by_stars.items()):
            if len(group) >= 5 and star_level < 5:
                merge_group = (star_level, group[:5])
                break

        if not merge_group:
            eligible = {k: len(v) for k, v in by_stars.items() if k < 5}
            if not eligible:
                await ctx.reply(f"**{stand_name}** is already at ★5!", mention_author=False)
            else:
                counts = ", ".join(f"★{k}: {v}/5" for k, v in sorted(eligible.items()))
                await ctx.reply(f"Need 5 copies at the same star level.\n{counts}", mention_author=False)
            return

        star_level, to_consume = merge_group
        new_stars = star_level + 1
        keeper = to_consume[0]
        for s in to_consume[1:]:
            await db.delete_stand(s["id"])

        bonus_xp = 100 * star_level
        await db.update_stand(keeper["id"], stars=new_stars, merge_count=keeper["merge_count"] + 1)
        await db.add_stand_xp(keeper["id"], bonus_xp)

        from src.utils.stands_data import get_image

        embed = discord.Embed(
            title="⭐ Merge Successful!",
            description=f"5× **{stand_name}** ★{star_level} → **{stand_name}** ★{new_stars}\n+{bonus_xp} bonus XP!",
            color=0xF1C40F,
        )

        # Add the new star image
        new_image = get_image(stand_name, new_stars)
        if new_image:
            embed.set_image(url=new_image)

        await ctx.reply(embed=embed, mention_author=False)

    # ── Suse ──────────────────────────────────────────────────────────────────

    @commands.command(name="use", aliases=["consume", "activate", "useitem", "u", "apply", "eat", "drink", "usepotion"])
    async def suse(self, ctx: commands.Context, item_id: str, *, stand_name: str = ""):
        """Use an item. Usage: Suse <item_id> [stand name]"""
        user_id = str(ctx.author.id)
        await db.get_or_create_user(user_id, ctx.author.name)

        if item_id not in ITEMS:
            await ctx.reply(f"Unknown item `{item_id}`.", mention_author=False)
            return

        item_def = ITEMS[item_id]

        if item_id == "xpPotion":
            if not stand_name:
                await ctx.reply("Usage: `Suse xpPotion <stand name>`", mention_author=False)
                return
            copies = await db.get_stands_by_name(user_id, stand_name)
            if not copies:
                await ctx.reply(f"You don't own **{stand_name}**.", mention_author=False)
                return
            stand = max(copies, key=lambda s: s["level"])
            if stand["level"] >= 50:
                await ctx.reply("That stand is already at max level!", mention_author=False)
                return
            if not await db.consume_item(user_id, "xpPotion"):
                await ctx.reply("You don't have any XP Potions!", mention_author=False)
                return
            xp_needed = xp_to_next_level(stand["level"])
            await db.add_stand_xp(stand["id"], xp_needed)
            await ctx.reply(f"🧪 **{stand['stand_name']}** levelled up to **Lv.{stand['level'] + 1}**!", mention_author=False)

        elif item_id == "actStone":
            if not stand_name:
                await ctx.reply("Usage: `Suse actStone <stand name>`", mention_author=False)
                return
            if stand_name not in ACT_EVOLUTIONS:
                await ctx.reply(f"**{stand_name}** cannot use an Act Stone.", mention_author=False)
                return
            copies = await db.get_stands_by_name(user_id, stand_name)
            if not copies:
                await ctx.reply(f"You don't own **{stand_name}**.", mention_author=False)
                return
            stand = max(copies, key=lambda s: s["level"])
            evo   = ACT_EVOLUTIONS[stand_name]
            req   = evo["required_level"]
            if not await db.consume_item(user_id, "actStone"):
                await ctx.reply("You don't have an Act Stone!", mention_author=False)
                return
            if stand["level"] >= req:
                await db._apply_evolution(stand["id"], "actStone")
                await ctx.reply(f"💠 **{stand_name}** evolved into **{evo['evolves_to']}**!", mention_author=False)
            else:
                await db.create_pending_evolution(user_id, stand["id"], "actStone", req)
                await ctx.reply(f"💠 Act Stone applied. **{stand_name}** will evolve at **Lv.{req}**!", mention_author=False)

        elif item_id == "requiemArrow":
            if not stand_name:
                await ctx.reply("Usage: `Suse requiemArrow <stand name>`", mention_author=False)
                return
            if stand_name not in REQUIEM_EVOLUTIONS:
                await ctx.reply(f"**{stand_name}** cannot be pierced by the Requiem Arrow.", mention_author=False)
                return
            copies = await db.get_stands_by_name(user_id, stand_name)
            if not copies:
                await ctx.reply(f"You don't own **{stand_name}**.", mention_author=False)
                return
            stand = max(copies, key=lambda s: s["level"])
            evo   = REQUIEM_EVOLUTIONS[stand_name]
            if not await db.consume_item(user_id, "requiemArrow"):
                await ctx.reply("You don't have a Requiem Arrow!", mention_author=False)
                return
            if stand["level"] >= 40:
                await db._apply_evolution(stand["id"], "requiemArrow")
                await ctx.reply(f"🏹 **{stand_name}** evolved into **{evo['evolves_to']}**!", mention_author=False)
            else:
                await db.create_pending_evolution(user_id, stand["id"], "requiemArrow", 40)
                await ctx.reply(f"🏹 Requiem Arrow applied. **{stand_name}** will evolve at **Lv.40**!", mention_author=False)

        elif item_def.get("is_corpse_part"):
            from src.utils.constants import CORPSE_PARTS
            part_data = CORPSE_PARTS.get(item_id)
            if not await db.consume_item(user_id, item_id):
                await ctx.reply(f"You don't have **{item_def['name']}**!", mention_author=False)
                return
            unlocks = part_data.get("unlocks_stand") if part_data else None
            if unlocks:
                await db.unlock_stand(user_id, unlocks, unlock_type="corpse_part")
                await ctx.reply(f"✝️ **{item_def['name']}** resonates with you!\n**{unlocks}** added to your roll pool!", mention_author=False)
            else:
                await ctx.reply(f"✝️ You absorbed the **{item_def['name']}**. Its power flows through you.", mention_author=False)
        else:
            await ctx.reply(f"**{item_def['name']}** can't be used here.", mention_author=False)


# ════════════════════════════════════════════════════════════
# INVENTORY VIEW — area tabs + sub-page arrows
# ════════════════════════════════════════════════════════════

AREA_EMOJIS = {
    "Cairo":        "🏜️",
    "Morioh Town":  "🏘️",
    "Italy":        "🍕",
    "Philadelphia": "🗽",
    "Morioh SBR":   "🌾",
    "Other":        "📦",
}

class InventoryView(discord.ui.View):
    def __init__(self, author: discord.User, area_groups: dict[str, dict[str, list]], total: int):
        super().__init__(timeout=120)
        self.author      = author
        self.area_groups = area_groups          # area → {stand_name: [copies]}
        self.total       = total
        self.areas       = list(area_groups.keys())
        self.area_idx    = 0                    # which area tab we're on
        self.page        = 0                    # sub-page within that area
        self._rebuild()

    # ── Build lines for current area ─────────────────────────────────────────

    def _lines_for_area(self) -> list[str]:
        area    = self.areas[self.area_idx]
        grouped = self.area_groups[area]
        lines   = []
        for name, copies in sorted(grouped.items()):
            primary_flag = "⭐ " if any(c["is_primary"] for c in copies) else ""
            shiny_count  = sum(1 for c in copies if c["is_shiny"])
            shiny_str    = f" ✨×{shiny_count}" if shiny_count else ""
            stars        = max(c["stars"] for c in copies)
            emoji        = get_emoji(name)
            e_str        = f"{emoji} " if emoji else ""
            lines.append(f"{primary_flag}{e_str}**{name}** {'★'*stars} ×{len(copies)}{shiny_str}")
        return lines

    def _max_pages(self) -> int:
        lines = self._lines_for_area()
        return max(1, -(-len(lines) // PAGE_SIZE))   # ceiling division

    # ── Embed ─────────────────────────────────────────────────────────────────

    def build_embed(self) -> discord.Embed:
        area    = self.areas[self.area_idx]
        emoji   = AREA_EMOJIS.get(area, "📦")
        lines   = self._lines_for_area()
        total_p = self._max_pages()

        start  = self.page * PAGE_SIZE
        chunk  = lines[start : start + PAGE_SIZE]

        area_count = sum(len(v) for v in self.area_groups[area].values())

        embed = discord.Embed(
            title=f"🎴 {self.author.name}'s Stands  ({self.total} total)",
            description="\n".join(chunk) or "*No stands here.*",
            color=0x9B59B6,
        )
        embed.set_footer(
            text=f"{emoji} {area}  ({area_count} stands)  •  Page {self.page+1}/{total_p}"
        )
        return embed

    # ── Button layout ─────────────────────────────────────────────────────────

    def _rebuild(self):
        self.clear_items()

        # Area tab buttons — row 0
        for i, area in enumerate(self.areas):
            emoji   = AREA_EMOJIS.get(area, "📦")
            is_cur  = i == self.area_idx
            btn = discord.ui.Button(
                label   = f"{emoji} {area}",
                style   = discord.ButtonStyle.primary if is_cur else discord.ButtonStyle.secondary,
                row     = 0,
                custom_id = f"area_{i}",
                disabled = is_cur,
            )
            btn.callback = self._make_area_callback(i)
            self.add_item(btn)

        # Sub-page nav — row 1 (only if more than one page)
        max_p = self._max_pages()
        if max_p > 1:
            prev = discord.ui.Button(
                label="◀ Prev", style=discord.ButtonStyle.secondary,
                row=1, custom_id="prev", disabled=(self.page == 0)
            )
            prev.callback = self._prev_callback
            self.add_item(prev)

            nxt = discord.ui.Button(
                label="Next ▶", style=discord.ButtonStyle.secondary,
                row=1, custom_id="next", disabled=(self.page >= max_p - 1)
            )
            nxt.callback = self._next_callback
            self.add_item(nxt)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _make_area_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("This isn't your inventory!", ephemeral=True)
                return
            self.area_idx = idx
            self.page     = 0
            self._rebuild()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        return callback

    async def _prev_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your inventory!", ephemeral=True)
            return
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _next_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your inventory!", ephemeral=True)
            return
        self.page = min(self._max_pages() - 1, self.page + 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        self.clear_items()


# ════════════════════════════════════════════════════════════
# EQUIP SELECT VIEW — dropdown for choosing which copy to equip
# ════════════════════════════════════════════════════════════

class EquipSelectView(discord.ui.View):
    def __init__(self, author: discord.User, copies: list, slot_type: str):
        super().__init__(timeout=60)
        self.author = author
        self.copies = copies
        self.slot_type = slot_type  # "primary" or "secondary"

        # Sort copies by level (descending), then stars (descending)
        sorted_copies = sorted(copies, key=lambda c: (c["level"], c["stars"]), reverse=True)

        # Build dropdown options
        options = []
        for i, copy in enumerate(sorted_copies):
            stars = "★" * copy["stars"]
            shiny = " ✨" if copy["is_shiny"] else ""
            label = f"Lv.{copy['level']} {stars}{shiny}"
            description = f"ID: {copy['id']} • XP: {copy.get('exp', 0)}"
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(copy["id"]),
                )
            )

        # Create the select dropdown
        select = discord.ui.Select(
            placeholder="Choose a stand to equip...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._select_callback
        self.add_item(select)

    async def _select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return

        stand_id = int(interaction.data["values"][0])
        selected_stand = next(c for c in self.copies if c["id"] == stand_id)

        # Check if the stand is already equipped in the other slot
        if self.slot_type == "primary":
            secondary = await db.get_secondary_stand(str(self.author.id))
            if secondary and secondary["id"] == stand_id:
                await interaction.response.send_message(
                    f"**{selected_stand['stand_name']}** is already equipped as your secondary stand!",
                    ephemeral=True
                )
                return
            await db.set_primary_stand(str(self.author.id), stand_id)
            emoji = "⭐"
        else:
            primary = await db.get_primary_stand(str(self.author.id))
            if primary and primary["id"] == stand_id:
                await interaction.response.send_message(
                    f"**{selected_stand['stand_name']}** is already equipped as your primary stand!",
                    ephemeral=True
                )
                return
            await db.set_secondary_stand(str(self.author.id), stand_id)
            emoji = "🌟"

        # Update embed to show success
        stars = "★" * selected_stand["stars"]
        shiny = " ✨" if selected_stand["is_shiny"] else ""
        embed = discord.Embed(
            title=f"{emoji} Stand Equipped!",
            description=f"**{selected_stand['stand_name']}** Lv.{selected_stand['level']} {stars}{shiny}\nis now your {self.slot_type} stand!",
            color=0x2ECC71,
        )
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        self.clear_items()


# ════════════════════════════════════════════════════════════
# INFO SELECT VIEW — dropdown for choosing which copy to view info
# ════════════════════════════════════════════════════════════

class InfoSelectView(discord.ui.View):
    def __init__(self, author: discord.User, copies: list, cog):
        super().__init__(timeout=60)
        self.author = author
        self.copies = copies
        self.cog = cog

        # Sort copies by level (descending), then stars (descending)
        sorted_copies = sorted(copies, key=lambda c: (c["level"], c["stars"]), reverse=True)

        # Build dropdown options
        options = []
        for i, copy in enumerate(sorted_copies):
            stars = "★" * copy["stars"]
            shiny = " ✨" if copy["is_shiny"] else ""
            label = f"Lv.{copy['level']} {stars}{shiny}"
            description = f"ID: {copy['id']} • XP: {copy.get('exp', 0)}"
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(copy["id"]),
                )
            )

        # Create the select dropdown
        select = discord.ui.Select(
            placeholder="Choose a stand to view...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._select_callback
        self.add_item(select)

    async def _select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return

        stand_id = int(interaction.data["values"][0])
        selected_stand = next(c for c in self.copies if c["id"] == stand_id)

        max_star_level = max(s["stars"] for s in self.copies)

        from src.battle.stand_stats import STAND_CATALOG, make_stand
        from src.utils.embeds import stand_info_embed, StandImageView

        catalog   = STAND_CATALOG.get(selected_stand["stand_name"])
        stand_obj = make_stand(selected_stand["stand_name"], selected_stand["level"], selected_stand["stars"], selected_stand["is_shiny"]) if catalog else None
        embed     = stand_info_embed(selected_stand, catalog, stand_obj)

        # Create view for star navigation
        view = StandImageView(selected_stand["stand_name"], max_stars=max_star_level)
        view.current_star = selected_stand["stars"]
        view._update_button_labels()

        await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        self.clear_items()


async def setup(bot):
    await bot.add_cog(Inventory(bot))