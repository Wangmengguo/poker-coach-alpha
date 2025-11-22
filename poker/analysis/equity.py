from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pokerkit import analysis as pk_analysis  # type: ignore
from pokerkit.hands import StandardHighHand  # type: ignore
from pokerkit.utilities import Deck  # type: ignore

from .preflop_tables import PREFLOP_EQUITIES_BY_PLAYERS
from .ranges import Range


@dataclass
class HandStrengthResult:
    hand_strength_pct: Optional[float]
    model: str = "pokerkit.calculate_hand_strength"
    sample_count: int = 0
    players: int = 0
    degraded: bool = False
    reason: Optional[str] = None


_RANK_ORDER = "23456789TJQKA"
_SUITS = ["s", "h", "d", "c"]


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


def _expand_range_key(key: str) -> Optional[Tuple[str, str, Optional[str]]]:
    """Parse a shorthand like 'AKs', 'AQo', 'TT' into (hi, lo, suited_flag)."""
    if len(key) == 2:  # pair e.g., 'AA'
        return key[0], key[1], None
    if len(key) == 3:
        r1, r2, flag = key[0], key[1], key[2].lower()
        return r1, r2, flag
    return None


def _combos_for_key(key: str) -> list[Tuple[str, str]]:
    """Generate all hole-card combos matching a shorthand key."""
    parsed = _expand_range_key(key)
    if not parsed:
        return []
    r1, r2, flag = parsed
    cards = []
    if r1 == r2:
        # Pair: 6 combos
        for i in range(len(_SUITS)):
            for j in range(i + 1, len(_SUITS)):
                cards.append((f"{r1}{_SUITS[i]}", f"{r2}{_SUITS[j]}"))
        return cards
    # Non-pair
    if flag == "s":  # suited
        for s in _SUITS:
            cards.append((f"{r1}{s}", f"{r2}{s}"))
    elif flag == "o":  # offsuit
        for s1 in _SUITS:
            for s2 in _SUITS:
                if s1 != s2:
                    cards.append((f"{r1}{s1}", f"{r2}{s2}"))
    else:
        # If unspecified, allow both suited and offsuit
        for s1 in _SUITS:
            for s2 in _SUITS:
                if r1 == r2 and s1 >= s2:
                    continue
                cards.append((f"{r1}{s1}", f"{r2}{s2}"))
    return cards


def _deck_without(dead: Iterable[str]) -> list[str]:
    base = [r + s for r in _RANK_ORDER for s in _SUITS]
    dead_set = {c.lower() for c in dead}
    return [c for c in base if c.lower() not in dead_set]


def _score_five(cards5: Iterable[str]) -> Tuple[int, list[int]]:
    """Simple 5-card evaluator returning (category, kickers list).

    Categories:
      8 SF, 7 Quads, 6 Full House, 5 Flush, 4 Straight, 3 Trips, 2 Two Pair, 1 Pair, 0 High Card.
    """
    # map ranks to values with A=14
    ranks = []
    suits = []
    for c in cards5:
        r, s = c[0], c[1]
        ranks.append(_RANK_ORDER.index(r) + 2)
        suits.append(s)
    ranks.sort()
    from collections import Counter

    rc = Counter(ranks)
    counts = sorted(rc.items(), key=lambda x: (-x[1], -x[0]))
    is_flush = len(set(suits)) == 1
    # Straight check with wheel support
    unique_r = sorted(set(ranks))
    is_straight = False
    high_straight = 0
    if len(unique_r) == 5:
        if unique_r[-1] - unique_r[0] == 4:
            is_straight = True
            high_straight = unique_r[-1]
        elif unique_r == [2, 3, 4, 5, 14]:
            is_straight = True
            high_straight = 5

    if is_straight and is_flush:
        return 8, [high_straight]
    if counts[0][1] == 4:
        quad = counts[0][0]
        kicker = max(r for r in ranks if r != quad)
        return 7, [quad, kicker]
    if counts[0][1] == 3 and counts[1][1] == 2:
        return 6, [counts[0][0], counts[1][0]]
    if is_flush:
        return 5, sorted(ranks, reverse=True)
    if is_straight:
        return 4, [high_straight]
    if counts[0][1] == 3:
        trips = counts[0][0]
        kickers = sorted([r for r in ranks if r != trips], reverse=True)
        return 3, [trips] + kickers
    if counts[0][1] == 2 and counts[1][1] == 2:
        pairs = sorted([counts[0][0], counts[1][0]], reverse=True)
        kicker = max(r for r in ranks if r not in pairs)
        return 2, pairs + [kicker]
    if counts[0][1] == 2:
        pair = counts[0][0]
        kickers = sorted([r for r in ranks if r != pair], reverse=True)
        return 1, [pair] + kickers
    return 0, sorted(ranks, reverse=True)


