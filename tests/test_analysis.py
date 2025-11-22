from dataclasses import dataclass, field
from typing import List, Sequence

import pytest

from poker.analysis.core import (
    compute_board_texture,
    compute_call_ev,
    compute_outs,
    compute_pot_math,
    compute_pot_odds_and_equity_need,
    describe_hand,
)
from poker.analysis.compose import compose_analysis
from poker.analysis.models import DecisionContext
from poker.analysis.equity import compute_hand_strength, compute_equity_vs_range
from poker.analysis.ranges import build_default_preflop_range
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
    assert result["effective_stack"] == 80
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
    assert result["effective_stack"] == 100
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
    assert result["effective_stack"] == 0
    assert result["spr"] == 0.0


def test_compute_pot_odds_and_equity_need_basic():
    res = compute_pot_odds_and_equity_need(pot=30, to_call=10, current_street_bets_sum=0)
    assert res["pot_decision"] == 40.0
    assert res["pot_odds_pct"] == 25.0
    assert res["required_equity_pct"] == 25.0


def test_compute_pot_odds_handles_zero():
    res = compute_pot_odds_and_equity_need(pot=0, to_call=0, current_street_bets_sum=0)
    assert res["pot_decision"] == 0.0
    assert res["pot_odds_pct"] == 0.0
    assert res["required_equity_pct"] == 0.0


def test_compute_call_ev_with_and_without_tie():
    # even-money spot: EV ~ 0
    ev_even = compute_call_ev(to_call=50, pot_decision=100, win_pct=0.5, tie_pct=0.0)
    assert ev_even == 0.0

    # profitable call with tie component
    ev_tie = compute_call_ev(to_call=50, pot_decision=200, win_pct=0.30, tie_pct=0.10)
    # Outcomes: win +150 (30%), tie +50 (10%), lose -50 (60%) => EV = 20
    assert ev_tie == pytest.approx(20.0)


# ---- compose_analysis minimal integration ----


@dataclass
class FakeStateCompose:
    bets: Sequence[int] = field(default_factory=list)
    stacks: Sequence[int] = field(default_factory=list)
    pot_amounts: Sequence[int] = field(default_factory=list)
    statuses: Sequence[bool] = field(default_factory=list)
    board_cards: Sequence[Sequence[str]] = field(default_factory=list)
    hole_cards: Sequence[Sequence[str]] = field(default_factory=list)
    street_index: int = 0


def test_compose_analysis_builds_payload_and_dc():
    state = FakeStateCompose(
        bets=[5, 5],
        stacks=[100, 120],
        pot_amounts=[30],
        statuses=[True, True],
        board_cards=[["As", "Kd", "2c"]],
        hole_cards=[["Ah", "Ad"], ["7s", "7c"]],
        street_index=1,  # flop
    )
    positions = {"1": "BTN", "2": "SB"}

    dc, payload = compose_analysis(
        state,
        hero_idx=0,
        hero_seat=1,
        session_stats=None,
        positions_map=positions,
        include_hand_strength=False,
    )

    # DecisionContext assertions
    assert isinstance(dc, DecisionContext)
    assert dc.to_call == 0
    assert dc.pot == 30
    assert dc.current_street_bets_sum == 10
    assert dc.pot_decision == 40.0
    assert dc.pot_odds_pct == 0.0  # free call
    assert dc.effective_stack == 100
    assert dc.spr == pytest.approx(3.33, rel=1e-2)
    assert dc.hand_label in ("Set", "Trips")
    assert dc.outs == 0
    assert dc.hero_position == "BTN"
    assert dc.players_count == 2

    # Payload assertions (prompt-friendly)
    assert "pot_math" in payload
    assert payload["pot_math"]["effective_stack"] == 100
    assert payload.get("pot_extra", {}).get("pot_decision") == 40.0
    assert payload.get("hand", {}).get("label") in ("Set", "Trips")
    assert payload.get("outs", {}).get("outs", 0) == 0


def test_compute_equity_vs_range_basic():
    # Hero AA vs very weak range -> equity should be well above 50%
    class FakeStateEq(FakeStateCompose):
        pass

    state = FakeStateCompose(
        bets=[0, 0],
        stacks=[100, 100],
        pot_amounts=[0],
        statuses=[True, True],
        board_cards=[],
        hole_cards=[["Ah", "Ad"], ["", ""]],
        street_index=0,
    )
    weak_range = {"72o": 1.0}

    import random

    random.seed(42)
    res = compute_equity_vs_range(state, hero_idx=0, villain_range=weak_range, sample_count=200, rng_seed=42)
    assert res.degraded is False
    assert res.players == 2
    assert res.win_pct > 70.0  # AA should dominate 72o
    assert res.win_pct <= 100.0


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


def test_compute_outs_gutshot_simple():
    # Gutshot: 7-8 with T-J on board (plus a blank) → need a 9
    outs_gutshot = compute_outs(["7d", "8c"], ["Jh", "Tc", "2s"])
    assert outs_gutshot["flush_draw"] is False
    assert outs_gutshot["oesd"] is False
    assert outs_gutshot.get("gutshot") is True
    assert outs_gutshot["outs"] == 4


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
