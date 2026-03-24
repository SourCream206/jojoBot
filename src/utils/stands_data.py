"""
utils/stands_data.py
Loads stands.json and exposes helpers for image URLs and emojis.
Place stands.json in the project root (same level as bot.py).
"""

import json
import os
from typing import Optional

# ── Load once at import time ───────────────────────────────────────────────────

_RAW: dict = {}

def _load():
    global _RAW
    path = os.path.join(os.path.dirname(__file__), "..", "..", "stands.json")
    path = os.path.normpath(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            _RAW = json.load(f)
    except FileNotFoundError:
        import logging
        logging.getLogger("jojo-rpg").warning(
            f"stands.json not found at {path} — images will be disabled"
        )

_load()


# ── Flat lookup: stand name → stand data ──────────────────────────────────────
# Also builds a reverse alias map so canonical names (e.g. "Echoes ACT1")
# resolve back to their stands.json key (e.g. "Echoes Act1").

_ALIASES = {
    "Echoes Act1":                "Echoes ACT1",
    "Echoes Act2":                "Echoes ACT2",
    "Echoes Act3":                "Echoes ACT3",
    "Killer Queen: Bites the Dust": "Bites the Dust",
    "Mr.President":               "Mr. President",
    "Super Fly":                  "Superfly",
}
# Reverse: canonical name → json name
_REVERSE_ALIASES = {v: k for k, v in _ALIASES.items()}

def _flat() -> dict[str, dict]:
    out = {}
    for part_data in _RAW.values():
        for name, data in part_data.items():
            canonical = _ALIASES.get(name, name)
            out[canonical] = data   # store under canonical name
            if name != canonical:
                out[name] = data    # also keep original for safety
    return out

_FLAT: dict[str, dict] = _flat()


# ── Public helpers ─────────────────────────────────────────────────────────────

def get_image(stand_name: str, stars: int = 1) -> Optional[str]:
    """
    Returns the image URL for a stand at the given star level.
    Falls back to star 1 image, then the base 'image' field, then None.
    """
    data = _FLAT.get(stand_name)
    if not data:
        return None

    star_images: dict = data.get("stars", {})
    star_key = str(stars)

    # Try exact star level first
    url = star_images.get(star_key, "").strip()
    if url:
        return url

    # Fall back: walk down from requested star to 1
    for s in range(stars - 1, 0, -1):
        url = star_images.get(str(s), "").strip()
        if url:
            return url

    # Final fallback: base image field
    return data.get("image", "").strip() or None


def get_emoji(stand_name: str) -> str:
    """Returns the Discord emoji string for a stand, or empty string if not found."""
    data = _FLAT.get(stand_name)
    if not data:
        return ""
    return data.get("emoji", "")


def get_rarity_from_json(stand_name: str) -> Optional[str]:
    """Returns rarity from stands.json (useful for cross-checking constants.py)."""
    data = _FLAT.get(stand_name)
    return data.get("rarity") if data else None


def is_rollable(stand_name: str) -> bool:
    data = _FLAT.get(stand_name)
    return bool(data.get("rollable", True)) if data else True