"""
db/client.py
All async database operations against Supabase.
Import `db` from here everywhere else — never call supabase directly outside this file.
"""

import os
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

log = logging.getLogger("jojo-rpg.db")

# ── Supabase client (lazy singleton) ──────────────────────────────────────────
_client: Optional[Client] = None

def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


def db() -> Client:
    return get_client()


# ════════════════════════════════════════════════════════════
# USERS
# ════════════════════════════════════════════════════════════

async def get_user(user_id: str) -> Optional[dict]:
    try:
        res = db().table("users").select("*").eq("id", user_id).single().execute()
        return res.data
    except Exception:
        return None

async def get_or_create_user(user_id: str, username: str) -> dict:
    user = await get_user(user_id)
    if user:
        return user
    res = db().table("users").insert({
        "id": user_id,
        "username": username,
    }).execute()
    return res.data[0]

async def update_user(user_id: str, **kwargs) -> dict:
    res = db().table("users").update(kwargs).eq("id", user_id).execute()
    return res.data[0]

async def add_coins(user_id: str, amount: int):
    user = await get_user(user_id)
    new_total = max(0, user["coins"] + amount)
    await update_user(user_id, coins=new_total)
    return new_total

async def add_diamonds(user_id: str, amount: int):
    user = await get_user(user_id)
    new_total = max(0, user["diamonds"] + amount)
    await update_user(user_id, diamonds=new_total)
    return new_total

async def increment_pity(user_id: str, tier: str = "legendary"):
    """Increments pity_counter or mythical_pity_counter."""
    col = "pity_counter" if tier == "legendary" else "mythical_pity_counter"
    user = await get_user(user_id)
    await update_user(user_id, **{col: user[col] + 1})

async def reset_pity(user_id: str, tier: str = "legendary"):
    col = "pity_counter" if tier == "legendary" else "mythical_pity_counter"
    await update_user(user_id, **{col: 0})


# ════════════════════════════════════════════════════════════
# STANDS
# ════════════════════════════════════════════════════════════

async def get_user_stands(user_id: str) -> list[dict]:
    res = db().table("user_stands").select("*").eq("user_id", user_id).execute()
    return res.data or []

async def get_stand_by_id(stand_id: int) -> Optional[dict]:
    try:
        res = db().table("user_stands").select("*").eq("id", stand_id).single().execute()
        return res.data
    except Exception:
        return None

async def get_primary_stand(user_id: str) -> Optional[dict]:
    try:
        res = (
            db().table("user_stands")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_primary", True)
            .single()
            .execute()
        )
        return res.data
    except Exception:
        return None

async def get_secondary_stand(user_id: str) -> Optional[dict]:
    try:
        res = (
            db().table("user_stands")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_secondary", True)
            .single()
            .execute()
        )
        return res.data
    except Exception:
        return None

async def add_stand(user_id: str, stand_name: str, stars: int = 1, is_shiny: bool = False) -> dict:
    res = db().table("user_stands").insert({
        "user_id":    user_id,
        "stand_name": stand_name,
        "stars":      stars,
        "is_shiny":   is_shiny,
    }).execute()
    return res.data[0]

async def set_primary_stand(user_id: str, stand_id: int):
    """Clears existing primary then sets new one. Unsets secondary if target is currently secondary."""
    db().table("user_stands").update({"is_primary": False}).eq("user_id", user_id).execute()
    db().table("user_stands").update({"is_primary": True, "is_secondary": False}).eq("id", stand_id).execute()

async def set_secondary_stand(user_id: str, stand_id: int):
    """Clears existing secondary then sets new one. Unsets primary if target is currently primary."""
    db().table("user_stands").update({"is_secondary": False}).eq("user_id", user_id).execute()
    db().table("user_stands").update({"is_secondary": True, "is_primary": False}).eq("id", stand_id).execute()

async def update_stand(stand_id: int, **kwargs):
    res = db().table("user_stands").update(kwargs).eq("id", stand_id).execute()
    return res.data[0]

async def delete_stand(stand_id: int):
    db().table("user_stands").delete().eq("id", stand_id).execute()

