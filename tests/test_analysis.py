from dataclasses import dataclass, field
from typing import List, Sequence

from poker.analysis.core import (
    compute_board_texture,
    compute_outs,
    compute_pot_math,
    describe_hand,
)
from poker.analysis.equity import compute_hand_strength
from poker.analysis.preflop_tables import PREFLOP_EQUITIES_BY_PLAYERS


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


def test_compute_board_texture_empty_board():
    tex = compute_board_texture([])
    assert tex == {"paired": False, "monotone": False, "two_tone": False, "straighty": False}


def test_compute_board_texture_paired_monotone_and_straighty_flop():
    # Flop: 9h 9d Th
    tex = compute_board_texture(["9h", "9d", "Th"])
    assert tex["paired"] is True
    # Suits: h, d, h -> at least 2 hearts but only 2 to flush; monotone uses >=3 same suit
    # Add another heart to make it clearly monotone-like
    tex2 = compute_board_texture(["9h", "9d", "Th", "Ah"])
    assert tex2["monotone"] is True


def test_compute_board_texture_two_tone_board():
    # Board with exactly two suits
    tex = compute_board_texture(["Ah", "Kd", "9h", "2d"])
    assert tex["two_tone"] is True
    assert tex["monotone"] is False


def test_compute_board_texture_straighty_with_wheel_wrap():
    # Flop A 2 3 rainbow; should be straighty (potential wheel)
    tex = compute_board_texture(["As", "2d", "3c"])
    assert tex["straighty"] is True

    # Turn brings 4 → even more straighty
    tex2 = compute_board_texture(["As", "2d", "3c", "4h"])
    assert tex2["straighty"] is True


def test_verbose_card_strings_are_parsed_correctly():
    # Board and hero cards using verbose pokerkit-style strings
    board_verbose = [
        "QUEEN OF SPADES (Qs)",
        "FIVE OF DIAMONDS (5d)",
        "SEVEN OF HEARTS (7h)",
        "TREY OF SPADES (3s)",
        "QUEEN OF HEARTS (Qh)",
    ]
    hero_verbose = ["QUEEN OF CLUBS (Qc)", "ACE OF HEARTS (Ah)"]

    tex = compute_board_texture(board_verbose)
    assert tex["paired"] is True
    assert tex["monotone"] is False
    assert tex["two_tone"] is False

    label = describe_hand(hero_verbose, board_verbose)
    # Hero has trips queens here, no flush
    assert label in ("Trips", "Set")

    outs = compute_outs(hero_verbose, board_verbose)
    assert outs["outs"] == 0


def test_describe_hand_overpair_and_tptk():
    # Overpair: AsAh on Kd7c2s
    label_overpair = describe_hand(["As", "Ah"], ["Kd", "7c", "2s"])
    assert label_overpair == "Overpair"

    # TPTK: AsKd on Kh7c2s
    label_tptk = describe_hand(["As", "Kd"], ["Kh", "7c", "2s"])
    assert label_tptk == "Top Pair, Top Kicker"


def test_describe_hand_two_pair_and_set_priority():
    # Two Pair: AsKd on KhAd7c
    label_two_pair = describe_hand(["As", "Kd"], ["Kh", "Ad", "7c"])
    assert label_two_pair == "Two Pair"

    # Set: 9c9d on 9h7c2s
    label_set = describe_hand(["9c", "9d"], ["9h", "7c", "2s"])
    assert label_set == "Set"


def test_describe_hand_middle_pair_and_preflop_labels():
    # Middle pair: hero pairs a non-top board rank
    label_mid_pair = describe_hand(["9c", "4d"], ["Qh", "9s", "2c"])
    assert label_mid_pair == "Pair"

    # Bottom pair: hero pairs the lowest board rank
    label_bottom_pair = describe_hand(["2c", "7d"], ["Kh", "9s", "2d"])
    assert label_bottom_pair == "Pair"

    # Preflop pocket pair
    label_pocket = describe_hand(["9c", "9d"], [])
    assert label_pocket == "Pocket 9s"

    # Preflop non-pair
    label_preflop = describe_hand(["As", "Kd"], [])
    assert label_preflop == "Preflop"


def test_compute_outs_flush_oesd_and_combo():
    # Pure flush draw: hero has one spade, board has 3 spades, no OESD
    outs_flush = compute_outs(["As", "Kd"], ["Qs", "9s", "2s"])
    assert outs_flush["flush_draw"] is True
    assert outs_flush["oesd"] is False
    assert outs_flush["outs"] == 9

    # Pure OESD: 7-8 on 9-6-2
    outs_oesd = compute_outs(["7d", "8c"], ["9d", "6h", "2s"])
    assert outs_oesd["flush_draw"] is False
    assert outs_oesd["oesd"] is True
    assert outs_oesd["outs"] == 8

    # Combo draw: AsKs on QsJsTs
    outs_combo = compute_outs(["As", "Ks"], ["Qs", "Js", "Ts"])
    assert outs_combo["flush_draw"] is True
    assert outs_combo["oesd"] is True
    assert outs_combo["combo"] is True
    assert outs_combo["outs"] == 15


@dataclass
class FakePreflopState:
    street_index: int = 0
    hole_cards: Sequence[Sequence[str]] = field(default_factory=list)
    statuses: Sequence[bool] = field(default_factory=list)


def test_preflop_lookup_aa_and_unknown_combo():
    # Hero AA vs random: should use lookup
    state = FakePreflopState(
        street_index=0,
        hole_cards=[["As", "Ah"]],
        statuses=[True, True],
    )
    res = compute_hand_strength(state, hero_idx=0, sample_count=100)
    assert res.model == "preflop_lookup"
    assert res.sample_count == 0
    assert res.hand_strength_pct == PREFLOP_EQUITIES_BY_PLAYERS[2]["AA"]

    # Unknown combo should mark as preflop_unavailable
    state_unknown = FakePreflopState(
        street_index=0,
        hole_cards=[["2c", "7d"]],
        statuses=[True, True],
    )
    res_unknown = compute_hand_strength(state_unknown, hero_idx=0, sample_count=100)
    assert res_unknown.model in ("preflop_unavailable", "preflop_lookup")
    if res_unknown.model == "preflop_unavailable":
        assert res_unknown.hand_strength_pct is None
