from __future__ import annotations

from typing import Dict

# Frequency-weighted shorthand range, e.g. {"AKs": 1.0, "AQo": 0.5}
Range = Dict[str, float]


def build_default_preflop_range(position: str, stack_bb: int) -> Range:
    """Conservative default preflop range (non-empty).

    - For short stacks (<=20bb): tight shove/call range.
    - For deeper stacks: a minimal value range; always returns at least {"AA": 1.0}.
    """
    if stack_bb <= 20:
        return {
            "AA": 1.0,
            "KK": 1.0,
            "QQ": 1.0,
            "JJ": 1.0,
            "TT": 1.0,
            "AKs": 1.0,
            "AKo": 1.0,
            "AQs": 0.8,
            "AJs": 0.7,
        }

    conservative = {"AA": 1.0, "KK": 1.0, "QQ": 1.0, "AKs": 1.0}
    if position in ("BTN", "CO"):
        conservative.update({"JJ": 1.0, "AQs": 1.0, "AJs": 0.8, "KQs": 0.8})
    elif position in ("SB", "BB"):
        conservative.update({"JJ": 1.0, "TT": 0.8, "AQs": 0.8, "AQo": 0.5})
    return conservative
