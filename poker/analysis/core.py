from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Tuple


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


def _short_code(card: Any) -> str:
    """Best-effort conversion of a card object/string to short code like 'Qs'.

    Supports raw short codes ('Qs') and verbose strings from pokerkit
    such as 'QUEEN OF SPADES (Qs)' by extracting the text inside the last
    pair of parentheses when present.
    """
    s = str(card).strip()
    # Verbose form like "QUEEN OF SPADES (Qs)"
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


def compute_board_texture(board: Iterable[str]) -> Dict[str, bool]:
    """Compute simple board texture flags from a list of card strings.

    Board cards use standard notation like 'Ah', 'Ts', '9d', etc.
    Flags:
      - paired: any rank appears at least twice
      - monotone: all cards same suit or at least 3 to a flush
      - two_tone: exactly two suits present on the board
      - straighty: ranks form a long consecutive chain
    """
    cards = [c for c in board if c]
    if not cards:
        return {"paired": False, "monotone": False, "two_tone": False, "straighty": False}

    # Extract ranks and suits
    ranks: List[str] = []
    suits: List[str] = []
    for c in cards:
        s = _short_code(c)
        if len(s) < 2:
            continue
        ranks.append(s[0])
        suits.append(s[1])

    # Paired: any rank count >= 2
    paired = False
    rank_counts: Dict[str, int] = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
        if rank_counts[r] >= 2:
            paired = True

    # Suit-based texture
    suit_counts: Dict[str, int] = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    unique_suits = len(suit_counts)
    max_suit_count = max(suit_counts.values()) if suit_counts else 0

    # Monotone if all cards same suit, or at least three to a flush
    monotone = max_suit_count >= 3
    two_tone = unique_suits == 2

    # Straighty: longest consecutive chain on the board is long enough
    # Ranks mapping with A-5 wheel support
    rank_to_val: Mapping[str, int] = {
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "6": 6,
        "7": 7,
        "8": 8,
        "9": 9,
        "T": 10,
        "J": 11,
        "Q": 12,
        "K": 13,
        "A": 14,
    }
    vals: List[int] = []
    for r in ranks:
        base = rank_to_val.get(r)
        if base is None:
            continue
        vals.append(base)
        # For wheel boards (A2345), treat A also as 1
        if r[0] == "A":
            vals.append(1)
    if not vals:
        straighty = False
    else:
        for_straight = sorted(set(vals))
        longest = 1
        cur = 1
        for i in range(1, len(for_straight)):
            if for_straight[i] == for_straight[i - 1] + 1:
                cur += 1
                longest = max(longest, cur)
            else:
                cur = 1
        # Heuristic thresholds from spec:
        # - flop: longest chain >= 3
        # - turn/river: longest chain >= 4
        # Here we only know board length, so approximate:
        if len(cards) <= 3:
            straighty = longest >= 3
        else:
            straighty = longest >= 4

    return {
        "paired": bool(paired),
        "monotone": bool(monotone),
        "two_tone": bool(two_tone),
        "straighty": bool(straighty),
    }


_RANK_TO_VAL: Mapping[str, int] = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


def _parse_cards(cards: Iterable[str]) -> List[Tuple[str, str, int]]:
    parsed: List[Tuple[str, str, int]] = []
    for c in cards:
        s = _short_code(c)
        if len(s) < 2:
            continue
        rank = s[0]
        suit = s[1]
        val = _RANK_TO_VAL.get(rank)
        if val is None:
            continue
        parsed.append((rank, suit, val))
    return parsed


def _longest_straight(vals: Iterable[int]) -> int:
    uniq = sorted(set(vals))
    if not uniq:
        return 0
    # Handle wheel: treat A (14) also as 1
    if 14 in uniq:
        uniq = sorted(set(uniq + [1]))
    longest = 1
    cur = 1
    for i in range(1, len(uniq)):
        if uniq[i] == uniq[i - 1] + 1:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    return longest


