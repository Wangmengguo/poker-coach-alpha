from __future__ import annotations

import random
from typing import Dict, List


class SimpleBot:
    """Very naive bot that respects provided legal_actions.

    Preference: check > call > min raise_to > fold > anything.
    """

    def choose(self, legal_actions: List[Dict]) -> Dict:
        if not legal_actions:
            return {"type": "check"}
        for t in ("check", "call"):
            for a in legal_actions:
                if a.get("type") == t:
                    return a
        # pick smallest raise_to if any
        raises = [a for a in legal_actions if a.get("type") == "raise_to"]
        if raises:
            raises.sort(key=lambda a: a.get("amount", 0))
            return raises[0]
        # else fold if available
        for a in legal_actions:
            if a.get("type") == "fold":
                return a
        return random.choice(legal_actions)