async def add_stand_xp(stand_id: int, xp_amount: int) -> dict:
    """Adds XP to a stand. Handles level-ups and checks pending evolutions."""
    from src.utils.constants import xp_to_next_level
    stand = await get_stand_by_id(stand_id)
    new_xp = stand["exp"] + xp_amount
    new_level = stand["level"]

    while new_xp >= xp_to_next_level(new_level) and new_level < 50:
        new_xp -= xp_to_next_level(new_level)
        new_level += 1

    await update_stand(stand_id, exp=new_xp, level=new_level)

    # Check pending evolutions after every level change
    if new_level != stand["level"]:
        await check_pending_evolutions(stand["user_id"], stand_id, new_level)

    return await get_stand_by_id(stand_id)

async def get_stands_by_name(user_id: str, stand_name: str) -> list[dict]:
    """Exact match first, then case-insensitive fuzzy match."""
    # Try exact
    res = (
        db().table("user_stands")
        .select("*")
        .eq("user_id", user_id)
        .eq("stand_name", stand_name)
        .execute()
    )
    if res.data:
        return res.data

    # Fuzzy: get all stands, match case-insensitively with spaces/capitalisation ignored
    all_stands = await get_user_stands(user_id)
    normalised = stand_name.lower().replace(" ", "").replace("'", "").replace("-", "")
    matches = [
        s for s in all_stands
        if s["stand_name"].lower().replace(" ", "").replace("'", "").replace("-", "") == normalised
    ]
    return matches


# ════════════════════════════════════════════════════════════
# ITEMS
# ════════════════════════════════════════════════════════════

async def get_items(user_id: str) -> list[dict]:
    res = db().table("items").select("*").eq("user_id", user_id).execute()
    return res.data or []

async def get_item(user_id: str, item_id: str) -> Optional[dict]:
    try:
        res = (
            db().table("items")
            .select("*")
            .eq("user_id", user_id)
            .eq("item_id", item_id)
            .single()
            .execute()
        )
        return res.data
    except Exception:
        return None

async def add_item(user_id: str, item_id: str, quantity: int = 1):
    existing = await get_item(user_id, item_id)
    if existing:
        db().table("items").update(
            {"quantity": existing["quantity"] + quantity}
        ).eq("user_id", user_id).eq("item_id", item_id).execute()
    else:
        db().table("items").insert({
            "user_id":  user_id,
            "item_id":  item_id,
            "quantity": quantity,
        }).execute()

async def consume_item(user_id: str, item_id: str, quantity: int = 1) -> bool:
    """Returns False if insufficient quantity."""
    existing = await get_item(user_id, item_id)
    if not existing or existing["quantity"] < quantity:
        return False
    new_qty = existing["quantity"] - quantity
    if new_qty == 0:
        db().table("items").delete().eq("user_id", user_id).eq("item_id", item_id).execute()
    else:
        db().table("items").update({"quantity": new_qty}).eq("user_id", user_id).eq("item_id", item_id).execute()
    return True


# ════════════════════════════════════════════════════════════
# COOLDOWNS
# ════════════════════════════════════════════════════════════

