from poker.analysis.stats import (
    HumanStats,
    build_stats_payload,
    ensure_preflop_opportunity,
    new_session_stats,
    record_action_stats,
    reset_hand_flags,
)


def test_vpip_and_pfr_across_single_hand():
    stats: HumanStats = new_session_stats()
    reset_hand_flags(stats)

    # First preflop prompt for hero: count opportunity once
    ensure_preflop_opportunity(stats, street="preflop", is_hero=True)
    # Second call should be a no-op for the same hand
    ensure_preflop_opportunity(stats, street="preflop", is_hero=True)
    assert stats.vpip_opportunities == 1

    # Hero calls preflop once → VPIP voluntary increments, PFR stays 0
    record_action_stats(stats, street="preflop", is_hero=True, action_type="call")
    # A second voluntary action in the same hand should not double count VPIP
    record_action_stats(stats, street="preflop", is_hero=True, action_type="call")
    assert stats.vpip_voluntary == 1
    assert stats.pfr_raises == 0

    # New hand: reset per-hand flags but keep cumulative counts
    reset_hand_flags(stats)
    ensure_preflop_opportunity(stats, street="preflop", is_hero=True)
    assert stats.vpip_opportunities == 2

    # First preflop raise in this hand counts as both VPIP and PFR
    record_action_stats(stats, street="preflop", is_hero=True, action_type="raise_to")
    assert stats.vpip_voluntary == 2
    assert stats.pfr_raises == 1


def test_afq_only_counts_postflop_actions():
    stats: HumanStats = new_session_stats()

    # Preflop actions do not affect AFq totals
    record_action_stats(stats, street="preflop", is_hero=True, action_type="raise_to")
    record_action_stats(stats, street="preflop", is_hero=True, action_type="call")
    assert stats.afq_agg == 0
    assert stats.afq_total == 0

    # Postflop: raise_to counts as aggression and in total
    record_action_stats(stats, street="flop", is_hero=True, action_type="raise_to")
    # check/call only expand the denominator
    record_action_stats(stats, street="turn", is_hero=True, action_type="check")
    record_action_stats(stats, street="river", is_hero=True, action_type="call")

    assert stats.afq_agg == 1
    assert stats.afq_total == 3

    payload = build_stats_payload(stats)
    # AFq = 1 / 3 ≈ 33.3%
    assert payload["afq_agg"] == 1
    assert payload["afq_total"] == 3
    assert payload["afq_pct"] == 33.3


def test_build_stats_payload_percentages_consistent():
    stats: HumanStats = new_session_stats()
    # Simulate 10 hands with opportunities; hero VPIPs 4 times and raises 2 of those
    stats.vpip_opportunities = 10
    stats.vpip_voluntary = 4
    stats.pfr_raises = 2

    payload = build_stats_payload(stats)

    assert payload["vpip_voluntary"] == 4
    assert payload["vpip_opportunities"] == 10
    assert payload["vpip_pct"] == 40.0

    assert payload["pfr_raises"] == 2
    assert payload["pfr_opportunities"] == 10
    assert payload["pfr_pct"] == 20.0

    # Hands/sample size is exposed and used for style mapping
    assert payload["hands"] == 10
    # With 10 hands and VPIP=40%, AFq=0% → Loose-Passive under current thresholds
    assert payload["style"] == "Loose-Passive"


def test_style_mapping_loose_aggressive_with_enough_hands():
    stats: HumanStats = new_session_stats()
    # 40 hands with opportunity; 20 VPIP (50%) → Loose
    stats.vpip_opportunities = 40
    stats.vpip_voluntary = 20
    # PFR not relevant for style, but keep consistent
    stats.pfr_raises = 10
    # AFq: 24 aggressive actions out of 40 total → 60% → Aggressive
    stats.afq_agg = 24
    stats.afq_total = 40

    payload = build_stats_payload(stats)

    assert payload["hands"] == 40
    assert payload["style"] == "Loose-Aggressive"
