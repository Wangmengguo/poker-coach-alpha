from dataclasses import dataclass, field
from typing import List, Sequence

from poker.analysis.core import compute_pot_math


@dataclass
class FakeState:
    bets: Sequence[int] = field(default_factory=list)
    stacks: Sequence[int] = field(default_factory=list)
    pot_amounts: Sequence[int] = field(default_factory=list)
    statuses: Sequence[bool] = field(default_factory=list)


def test_compute_pot_math_basic_two_player():
    state = FakeState(
        bets=[2, 5],
        stacks=[100, 80],
        pot_amounts=[10, 20],
        statuses=[True, True],
    )

    # Hero is index 0 in state.bets/stacks/statuses
    result = compute_pot_math(state, hero_idx=0)

    assert result["to_call"] == 3  # 5 - 2
    assert result["pot"] == 30
    # effective_stack = min(100, 80) = 80; SPR = 80 / 30 ≈ 2.67
    assert result["spr"] == 2.67


def test_compute_pot_math_no_bets_no_pot():
    state = FakeState(
        bets=[],
        stacks=[100, 100],
        pot_amounts=[],
        statuses=[True, True],
    )

    result = compute_pot_math(state, hero_idx=0)

    assert result["to_call"] == 0
    assert result["pot"] == 0
    # Base pot is zero; by definition we divide by max(1, pot),
    # so SPR falls back to effective_stack / 1.
    assert result["spr"] == 100.0


def test_compute_pot_math_ignores_busted_opponents():
    # Opponent has stack but is marked not alive in statuses
    state = FakeState(
        bets=[2, 2],
        stacks=[100, 200],
        pot_amounts=[40],
        statuses=[True, False],
    )

    result = compute_pot_math(state, hero_idx=0)

    # No live opponent with stack → effective_stack = 0 → SPR = 0
    assert result["to_call"] == 0
    assert result["pot"] == 40
    assert result["spr"] == 0.0