async def get_cooldown(user_id: str, command: str) -> Optional[datetime]:
    """Returns expiry datetime if on cooldown, else None."""
    try:
        res = (
            db().table("cooldowns")
            .select("expires_at")
            .eq("user_id", user_id)
            .eq("command", command)
            .single()
            .execute()
        )
    except Exception:
        return None
    if not res.data:
        return None
    expires = datetime.fromisoformat(res.data["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires > datetime.now(timezone.utc):
        return expires
    await clear_cooldown(user_id, command)
    return None

async def set_cooldown(user_id: str, command: str, seconds: int):
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
    db().table("cooldowns").upsert({
        "user_id":    user_id,
        "command":    command,
        "expires_at": expires_at,
    }, on_conflict="user_id,command").execute()

async def clear_cooldown(user_id: str, command: str):
    db().table("cooldowns").delete().eq("user_id", user_id).eq("command", command).execute()


# ════════════════════════════════════════════════════════════
# AREA UNLOCKS
# ════════════════════════════════════════════════════════════

async def get_unlocked_areas(user_id: str) -> list[str]:
    res = db().table("area_unlocks").select("area_name").eq("user_id", user_id).execute()
    return [row["area_name"] for row in (res.data or [])]

async def unlock_area(user_id: str, area_name: str):
    db().table("area_unlocks").upsert({
        "user_id":   user_id,
        "area_name": area_name,
    }, on_conflict="user_id,area_name").execute()


# ════════════════════════════════════════════════════════════
# PLAYER UNLOCKED STANDS (Corpse Parts etc.)
# ════════════════════════════════════════════════════════════

async def get_unlocked_stands(user_id: str) -> list[str]:
    res = db().table("player_unlocked_stands").select("stand_name").eq("user_id", user_id).execute()
    return [row["stand_name"] for row in (res.data or [])]

async def unlock_stand(user_id: str, stand_name: str, unlock_type: str = "corpse_part"):
    db().table("player_unlocked_stands").upsert({
        "user_id":     user_id,
        "stand_name":  stand_name,
        "unlock_type": unlock_type,
    }, on_conflict="user_id,stand_name").execute()


# ════════════════════════════════════════════════════════════
# PENDING EVOLUTIONS
# ════════════════════════════════════════════════════════════

async def create_pending_evolution(user_id: str, stand_id: int, item_id: str, required_level: int):
    db().table("pending_evolutions").insert({
        "user_id":       user_id,
        "stand_id":      stand_id,
        "item_id":       item_id,
        "required_level": required_level,
    }).execute()

async def check_pending_evolutions(user_id: str, stand_id: int, current_level: int) -> list[dict]:
    """Fires any pending evolutions whose required_level has been reached. Returns fired evolutions."""
    res = (
        db().table("pending_evolutions")
        .select("*")
        .eq("stand_id", stand_id)
        .lte("required_level", current_level)
        .execute()
    )
    fired = []
    for evo in (res.data or []):
        await _apply_evolution(stand_id, evo["item_id"])
        db().table("pending_evolutions").delete().eq("id", evo["id"]).execute()
        fired.append(evo)
    return fired

async def _apply_evolution(stand_id: int, item_id: str):
    """Applies the evolution to the stand row."""
    from src.utils.constants import ACT_EVOLUTIONS, REQUIEM_EVOLUTIONS
    stand = await get_stand_by_id(stand_id)
    name = stand["stand_name"]

    if item_id == "actStone" and name in ACT_EVOLUTIONS:
        new_name = ACT_EVOLUTIONS[name]["evolves_to"]
        await update_stand(stand_id, stand_name=new_name, level=1, exp=0)
    elif item_id == "requiemArrow" and name in REQUIEM_EVOLUTIONS:
        new_name = REQUIEM_EVOLUTIONS[name]["evolves_to"]
        await update_stand(stand_id, stand_name=new_name, level=1, exp=0)


# ════════════════════════════════════════════════════════════
# BATTLE LOG
# ════════════════════════════════════════════════════════════

async def log_battle(attacker_id: str, defender_id: Optional[str], winner_id: str,
                     stand_used: str, xp_gained: int, coins_gained: int, is_pvp: bool = False):
    db().table("battle_log").insert({
        "attacker_id":  attacker_id,
        "defender_id":  defender_id,
        "winner_id":    winner_id,
        "stand_used":   stand_used,
        "xp_gained":    xp_gained,
        "coins_gained": coins_gained,
        "is_pvp":       is_pvp,
    }).execute()


# ════════════════════════════════════════════════════════════
# ACTIVE BATTLES
# ════════════════════════════════════════════════════════════

async def create_active_battle(attacker_id: str, defender_id: Optional[str],
                                attacker_hp: int, defender_hp: int,
                                turn: str, state: dict, is_pvp: bool = False) -> dict:
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    res = db().table("active_battles").insert({
        "attacker_id": attacker_id,
        "defender_id": defender_id,
        "attacker_hp": attacker_hp,
        "defender_hp": defender_hp,
        "turn":        turn,
        "state":       state,
        "is_pvp":      is_pvp,
        "expires_at":  expires_at,
    }).execute()
    return res.data[0]

async def update_active_battle(battle_id: int, attacker_hp: int, defender_hp: int, turn: str, state: dict):
    db().table("active_battles").update({
        "attacker_hp": attacker_hp,
        "defender_hp": defender_hp,
        "turn":        turn,
        "state":       state,
    }).eq("id", battle_id).execute()

async def delete_active_battle(battle_id: int):
    db().table("active_battles").delete().eq("id", battle_id).execute()

async def get_active_battle_for_user(user_id: str) -> Optional[dict]:
    try:
        res = (
            db().table("active_battles")
            .select("*")
            .or_(f"attacker_id.eq.{user_id},defender_id.eq.{user_id}")
            .single()
            .execute()
        )
        return res.data
    except Exception:
        return None

async def resolve_expired_battles():
    """On bot startup: award wins by HP for timed-out battles."""
    now = datetime.now(timezone.utc).isoformat()
    res = db().table("active_battles").select("*").lt("expires_at", now).execute()
    for battle in (res.data or []):
        winner_id = (
            battle["attacker_id"] if battle["attacker_hp"] >= battle["defender_hp"]
            else battle["defender_id"]
        )
        if winner_id:
            await update_user(winner_id, win_count=(await get_user(winner_id))["win_count"] + 1)
        await delete_active_battle(battle["id"])
        log.info(f"Resolved expired battle {battle['id']}, winner: {winner_id}")


# ════════════════════════════════════════════════════════════
# BATTLE QUEUE
# ════════════════════════════════════════════════════════════

async def queue_battle_challenge(challenger_id: str, target_id: str) -> dict:
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    res = db().table("battle_queue").insert({
        "challenger_id": challenger_id,
        "target_id":     target_id,
        "expires_at":    expires_at,
        "status":        "pending",
    }).execute()
    return res.data[0]

async def get_pending_challenges(target_id: str) -> list[dict]:
    res = (
        db().table("battle_queue")
        .select("*")
        .eq("target_id", target_id)
        .eq("status", "pending")
        .execute()
    )
    return res.data or []

async def update_challenge_status(challenge_id: int, status: str):
    db().table("battle_queue").update({"status": status}).eq("id", challenge_id).execute()

async def expire_battle_queue():
    """On bot startup: mark all expired pending challenges."""
    now = datetime.now(timezone.utc).isoformat()
    db().table("battle_queue").update({"status": "expired"}).lt("expires_at", now).eq("status", "pending").execute()


# ════════════════════════════════════════════════════════════
# QUESTS
# ════════════════════════════════════════════════════════════

async def get_user_quests(user_id: str) -> list[dict]:
    res = db().table("user_quests").select("*").eq("user_id", user_id).execute()
    return res.data or []

async def get_quest(user_id: str, quest_id: str) -> Optional[dict]:
    try:
        res = (
            db().table("user_quests")
            .select("*")
            .eq("user_id", user_id)
            .eq("quest_id", quest_id)
            .single()
            .execute()
        )
        return res.data
    except Exception:
        return None

async def upsert_quest(user_id: str, quest_id: str, progress: int = 0,
                       completed: bool = False, refreshes_at: Optional[str] = None):
    db().table("user_quests").upsert({
        "user_id":      user_id,
        "quest_id":     quest_id,
        "progress":     progress,
        "completed":    completed,
        "completed_at": datetime.now(timezone.utc).isoformat() if completed else None,
        "refreshes_at": refreshes_at,
    }, on_conflict="user_id,quest_id").execute()


# ════════════════════════════════════════════════════════════
# LEADERBOARD
# ════════════════════════════════════════════════════════════

async def get_win_leaderboard(limit: int = 10) -> list[dict]:
    res = (
        db().table("users")
        .select("id, username, win_count, loss_count")
        .order("win_count", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []

async def get_power_leaderboard(limit: int = 10) -> list[dict]:
    """Returns top users by their primary stand's computed power score."""
    # We pull primary stands and join manually since Supabase JS SDK doesn't do complex joins
    res = (
        db().table("user_stands")
        .select("user_id, stand_name, level, stars, is_shiny, users(username)")
        .eq("is_primary", True)
        .limit(limit * 2)  # overfetch; sort in Python
        .execute()
    )
    from src.battle.stand import compute_power_score
    rows = res.data or []
    scored = sorted(rows, key=lambda r: compute_power_score(r), reverse=True)
    return scored[:limit]