def _best5_score(seven: Iterable[str]) -> Tuple[int, list[int]]:
    from itertools import combinations

    best = None
    for combo in combinations(seven, 5):
        score = _score_five(combo)
        if best is None or score > best:
            best = score
    return best or (0, [])


def _sample_villain_hand(range_: Range, dead: Iterable[str], rnd) -> Optional[Tuple[str, str]]:
    combos: list[Tuple[str, str]] = []
    weights: list[float] = []
    dead_set = {c.lower() for c in dead}
    for key, w in range_.items():
        for h1, h2 in _combos_for_key(key):
            if h1.lower() in dead_set or h2.lower() in dead_set or h1.lower() == h2.lower():
                continue
            combos.append((h1, h2))
            weights.append(float(max(w, 0.0)))
    if not combos or sum(weights) <= 0:
        return None
    # weighted choice
    total = sum(weights)
    r = rnd.random() * total
    acc = 0.0
    for c, w in zip(combos, weights):
        acc += w
        if r <= acc:
            return c
    return combos[-1]


def _complete_board(board: Iterable[str], deck: list[str], rnd) -> list[str]:
    need = max(0, 5 - len(board))
    deck_copy = list(deck)
    rnd.shuffle(deck_copy)
    return list(board) + deck_copy[:need]


@dataclass
class EquityResult:
    win_pct: float
    tie_pct: float
    lose_pct: float
    sample_count: int
    players: int
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


def compute_equity_vs_range(
    state: Any,
    hero_idx: int,
    villain_range: Range,
    sample_count: int = 200,
    rng_seed: Optional[int] = None,
) -> EquityResult:
    """Monte Carlo equity vs a specific villain range (heads-up only for now)."""

    import random

    rnd = random.Random(rng_seed)

    # Gather hero cards and board
    hero = _hero_hole_cards(state, hero_idx)
    board = _flatten_board_cards(state)

    if not hero or len(hero) != 2:
        return EquityResult(
            win_pct=0.0,
            tie_pct=0.0,
            lose_pct=0.0,
            sample_count=0,
            players=0,
            degraded=True,
            reason="hero_cards_missing",
        )

    dead_cards = list(hero) + list(board)
    wins = ties = losses = 0
    actual_samples = 0

    for _ in range(max(1, sample_count)):
        villain_hand = _sample_villain_hand(villain_range, dead_cards, rnd)
        if villain_hand is None:
            return EquityResult(
                win_pct=0.0,
                tie_pct=0.0,
                lose_pct=0.0,
                sample_count=0,
                players=0,
                degraded=True,
                reason="empty_range",
            )
        # Build deck minus dead cards and villain hand
        board_now = list(board)
        dead_now = dead_cards + list(villain_hand)
        deck = _deck_without(dead_now)
        full_board = _complete_board(board_now, deck, rnd)

        hero_score = _best5_score(list(hero) + full_board)
        villain_score = _best5_score(list(villain_hand) + full_board)
        if hero_score > villain_score:
            wins += 1
        elif hero_score == villain_score:
            ties += 1
        else:
            losses += 1
        actual_samples += 1

    total = float(max(1, actual_samples))
    return EquityResult(
        win_pct=wins * 100.0 / total,
        tie_pct=ties * 100.0 / total,
        lose_pct=losses * 100.0 / total,
        sample_count=actual_samples,
        players=2,
        degraded=False,
        reason=None,
    )
