"""
battle/ai.py
PvE AI — picks damaging moves only (status moves are skipped).
Difficulty scales with boss flag.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.battle.stand import Stand, Move


def ai_choose_move(stand: "Stand", is_boss: bool = False) -> "Move":
    """
    Returns the move the AI will use this turn.
    - Normal AI: picks highest-power damaging move 60% of time, random otherwise.
    - Boss AI: always picks the highest-power move available.
    """
    moves = stand.damaging_moves
    if not moves:
        # Fallback: all PP exhausted — use first move ignoring PP (shouldn't happen in practice)
        moves = [m for m in stand.moves if m.category != "Status"]
        if not moves:
            moves = stand.moves

    if is_boss:
        return max(moves, key=lambda m: m.power)

    # Normal AI: 60% best move, 40% random
    if random.random() < 0.60:
        return max(moves, key=lambda m: m.power)
    return random.choice(moves)


def ai_use_time_stop(stand: "Stand") -> bool:
    """The World AI: always use Time Stop on the first available turn."""
    from src.battle.gimmicks import try_time_stop
    return stand.gimmick == "time_stop" and not stand.gimmick_used