def describe_hand(hero_cards: Iterable[str], board: Iterable[str]) -> str:
    """Return a coarse human-readable hand label for hero.

    Priority:
      Straight Flush > Quads > Full House > Flush > Straight >
      Set/Trips > Two Pair > Pair (with Overpair/TPTK) > High Card.
    """
    hero = _parse_cards(hero_cards)
    board_cards = _parse_cards(board)
    # Preflop: keep it simple for MVP
    if not board_cards:
        if len(hero) == 2 and hero[0][0] == hero[1][0]:
            return f"Pocket {hero[0][0]}s"
        return "Preflop"

    all_cards = hero + board_cards
    if len(all_cards) < 5:
        return "Unknown"

    # Counts
    rank_counts: Dict[str, int] = {}
    hero_rank_counts: Dict[str, int] = {}
    board_rank_counts: Dict[str, int] = {}
    suit_counts: Dict[str, int] = {}
    vals: List[int] = []

    for r, s, v in all_cards:
        rank_counts[r] = rank_counts.get(r, 0) + 1
        suit_counts[s] = suit_counts.get(s, 0) + 1
        vals.append(v)
    for r, _, _ in hero:
        hero_rank_counts[r] = hero_rank_counts.get(r, 0) + 1
    for r, _, _ in board_cards:
        board_rank_counts[r] = board_rank_counts.get(r, 0) + 1

    # Flush detection
    flush_suit = None
    for s, cnt in suit_counts.items():
        if cnt >= 5:
            flush_suit = s
            break
    flush_vals = [v for r, s, v in all_cards if s == flush_suit] if flush_suit else []

    # Straight detection
    longest_all = _longest_straight(vals)
    has_straight = longest_all >= 5
    has_straight_flush = False
    if flush_suit:
        longest_flush = _longest_straight(flush_vals)
        has_straight_flush = longest_flush >= 5 and bool(flush_vals)

    # High-rank patterns
    counts_sorted = sorted(rank_counts.values(), reverse=True)
    has_four = 4 in counts_sorted
    has_three = 3 in counts_sorted
    pairs = [r for r, c in rank_counts.items() if c == 2]

    if has_straight_flush:
        return "Straight Flush"
    if has_four:
        return "Quads"
    if has_three and (len(pairs) >= 1 or counts_sorted.count(3) >= 2):
        return "Full House"
    if flush_suit:
        return "Flush"
    if has_straight:
        return "Straight"

    # Trips / Set
    if has_three:
        # Choose top trips rank
        trips_ranks = [r for r, c in rank_counts.items() if c == 3]
        trips_ranks.sort(key=lambda r: _RANK_TO_VAL[r], reverse=True)
        r3 = trips_ranks[0]
        if hero_rank_counts.get(r3, 0) >= 2:
            return "Set"
        if hero_rank_counts.get(r3, 0) >= 1:
            return "Trips"
        # Trips entirely on board
        return "Trips"

    # Two pair
    if len(pairs) >= 2:
        return "Two Pair"

    # One pair / Overpair / Top Pair
    # Board context
    board_vals = [v for _, _, v in board_cards]
    board_top = max(board_vals) if board_vals else None
    hero_vals = [v for _, _, v in hero]
    hero_ranks = [r for r, _, _ in hero]

    hero_has_pair = len(hero) == 2 and hero_ranks[0] == hero_ranks[1]
    hero_pair_val = hero_vals[0] if hero_has_pair else None

    # Hero pairs with board?
    hero_board_pair_ranks = set()
    board_rank_set = {r for r, _, _ in board_cards}
    for r in hero_ranks:
        if r in board_rank_set:
            hero_board_pair_ranks.add(r)

    # If no explicit evidence of a pair, treat as High Card
    if not pairs and not hero_has_pair and not hero_board_pair_ranks:
        return "High Card"

    # Overpair: hero pocket pair above top board rank
    if hero_has_pair and board_top is not None and hero_pair_val > board_top:
        return "Overpair"

    # Top Pair / TPTK: hero has a card matching top board rank
    if board_top is not None:
        # Find rank char for board_top
        top_rank_char = None
        for r, v in _RANK_TO_VAL.items():
            if v == board_top:
                top_rank_char = r
                break
        if top_rank_char and top_rank_char in hero_ranks:
            # Kicker is the other hero card
            if len(hero_vals) == 2:
                kicker_val = hero_vals[0] if hero_ranks[0] != top_rank_char else hero_vals[1]
                other_board_vals = [v for v in board_vals if v != board_top]
                board_other_max = max(other_board_vals) if other_board_vals else 0
                if kicker_val > board_other_max:
                    return "Top Pair, Top Kicker"
            return "Top Pair"

    # Any other made pair
    return "Pair"


def compute_outs(hero_cards: Iterable[str], board: Iterable[str]) -> Dict[str, Any]:
    """Compute simplified hero-only outs for flush/OESD/combination draws.

    Rules:
      - Flush draw: 9 outs if hero+board have >=4 of a suit and hero holds
        at least one card of that suit.
      - OESD: 8 outs if hero+board ranks contain a 4-long consecutive chain
        (with wheel support) in which at least one rank is from hero.
      - Combo: if both flush draw and OESD, report 15 outs.
    """
    hero = _parse_cards(hero_cards)
    board_cards = _parse_cards(board)
    all_cards = hero + board_cards
    if not hero or not board_cards:
        return {"flush_draw": False, "oesd": False, "combo": False, "outs": 0}

    # Suit counts
    suit_counts: Dict[str, int] = {}
    for _, s, _ in all_cards:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    # Flush draw detection
    flush_draw = False
    hero_suits = {s for _, s, _ in hero}
    for suit, cnt in suit_counts.items():
        if cnt >= 4 and suit in hero_suits:
            flush_draw = True
            break

    # OESD detection: look for 4-long straight chain that includes hero rank
    all_vals = [v for _, _, v in all_cards]
    longest = _longest_straight(all_vals)
    oesd = False
    if longest >= 4:
        # Build full rank set with wheel
        uniq = sorted(set(all_vals))
        if 14 in uniq:
            uniq = sorted(set(uniq + [1]))
        hero_vals = {v for _, _, v in hero}
        # Treat hero A as 1 as well for wheel involvement
        if 14 in hero_vals:
            hero_vals.add(1)
        # Scan all 4-length chains and see if hero participates
        for i in range(len(uniq)):
            chain = [uniq[i]]
            for j in range(i + 1, len(uniq)):
                if uniq[j] == chain[-1] + 1:
                    chain.append(uniq[j])
                elif uniq[j] > chain[-1] + 1:
                    break
                if len(chain) >= 4:
                    if hero_vals.intersection(chain):
                        oesd = True
                        break
            if oesd:
                break

    # Outs accounting
    if flush_draw and oesd:
        outs = 15
        combo = True
    elif flush_draw:
        outs = 9
        combo = False
    elif oesd:
        outs = 8
        combo = False
    else:
        outs = 0
        combo = False

    return {
        "flush_draw": bool(flush_draw),
        "oesd": bool(oesd),
        "combo": bool(combo),
        "outs": int(outs),
    }
