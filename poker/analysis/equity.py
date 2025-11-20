from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pokerkit import analysis as pk_analysis  # type: ignore
from pokerkit.hands import StandardHighHand  # type: ignore
from pokerkit.utilities import Deck  # type: ignore

from .preflop_tables import PREFLOP_EQUITIES_BY_PLAYERS


@dataclass
class HandStrengthResult:
    hand_strength_pct: Optional[float]
    model: str = "pokerkit.calculate_hand_strength"
    sample_count: int = 0
    players: int = 0
    degraded: bool = False
    reason: Optional[str] = None


_RANK_ORDER = "23456789TJQKA"


def _short_code(card: Any) -> str:
    """Best-effort extract short code like 'As' from pokerkit card or string."""
    s = str(card).strip()
    if "(" in s and ")" in s:
        try:
            start = s.rfind("(") + 1
            end = s.rfind(")")
            inner = s[start:end].strip()
            if inner:
                return inner
        except Exception:
            pass
    return s


def _rank_suit(card: Any) -> Tuple[Optional[str], Optional[str]]:
    code = _short_code(card)
    if len(code) < 2:
        return None, None
    return code[0], code[1]


def _normalize_preflop_key(hero: Tuple) -> Optional[str]:
    """Normalize hero hole cards to keys like 'AKs', '72o', or 'AA'.

    This is heads-up vs random shorthand; for now we only use rank/suit.
    """
    if len(hero) != 2:
        return None
    r1, s1 = _rank_suit(hero[0])
    r2, s2 = _rank_suit(hero[1])
    if not r1 or not r2 or not s1 or not s2:
        return None
    # Pair
    if r1 == r2:
        return f"{r1}{r2}"
    # Order ranks high-to-low according to standard order
    try:
        i1 = _RANK_ORDER.index(r1)
        i2 = _RANK_ORDER.index(r2)
    except ValueError:
        return None
    if i1 < i2:  # lower index = lower rank
        # swap so that r1 is always higher
        r1, r2, s1, s2 = r2, r1, s2, s1
    suited = s1 == s2
    return f"{r1}{r2}{'s' if suited else 'o'}"




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

    # Preflop: prefer lookup over Monte Carlo to avoid noisy estimates.
    try:
        street_idx = getattr(state, "street_index", None)
    except Exception:
        street_idx = None
    if street_idx == 0 or (street_idx is None and not board):
        key = _normalize_preflop_key(hero)
        table = PREFLOP_EQUITIES_BY_PLAYERS.get(players)
        pct = table.get(key) if table and key else None
        if pct is not None:
            return HandStrengthResult(
                hand_strength_pct=float(pct),
                model="preflop_lookup",
                sample_count=0,
                players=players,
                degraded=False,
                reason=None,
            )
        # Unknown combo or unsupported player count: explicitly mark as unavailable.
        return HandStrengthResult(
            hand_strength_pct=None,
            model="preflop_unavailable",
            sample_count=0,
            players=players,
            degraded=False,
            reason="preflop_unavailable",
        )

    # Time-boxed Monte Carlo: run in batches inside the requested sample_count
    # budget; callers should cap sample_count so that the enclosing timeout
    # (e.g. 300ms) is respected.
    try:
        hole_range: Iterable[Iterable] = (hero,)
        remaining = max(1, sample_count)
        total_strength = 0.0
        total_samples = 0
        batch = 100 if remaining > 200 else remaining
        while remaining > 0:
            cur = min(batch, remaining)
            strength = pk_analysis.calculate_hand_strength(
                players,
                hole_range,
                board,
                2,
                5,
                Deck.STANDARD,
                (StandardHighHand,),
                sample_count=cur,
            )
            total_strength += float(strength) * cur
            total_samples += cur
            remaining -= cur

        if total_samples <= 0:
            return HandStrengthResult(
                hand_strength_pct=None,
                sample_count=0,
                players=players,
                degraded=True,
                reason="no_samples",
            )

        pct = (total_strength / float(total_samples)) * 100.0
        return HandStrengthResult(
            hand_strength_pct=pct,
            sample_count=int(total_samples),
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
