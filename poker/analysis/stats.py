from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class HumanStats:
    """Session-scoped human-only stats for VPIP/PFR/AFq.

    This structure is intentionally minimal and pure so that it can be
    unit-tested independently of the engine. It is owned by TableEngine
    but all update rules live here.
    """

    vpip_opportunities: int = 0
    vpip_voluntary: int = 0
    pfr_raises: int = 0  # hands with a preflop raise by hero
    # AFq components (postflop only):
    afq_agg: int = 0  # bets + raises count
    afq_total: int = 0  # bets + raises + calls + checks (no folds)
    # Per-hand flags
    vpip_opp_counted: bool = False
    vpip_counted: bool = False
    pfr_counted: bool = False


def new_session_stats() -> HumanStats:
    """Create a fresh stats container for a new session."""
    return HumanStats()


def reset_hand_flags(stats: HumanStats) -> None:
    """Reset per-hand flags while keeping cumulative session counters."""
    stats.vpip_opp_counted = False
    stats.vpip_counted = False
    stats.pfr_counted = False


def ensure_preflop_opportunity(stats: HumanStats, *, street: str, is_hero: bool) -> None:
    """Count a VPIP opportunity for the human on the first preflop prompt."""
    if not is_hero:
        return
    if street != "preflop":
        return
    if stats.vpip_opp_counted:
        return
    stats.vpip_opportunities += 1
    stats.vpip_opp_counted = True


def record_action_stats(
    stats: HumanStats,
    *,
    street: str,
    is_hero: bool,
    action_type: str,
) -> None:
    """Update VPIP/PFR/AFq counters given a single action.

    - VPIP: first time the hero voluntarily puts chips in preflop (call/raise_to).
    - PFR: first preflop raise_to by hero (counts hand as raised preflop).
    - AFq: postflop (bets + raises) / (bets + raises + calls + checks); folds excluded.
    """
    if not is_hero:
        return

    is_preflop = street == "preflop"

    # VPIP tracking (human-only, preflop, voluntary money): call or raise_to counts once per hand
    if is_preflop and not stats.vpip_counted and action_type in ("call", "raise_to"):
        stats.vpip_voluntary += 1
        stats.vpip_counted = True

    # PFR tracking (human-only, preflop): any raise action (incl. 3bet+) counts once per hand
    if is_preflop and not stats.pfr_counted and action_type == "raise_to":
        stats.pfr_raises += 1
        stats.pfr_counted = True

    # AFq tracking (postflop only): (bets + raises) / (bets + raises + calls + checks)
    if not is_preflop:
        if action_type == "raise_to":
            # We treat both bets and raises as aggression.
            stats.afq_agg += 1
            stats.afq_total += 1
        elif action_type in ("check", "call"):
            stats.afq_total += 1
        # folds are excluded from denominator by convention


def build_stats_payload(stats: HumanStats) -> Dict[str, Any]:
    """Build a prompt-safe stats payload with percentages and raw counts."""
    vpip_num = int(stats.vpip_voluntary)
    vpip_den = int(stats.vpip_opportunities)
    vpip_pct = float(vpip_num * 100.0 / vpip_den) if vpip_den > 0 else 0.0

    # PFR uses the same opportunity denominator as VPIP
    pfr_num = int(stats.pfr_raises)
    pfr_den = vpip_den
    pfr_pct = float(pfr_num * 100.0 / pfr_den) if pfr_den > 0 else 0.0

    # AFq across postflop streets
    afq_agg = int(stats.afq_agg)
    afq_total = int(stats.afq_total)
    afq_pct = float(afq_agg * 100.0 / afq_total) if afq_total > 0 else 0.0

    hands = vpip_den

    # TL×AP style mapping with small-sample guard.
    if hands < 20:
        style = "Unknown"
    else:
        loose = vpip_pct >= 28.0
        tight = vpip_pct <= 18.0
        aggressive = afq_pct >= 45.0
        passive = afq_pct <= 30.0

        if tight and aggressive:
            style = "Tight-Aggressive"
        elif tight and passive:
            style = "Tight-Passive"
        elif loose and aggressive:
            style = "Loose-Aggressive"
        elif loose and passive:
            style = "Loose-Passive"
        else:
            style = "Unknown"

    return {
        "vpip_pct": round(vpip_pct, 1),
        "vpip_voluntary": vpip_num,
        "vpip_opportunities": vpip_den,
        "pfr_pct": round(pfr_pct, 1),
        "pfr_raises": pfr_num,
        "pfr_opportunities": pfr_den,
        "afq_pct": round(afq_pct, 1),
        "afq_agg": afq_agg,
        "afq_total": afq_total,
        "hands": int(hands),
        "style": style,
    }

