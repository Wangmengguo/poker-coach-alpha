from poker.engine import EngineConfig, TableEngine


def test_blinds_posted_in_initial_snapshot():
    cfg = EngineConfig()  # defaults sb=1, bb=2
    eng = TableEngine(cfg)

    # Start a session and advance to the first human prompt (preflop)
    eng.start_session()
    messages, _ = eng.advance(human_seat=1)

    # Find the last snapshot emitted
    snapshots = [m for m in messages if m.get("type") == "snapshot"]
    assert snapshots, "No snapshots emitted after starting session"
    table = snapshots[-1]["table"]

    # Bets should reflect posted blinds for SB and BB seats
    bets = table.get("bets", {})
    positions = table.get("positions", {})

    # Identify SB and BB seats from positions map
    sb_seat = None
    bb_seat = None
    for seat_str, pos in positions.items():
        if pos == "SB":
            sb_seat = int(seat_str)
        elif pos == "BB":
            bb_seat = int(seat_str)

    assert sb_seat is not None and bb_seat is not None, "Positions map missing SB/BB"

    assert bets.get(str(sb_seat), 0) == cfg.sb, f"SB seat {sb_seat} should post {cfg.sb}"
    assert bets.get(str(bb_seat), 0) == cfg.bb, f"BB seat {bb_seat} should post {cfg.bb}"
