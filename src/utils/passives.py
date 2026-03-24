"""
utils/passives.py
Resolves the active meta-passive from a user's primary stand.
"""

from src.utils.constants import META_PASSIVES
from typing import Optional


async def get_active_passive(user_id: str) -> Optional[dict]:
    """Returns the passive dict for the user's primary stand, or None."""
    from src.db import client as db
    primary = await db.get_primary_stand(user_id)
    if not primary:
        return None
    return META_PASSIVES.get(primary["stand_name"])


async def get_sroll_cooldown(user_id: str) -> int:
    """Returns the effective Sroll cooldown in seconds for this user."""
    BASE = 600   # 10 minutes
    passive = await get_active_passive(user_id)
    if passive and passive["type"] == "cooldown_reduce":
        return max(0, BASE - int(passive["value"]))
    return BASE
