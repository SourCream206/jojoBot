"""
bot/utils/helpers.py — Shared utility functions
"""

import json
import os
import random
import discord
from bot.config import RARITY_COLORS, RARITY_WEIGHTS

_stands_cache = None

def load_stands() -> dict:
    global _stands_cache
    if _stands_cache is not None:
        return _stands_cache
    path = os.path.join(os.path.dirname(__file__), "..", "data", "stands.json")
    with open(path, "r", encoding="utf-8") as f:
        _stands_cache = json.load(f)
    return _stands_cache


def normalize(name: str) -> str:
    if not name:
        return ""
    return name.lower().strip().replace(" ", "").replace("-", "").replace("'", "").replace(".", "")


def find_stand(name: str):
    """Returns (canonical_name, stand_data) or (None, None)."""
    norm = normalize(name)
    for part in load_stands().values():
        for sname, data in part.items():
            if normalize(sname) == norm:
                return sname, data
    return None, None


def get_stand_rarity(name: str) -> str | None:
    _, data = find_stand(name)
    return data["rarity"] if data else None


def build_weighted_list(weight_table: dict) -> list:
    """Returns list of (stand_name, stand_data) weighted by rarity."""
    stands = load_stands()
    pool = []
    for part in stands.values():
        for sname, sdata in part.items():
            if sdata.get("rollable", True):
                w = weight_table.get(sdata["rarity"], 0)
                pool.extend([(sname, sdata)] * w)
    return pool


def rarity_color(rarity: str) -> int:
    return RARITY_COLORS.get(rarity, 0x95A5A6)


def get_pvp_rank(elo: int) -> tuple[str, str]:
    from bot.config import PVP_RANKS
    rank = PVP_RANKS[0]
    for r in PVP_RANKS:
        if elo >= r[2]:
            rank = r
    return rank[0], rank[1]


def format_cooldown(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)


def stand_embed(stand_name: str, stand_data: dict, stars: int = 1, title: str = None) -> discord.Embed:
    rarity = stand_data.get("rarity", "Common")
    color = rarity_color(rarity)
    embed = discord.Embed(
        title=title or f"{stand_name} ★{stars}",
        description=f"**Rarity:** {rarity}",
        color=color
    )
    star_images = stand_data.get("stars", {})
    img = star_images.get(str(stars)) or stand_data.get("image", "")
    if img:
        embed.set_image(url=img)
    emoji = stand_data.get("emoji", "")
    if emoji:
        embed.set_footer(text=emoji)
    return embed
