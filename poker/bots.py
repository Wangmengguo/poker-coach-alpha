from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from .analysis.compose import compose_analysis


class SimpleBot:
    """Very naive bot that respects provided legal_actions.

    Preference: check > call > min raise_to > fold > anything.
    """

    def choose(self, legal_actions: List[Dict]) -> Dict:
        if not legal_actions:
            return {"type": "check"}
        for action_type in ("check", "call"):
            for action in legal_actions:
                if action.get("type") == action_type:
                    return action
        # pick smallest raise_to if any
        raises = [action for action in legal_actions if action.get("type") == "raise_to"]
        if raises:
            raises.sort(key=lambda action: action.get("amount", 0))
            return raises[0]
        # else fold if available
        for action in legal_actions:
            if action.get("type") == "fold":
                return action
        return random.choice(legal_actions)


def _edge_thresholds(street: str) -> Tuple[float, float, float]:
    """Return (weak, strong, very_strong) edge thresholds for a given street."""
    name = (street or "").lower()
    if name == "preflop":
        return -15.0, 15.0, 25.0
    if name == "flop":
        return -12.0, 12.0, 22.0
    if name == "turn":
        return -10.0, 10.0, 20.0
    if name == "river":
        return -8.0, 8.0, 18.0
    # Fallback for unknown street names
    return -10.0, 10.0, 20.0


