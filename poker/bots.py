from __future__ import annotations

import random
from typing import Dict, List


class SimpleBot:
    """Very naive bot that respects provided legal_actions.

    Note: This is a placeholder. Real implementation will consult pokerkit state.
    """

    def choose(self, legal_actions: List[Dict]) -> Dict:
        if not legal_actions:
            return {"type": "check"}
        # Prefer call over fold if available; else random legal action
        calls = [a for a in legal_actions if a.get("type") == "call"]
        if calls:
            return calls[0]
        return random.choice(legal_actions)
