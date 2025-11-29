from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from .core import (
    compute_board_texture,
    compute_outs,
    compute_pot_math,
    compute_pot_odds_and_equity_need,
    describe_hand,
)
from .equity import compute_hand_strength, compute_equity_vs_range
from .models import DecisionContext
from .stats import HumanStats, build_stats_payload
from .ranges import build_default_preflop_range


def _safe_list(obj: Any) -> List:
    try:
        return list(obj or [])
    except Exception:
        return []


def _flatten_board_cards(state: Any) -> List[str]:
    cards: List[str] = []
    for street in _safe_list(getattr(state, "board_cards", [])):
        for c in street or []:
            cards.append(str(c))
    return cards


def _hero_cards(state: Any, hero_idx: int) -> List[str]:
    holes = _safe_list(getattr(state, "hole_cards", []))
    if 0 <= hero_idx < len(holes):
        return [str(c) for c in holes[hero_idx] or []]
    return []


def _count_live_players(state: Any) -> int:
    statuses = _safe_list(getattr(state, "statuses", []))
    if statuses:
        try:
            return int(sum(1 for x in statuses if bool(x)))
        except Exception:
            pass
    stacks = _safe_list(getattr(state, "stacks", []))
    if stacks:
        try:
            return int(sum(1 for s in stacks if (s or 0) > 0))
        except Exception:
            pass
    return 0


def compose_analysis(
    state: Any,
    hero_idx: int,
    hero_seat: int,
    *,
    session_stats: Optional[HumanStats] = None,
    positions_map: Optional[Dict[str, str]] = None,
    include_hand_strength: bool = False,
    hand_strength_samples: int = 100,
) -> Tuple[DecisionContext, Dict[str, Any]]:
    """Extract decision context and prompt-friendly analysis payload.

    include_hand_strength:
        Default False to avoid blocking prompt on Monte Carlo. In engine we
        stream hand strength asynchronously; callers can set True for
        synchronous contexts or tests.
    """

    # Pot math
    pot_math = compute_pot_math(state, hero_idx)
    current_street_bets_sum = int(sum(_safe_list(getattr(state, "bets", []))))
    pot_extra = compute_pot_odds_and_equity_need(
        pot=pot_math["pot"],
        to_call=pot_math["to_call"],
        current_street_bets_sum=current_street_bets_sum,
    )

    # Cards / board
    hero_cards = _hero_cards(state, hero_idx)
    board_cards = _flatten_board_cards(state)
    board_texture = compute_board_texture(board_cards)
    hand_label = describe_hand(hero_cards, board_cards) if hero_cards else None
    outs_payload = compute_outs(hero_cards, board_cards) if hero_cards and board_cards else None
    outs_value = int(outs_payload.get("outs", 0)) if outs_payload else 0

    # Stats (human-only)
    stats_payload = build_stats_payload(session_stats) if session_stats else None

    # Street & position
    try:
        street_idx = getattr(state, "street_index", None)
        street = ["preflop", "flop", "turn", "river"][street_idx] if street_idx is not None else "unknown"
    except Exception:
        street = "unknown"
    hero_position = positions_map.get(str(hero_seat)) if positions_map else None

    players_count = _count_live_players(state)

    # Hand strength (optional to avoid extra Monte Carlo on prompt)
    hand_strength_pct: Optional[float] = None
    degraded = False
    reason: Optional[str] = None
    if include_hand_strength:
        try:
            hs_res = compute_hand_strength(state, hero_idx, sample_count=hand_strength_samples)
            hand_strength_pct = hs_res.hand_strength_pct
            degraded = bool(hs_res.degraded)
            reason = hs_res.reason
        except Exception as exc:  # pragma: no cover - defensive
            hand_strength_pct = None
            degraded = True
            reason = f"error: {exc}"

    # Preflop equity vs default range (heads-up approximation)
    range_equity_payload: Optional[Dict[str, Any]] = None
    if street == "preflop" and hero_cards:
        try:
            # Use a conservative default villain range for a generic position.
            # Stack depth is approximated as 100bb for now.
            villain_range = build_default_preflop_range("MP", stack_bb=100)
            eq_res = compute_equity_vs_range(
                state,
                hero_idx,
                villain_range,
                sample_count=200,
                rng_seed=None,
            )
            range_equity_payload = {
                "model": "vs_default_range",
                "equity_pct": round(eq_res.win_pct + 0.5 * eq_res.tie_pct, 1),
                "players": eq_res.players,
                "sample_count": eq_res.sample_count,
                "position": "MP",
            }
        except Exception:
            range_equity_payload = None

    dc = DecisionContext(
        street=street,
        hero_seat=hero_seat,
        hero_position=hero_position,
        to_call=pot_math["to_call"],
        pot=pot_math["pot"],
        current_street_bets_sum=current_street_bets_sum,
        pot_decision=pot_extra["pot_decision"],
        pot_odds_pct=pot_extra["pot_odds_pct"],
        required_equity_pct=pot_extra["required_equity_pct"],
        effective_stack=pot_math["effective_stack"],
        spr=pot_math["spr"],
        hand_strength_pct=hand_strength_pct,
        hand_label=hand_label,
        outs=outs_value,
        draw_info=outs_payload,
        board_texture=board_texture,
        players_count=players_count,
        human_stats=stats_payload,
        hero_cards=hero_cards or None,
        board_cards=board_cards or None,
        degraded=degraded,
        reason=reason,
    )

    analysis_payload: Dict[str, Any] = {
        "pot_math": {
            "to_call": pot_math["to_call"],
            "pot": pot_math["pot"],
            "effective_stack": pot_math["effective_stack"],
            "spr": pot_math["spr"],
        },
        "pot_extra": pot_extra,
    }
    if board_texture:
        analysis_payload["board_texture"] = board_texture
    if hand_label is not None:
        analysis_payload.setdefault("hand", {})["label"] = hand_label
    if outs_payload is not None:
        analysis_payload["outs"] = outs_payload
    if stats_payload is not None:
        analysis_payload["stats"] = stats_payload
    if range_equity_payload is not None:
        analysis_payload["range_equity"] = range_equity_payload
    if hero_position:
        analysis_payload.setdefault("context", {})["hero_position"] = hero_position
    # hand_strength is intentionally sent via async update elsewhere; skip here by default
    return dc, analysis_payload
