from __future__ import annotations

from typing import Dict, List

from poker.bots import EquityBot


def _make_actions() -> List[Dict]:
    return [
        {"type": "call", "amount": 10},
        {"type": "fold"},
    ]


def test_equity_bot_fallback_on_invalid_state():
    """EquityBot should fall back cleanly when state is unusable."""
    bot = EquityBot(hand_strength_samples=1, seed=123)
    legal_actions = _make_actions()
    action = bot.choose(state=None, hero_idx=0, hero_seat=2, legal_actions=legal_actions)
    assert action in legal_actions