class EquityBot:
    """Equity/EV-aware bot that chooses actions from legal_actions.

    Uses hand_strength_pct vs required_equity_pct plus simple heuristics on
    SPR 和底池赔率来在 fold / call / raise_to 之间选择。
    """

    def __init__(self, *, hand_strength_samples: int = 50, seed: Optional[int] = None) -> None:
        self.hand_strength_samples = hand_strength_samples
        self.rng = random.Random(seed)
        self._fallback = SimpleBot()

    def _clamp_pct(self, value: Optional[float]) -> float:
        if value is None:
            return 50.0
        return max(0.0, min(100.0, float(value)))

    def _pick_raises(
        self, legal_actions: List[Dict]
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        fixed = [
            action
            for action in legal_actions
            if action.get("type") == "raise_to" and "amount" in action
        ]
        fixed.sort(key=lambda action: action.get("amount", 0))
        ranged = [
            action
            for action in legal_actions
            if action.get("type") == "raise_to"
            and "amount" not in action
            and ("min" in action or "max" in action)
        ]
        return fixed, ranged, legal_actions

    def _pick_small_raise(self, fixed_raises: List[Dict]) -> Optional[Dict]:
        if not fixed_raises:
            return None
        return fixed_raises[0]

    def _pick_medium_raise(self, fixed_raises: List[Dict]) -> Optional[Dict]:
        if not fixed_raises:
            return None
        index = len(fixed_raises) // 2
        return fixed_raises[index]

    def _pick_large_raise(self, fixed_raises: List[Dict]) -> Optional[Dict]:
        if not fixed_raises:
            return None
        return fixed_raises[-1]

    def _build_range_raise(self, ranged_raises: List[Dict], fraction: float) -> Optional[Dict]:
        if not ranged_raises:
            return None
        # Use the first range entry as baseline
        entry = ranged_raises[0]
        min_to = entry.get("min")
        max_to = entry.get("max")
        if min_to is None and max_to is None:
            return None
        if min_to is None:
            min_to = max_to
        if max_to is None:
            max_to = min_to
        if min_to is None or max_to is None:
            return None
        fraction_clamped = max(0.0, min(1.0, fraction))
        amount = int(round(min_to + (max_to - min_to) * fraction_clamped))
        if amount < min_to:
            amount = min_to
        if amount > max_to:
            amount = max_to
        return {"type": "raise_to", "amount": amount}

    def choose(
        self,
        state: Any,
        hero_idx: int,
        hero_seat: int,
        legal_actions: List[Dict],
    ) -> Dict:
        """Choose an action based on equity/EV heuristics."""
        if not legal_actions:
            return {"type": "check"}

        # Fast path: if anything goes wrong, fall back to SimpleBot.
        try:
            decision_context, _ = compose_analysis(
                state,
                hero_idx,
                hero_seat,
                session_stats=None,
                positions_map=None,
                include_hand_strength=True,
                hand_strength_samples=self.hand_strength_samples,
            )
        except Exception:
            return self._fallback.choose(legal_actions)

        hand_strength = self._clamp_pct(decision_context.hand_strength_pct)
        required_equity = self._clamp_pct(decision_context.required_equity_pct)
        edge = hand_strength - required_equity

        weak_edge, strong_edge, very_strong_edge = _edge_thresholds(decision_context.street)

        to_call = max(0, int(decision_context.to_call))
        spr = float(decision_context.spr)

        # Categorize hand
        is_weak = edge <= weak_edge
        is_strong = edge >= strong_edge
        is_very_strong = edge >= very_strong_edge

        # Partition action space
        has_type = {action.get("type") for action in legal_actions}
        fixed_raises, ranged_raises, _ = self._pick_raises(legal_actions)

        def first_of(action_type: str) -> Optional[Dict]:
            for action in legal_actions:
                if action.get("type") == action_type:
                    return action
            return None

        # Scenario A: no bet to call (to_call == 0)
        if to_call == 0:
            check_action = first_of("check")
            if check_action is None:
                # Defensive: treat a zero-cost call as check, else fallback
                call_action = first_of("call")
                if call_action is not None and int(call_action.get("amount") or 0) == 0:
                    return call_action
                return self._fallback.choose(legal_actions)

            if is_strong and hand_strength >= 65.0:
                # Strong hand in an unopened pot: prefer raising to build pot
                target_action: Optional[Dict] = None
                if fixed_raises:
                    target_action = self._pick_medium_raise(fixed_raises)
                    # Mild randomization between medium and small raise
                    if target_action and self.rng.random() < 0.3:
                        small = self._pick_small_raise(fixed_raises)
                        if small is not None:
                            target_action = small
                elif ranged_raises:
                    target_action = self._build_range_raise(ranged_raises, 0.5)
                if target_action is not None:
                    return target_action
                return check_action

            # Marginal hand: mostly check, occasionally small raise for variety
            if weak_edge < edge < strong_edge and hand_strength >= 45.0:
                if fixed_raises and abs(edge) <= 5.0 and self.rng.random() < 0.2:
                    small_raise = self._pick_small_raise(fixed_raises)
                    if small_raise is not None:
                        return small_raise
                return check_action

            # Weak hand: always take the free card
            return check_action

        # Scenario B: facing a bet (to_call > 0)
        can_fold = "fold" in has_type
        can_call = "call" in has_type

        # Clear fold when badly behind on equity
        if is_weak and can_fold:
            return first_of("fold") or self._fallback.choose(legal_actions)

        # Marginal hands: mostly call, with some randomized folds/raises near breakeven
        if weak_edge < edge < strong_edge and can_call:
            abs_edge = abs(edge)
            if edge < 0.0 and abs_edge <= 5.0 and can_fold:
                if self.rng.random() < 0.8:
                    fold_action = first_of("fold")
                    if fold_action is not None:
                        return fold_action
            if edge > 0.0 and abs_edge <= 5.0 and fixed_raises and self.rng.random() < 0.25:
                candidate = (
                    self._pick_small_raise(fixed_raises)
                    if self.rng.random() < 0.5
                    else self._pick_medium_raise(fixed_raises)
                )
                if candidate is not None:
                    return candidate
            call_action = first_of("call")
            if call_action is not None:
                return call_action

        # Strong hands: prefer raising
        if is_strong:
            # Very strong hand with low SPR: lean towards bigger raises
            if is_very_strong and spr <= 3.0:
                if fixed_raises:
                    large = self._pick_large_raise(fixed_raises)
                    if large is not None:
                        return large
                if ranged_raises:
                    aggressive = self._build_range_raise(ranged_raises, 0.9)
                    if aggressive is not None:
                        return aggressive

            # Otherwise, choose a medium-to-large raise
            if fixed_raises:
                index = max(len(fixed_raises) // 2, len(fixed_raises) - 2)
                index = min(index, len(fixed_raises) - 1)
                return fixed_raises[index]
            if ranged_raises:
                medium = self._build_range_raise(ranged_raises, 0.5)
                if medium is not None:
                    return medium
            if can_call:
                call_action = first_of("call")
                if call_action is not None:
                    return call_action

        # Fallback for cases without clear strong/weak signals
        if can_call:
            call_action = first_of("call")
            if call_action is not None:
                return call_action
        if can_fold:
            return first_of("fold") or self._fallback.choose(legal_actions)

        # Last resort: reuse SimpleBot priority
        return self._fallback.choose(legal_actions)
