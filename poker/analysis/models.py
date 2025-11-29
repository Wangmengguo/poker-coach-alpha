from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DecisionContext:
    """Unified decision context shared by Coach and (future) Bot logic."""

    # Basic situation
    street: str
    hero_seat: int
    hero_position: Optional[str]

    # Pot math
    to_call: int
    pot: int
    current_street_bets_sum: int
    pot_decision: float
    pot_odds_pct: float
    required_equity_pct: float

    # Stack depth
    effective_stack: int
    spr: float

    # Hand info
    hand_strength_pct: Optional[float]
    hand_label: Optional[str]
    outs: int
    draw_info: Optional[Dict[str, Any]]
    board_texture: Dict[str, bool]

    # Context
    players_count: int
    human_stats: Optional[Dict[str, Any]] = None

    # Cards (hero + public board) for coaching/LLM contexts
    hero_cards: Optional[List[str]] = None
    board_cards: Optional[List[str]] = None

    # Future extensions
    villain_ranges: Optional[Dict[int, Any]] = None
    degraded: bool = False
    reason: Optional[str] = None
