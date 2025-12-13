from __future__ import annotations

import asyncio
from typing import Dict, List

from poker.ai_coach import AiProvider, DummyProvider, generate_ai_advice
from poker.analysis.models import DecisionContext


class _FakeProvider:
    def __init__(self, text: str) -> None:
        self._text = text

    async def generate(self, prompt: str) -> str:  # noqa: ARG002
        return self._text


def _dc(hand_strength_pct: float | None = None) -> DecisionContext:
    return DecisionContext(
        street="preflop",
        hero_seat=1,
        hero_position="BTN",
        to_call=2,
        pot=9,
        current_street_bets_sum=0,
        pot_decision=9.0,
        pot_odds_pct=22.2,
        required_equity_pct=22.2,
        effective_stack=399,
        spr=399.0,
        hand_strength_pct=hand_strength_pct,
        hand_label="Preflop",
        outs=0,
        draw_info=None,
        board_texture={},
        players_count=5,
    )


def test_generate_ai_advice_accepts_action_spec_json() -> None:
    legal_actions: List[Dict] = [{"type": "fold"}, {"type": "call", "amount": 2}]
    provider: AiProvider = _FakeProvider(
        '{"recommended_action":{"type":"call","amount":2},"secondary_action":{"type":"fold"},'
        '"confidence":0.8,"explanation":"Call looks fine."}'
    )
    advice = asyncio.run(generate_ai_advice(_dc(), legal_actions, provider))
    assert advice.reason == "llm_actions"
    assert advice.recommended_action == {"type": "call", "amount": 2}
    assert advice.secondary_action == {"type": "fold"}

def test_generate_ai_advice_accepts_python_literal_dict() -> None:
    legal_actions: List[Dict] = [{"type": "fold"}, {"type": "call", "amount": 2}]
    provider: AiProvider = _FakeProvider(
        "{'recommended_action': {'type': 'call', 'amount': 2}, 'secondary_action': None, "
        "'confidence': 0.55, 'explanation': 'OK'}"
    )
    advice = asyncio.run(generate_ai_advice(_dc(), legal_actions, provider))
    assert advice.reason == "llm_actions"
    assert advice.recommended_action == {"type": "call", "amount": 2}


def test_generate_ai_advice_extracts_first_balanced_object() -> None:
    legal_actions: List[Dict] = [{"type": "fold"}, {"type": "call", "amount": 2}]
    provider: AiProvider = _FakeProvider(
        'Here you go:\n```json\n{"recommended_id": 1, "secondary_id": 0, "confidence": 0.8,'
        ' "explanation": "Call."}\n```\n(extra { braces } after)'
    )
    advice = asyncio.run(generate_ai_advice(_dc(), legal_actions, provider))
    assert advice.reason == "llm_actions"
    assert advice.recommended_action == {"type": "call", "amount": 2}
    assert advice.secondary_action == {"type": "fold"}


def test_generate_ai_advice_parse_failed_falls_back_with_reason() -> None:
    legal_actions: List[Dict] = [{"type": "fold"}, {"type": "call", "amount": 2}]
    provider: AiProvider = _FakeProvider("this is not json")
    advice = asyncio.run(
        generate_ai_advice(_dc(hand_strength_pct=40.0), legal_actions, provider)
    )
    assert advice.reason == "llm_parse_failed_heuristic_actions"
    assert advice.recommended_action in legal_actions


def test_generate_ai_advice_dummy_provider_reports_dummy_reason() -> None:
    legal_actions: List[Dict] = [{"type": "fold"}, {"type": "call", "amount": 2}]
    provider: AiProvider = DummyProvider()
    advice = asyncio.run(
        generate_ai_advice(_dc(hand_strength_pct=40.0), legal_actions, provider)
    )
    assert advice.reason == "dummy_provider"
    assert advice.recommended_action in legal_actions
