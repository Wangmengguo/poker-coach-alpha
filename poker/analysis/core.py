from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PotMath:
    to_call: int
    pot: int
    spr: float


def _safe_list(obj: Any) -> List:
    try:
        return list(obj or [])
    except Exception:
        return []


def compute_pot_math(state: Any, hero_idx: int) -> Dict[str, Any]:
    """Compute minimal pot math for MVP v0.1.

    Fields:
      - to_call: chips needed to continue
      - pot: base pot (sum of pulled pots)
      - spr: stack-to-pot ratio vs max-cover opponent (rounded to 2 decimals)
    """
    bets = _safe_list(getattr(state, "bets", []))
    stacks = _safe_list(getattr(state, "stacks", []))
    pot_amounts = _safe_list(getattr(state, "pot_amounts", []))
    statuses = _safe_list(getattr(state, "statuses", [])) or [True] * len(stacks)

    # to_call
    mx = max(bets) if bets else 0
    mine = bets[hero_idx] if 0 <= hero_idx < len(bets) else 0
    to_call = max(0, int(mx) - int(mine))

    # pot (base, excludes current street unpulled bets)
    pot = int(sum(int(x) for x in pot_amounts)) if pot_amounts else 0

    # effective stack vs max-cover opponent among live seats
    hero_stack = int(stacks[hero_idx]) if 0 <= hero_idx < len(stacks) else 0
    opp_max = 0
    for j, s in enumerate(stacks):
        if j == hero_idx:
            continue
        alive = statuses[j] if j < len(statuses) else True
        if not alive:
            continue
        try:
            sj = int(s)
        except Exception:
            sj = 0
        if sj > opp_max:
            opp_max = sj
    effective_stack = min(hero_stack, opp_max) if opp_max > 0 else 0

    # SPR with base pot; guard zero by denominator >= 1
    denom = pot if pot > 0 else 1
    spr = round(float(effective_stack) / float(denom), 2) if effective_stack > 0 else 0.0

    return {"to_call": int(to_call), "pot": int(pot), "spr": float(spr)}

