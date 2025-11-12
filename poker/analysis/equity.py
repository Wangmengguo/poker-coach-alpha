from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Tuple

from pokerkit import analysis as pk_analysis  # type: ignore
from pokerkit.hands import StandardHighHand  # type: ignore
from pokerkit.utilities import Deck  # type: ignore


@dataclass
class HandStrengthResult:
    hand_strength_pct: Optional[float]
    model: str = "pokerkit.calculate_hand_strength"
    sample_count: int = 0
    players: int = 0
    degraded: bool = False
    reason: Optional[str] = None


def _flatten_board_cards(state: Any) -> Tuple:
    cards: List = []
    try:
        for street in getattr(state, "board_cards", []) or []:
            if street:
                for c in street:
                    cards.append(c)
    except Exception:
        pass
    return tuple(cards)


def _hero_hole_cards(state: Any, hero_idx: int) -> Optional[Tuple]:
    try:
        hc = getattr(state, "hole_cards", []) or []
        if 0 <= hero_idx < len(hc):
            cards = tuple(hc[hero_idx] or [])
            if len(cards) == 2:
                return cards
    except Exception:
        pass
    return None


def _live_player_count(state: Any) -> int:
    statuses = list(getattr(state, "statuses", []) or [])
    if statuses:
        try:
            return int(sum(1 for x in statuses if bool(x)))
        except Exception:
            pass
    stacks = list(getattr(state, "stacks", []) or [])
    if stacks:
        return int(sum(1 for s in stacks if (s or 0) > 0))
    return 0


def compute_hand_strength(state: Any, hero_idx: int, sample_count: int = 100) -> HandStrengthResult:
    """Compute hand strength using PokerKit's calculate_hand_strength.

    Returns percentage in [0,100] or None on insufficient info.
    """
    players = _live_player_count(state)
    hero = _hero_hole_cards(state, hero_idx)
    board = _flatten_board_cards(state)

    if players < 2 or hero is None:
        return HandStrengthResult(
            hand_strength_pct=None,
            sample_count=sample_count,
            players=players,
            reason="insufficient_info",
        )

    try:
        # hole_range: iterable of exact combos; we pass the exact hero hand only
        hole_range: Iterable[Iterable] = (hero,)
        strength = pk_analysis.calculate_hand_strength(
            players,
            hole_range,
            board,
            2,
            5,
            Deck.STANDARD,
            (StandardHighHand,),
            sample_count=sample_count,
        )
        pct = float(strength) * 100.0
        return HandStrengthResult(
            hand_strength_pct=pct,
            sample_count=sample_count,
            players=players,
        )
    except Exception as e:
        return HandStrengthResult(
            hand_strength_pct=None,
            sample_count=sample_count,
            players=players,
            degraded=True,
            reason=f"error: {e}",
        )
