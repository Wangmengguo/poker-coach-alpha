from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .analysis.compose import compose_analysis
from .analysis.models import DecisionContext
from .ai_coach import AiProvider, AiAdvice, generate_llm_actions_only
from .engine import TableEngine


@dataclass
class LlmDecisionResult:
    action: Dict[str, Any]
    advice: Optional[AiAdvice]
    llm_failed: bool


class LlmBot:
    """LLM-driven bot wrapper for simulation.

    This bot:
    - Uses the existing analysis pipeline (DecisionContext via compose_analysis).
    - Calls generate_llm_actions_only to obtain LLM-recommended actions.
    - Applies a safe fallback policy when the LLM output is unusable.
    """

    def __init__(
        self,
        provider: AiProvider,
        *,
        model_alias: str,
        llm_timeout_seconds: float = 5.0,
    ) -> None:
        self.provider = provider
        self.model_alias = model_alias
        self.llm_timeout_seconds = max(0.1, float(llm_timeout_seconds))

    async def choose_action(
        self,
        engine: TableEngine,
        hero_idx: int,
        hero_seat: int,
    ) -> LlmDecisionResult:
        """Return a single legal action for the current decision.

        The engine is assumed to be in a state where hero_seat is to act.
        """
        state = engine.state
        legal_actions = engine.legal_actions()
        if not legal_actions or state is None:
            # Degenerate case: nothing to do; treat as check when possible.
            fallback = self._fallback_action(legal_actions, to_call=0)
            return LlmDecisionResult(action=fallback, advice=None, llm_failed=True)

        hero_index = hero_idx

        try:
            positions_map = None
            try:
                positions_map = engine._positions_map()  # type: ignore[attr-defined]
            except Exception:
                positions_map = None

            dc, _payload = compose_analysis(
                state,
                hero_index,
                hero_seat,
                session_stats=getattr(engine, "session_stats", None),
                positions_map=positions_map,
                include_hand_strength=False,
            )
        except Exception:
            # If analysis fails, fall back immediately.
            fallback = self._fallback_action(legal_actions, to_call=0)
            return LlmDecisionResult(action=fallback, advice=None, llm_failed=True)

        llm_failed = False
        advice: Optional[AiAdvice]
        try:
            advice = await generate_llm_actions_only(
                dc,
                legal_actions,
                self.provider,
                action_history=getattr(engine, "action_history", None),
                llm_timeout_seconds=self.llm_timeout_seconds,
            )
        except Exception:
            advice = None
            llm_failed = True

        action: Dict[str, Any]
        if advice is None or advice.recommended_action is None:
            llm_failed = True
            to_call = getattr(dc, "to_call", 0) or 0
            action = self._fallback_action(legal_actions, to_call=int(to_call))
        else:
            action = advice.recommended_action

        return LlmDecisionResult(
            action=action,
            advice=advice,
            llm_failed=llm_failed,
        )

    def _fallback_action(self, legal_actions: List[Dict[str, Any]], to_call: int) -> Dict[str, Any]:
        """Safe fallback when LLM output is unusable.

        Policy:
        - If to_call == 0 and there is a 'check', use 'check'.
        - Else if there is 'fold', use 'fold'.
        - Else if there is 'call', use 'call'.
        - Else return the first legal action or a dummy check.
        """
        if not legal_actions:
            return {"type": "check"}

        if to_call == 0:
            for action in legal_actions:
                if action.get("type") == "check":
                    return action

        for action in legal_actions:
            if action.get("type") == "fold":
                return action

        for action in legal_actions:
            if action.get("type") == "call":
                return action

        return legal_actions[0]

