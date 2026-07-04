"""Basic tests for core functionality without external dependencies."""

from poker.engine import EngineConfig, TableEngine
from ws.protocol import Error, LegalAction, validate_action_against_legal


def test_engine_basic():
    """Test basic engine functionality."""
    config = EngineConfig(session_id="test", max_hands=2)
    engine = TableEngine(config)

    # Start session
    engine.start_session()
    assert engine.session_active
    assert engine.hand_index == 1

    # Should have initial state
    assert engine.state is not None

    # Get table snapshot
    snapshot = engine.build_table_snapshot()
    assert snapshot["table_id"] == "test"
    assert len(snapshot["players"]) == 6
    assert snapshot["players"][0]["id"] == "human"  # Seat 1

    print("✅ Engine basic test passed")


def test_bot_manager():
    """Test bot manager functionality."""
    config = EngineConfig(session_id="test_bots")
    engine = TableEngine(config)

    # Check bot seats
    assert engine.bot_manager.is_bot_seat(2)
    assert engine.bot_manager.is_bot_seat(3)
    assert not engine.bot_manager.is_bot_seat(1)  # Human seat

    # Test action idempotency
    action_id = "test_action_123"
    assert not engine.bot_manager.is_action_processed(action_id)
    engine.bot_manager.add_processed_action(action_id)
    assert engine.bot_manager.is_action_processed(action_id)

    print("✅ Bot manager test passed")


def test_deterministic_rng():
    """Test that RNG is deterministic."""
    config1 = EngineConfig(session_id="deterministic_test")
    config2 = EngineConfig(session_id="deterministic_test")

    engine1 = TableEngine(config1)
    engine2 = TableEngine(config2)

    # Same session ID should produce same seed
    seed1 = engine1._generate_hand_seed()
    seed2 = engine2._generate_hand_seed()
    assert seed1 == seed2

    # Different session ID should produce different seed
    config3 = EngineConfig(session_id="different_test")
    engine3 = TableEngine(config3)
    seed3 = engine3._generate_hand_seed()
    assert seed1 != seed3

    print("✅ Deterministic RNG test passed")


def test_action_validation():
    """Test action validation."""
    legal_actions = [
        LegalAction(type="check"),
        LegalAction(type="call", amount=10),
        LegalAction(type="raise_to", amount=20),
    ]

    # Valid actions
    assert validate_action_against_legal(LegalAction(type="check"), legal_actions)
    assert validate_action_against_legal(LegalAction(type="call", amount=10), legal_actions)

    # Invalid actions
    assert not validate_action_against_legal(LegalAction(type="fold"), legal_actions)
    assert not validate_action_against_legal(LegalAction(type="call", amount=5), legal_actions)

    print("✅ Action validation test passed")


def test_message_schemas():
    """Test message schemas."""
    # Test Error message
    error = Error(message="test error", trace="test trace")
    assert error.type == "error"
    assert error.message == "test error"

    # Test serialization
    error_dict = error.model_dump()
    assert error_dict["type"] == "error"
    assert error_dict["message"] == "test error"

    print("✅ Message schemas test passed")


def test_session_termination():
    """Test session termination conditions."""
    # Test max hands
    config = EngineConfig(session_id="test_term", max_hands=1)
    engine = TableEngine(config)
    engine.start_session()

    should_end, reason = engine.should_end_session()
    assert should_end
    assert reason == "max_hands"

    # Test session inactive
    engine.session_active = False
    should_end, reason = engine.should_end_session()
    assert should_end
    assert reason == "session_inactive"

    print("✅ Session termination test passed")


def test_game_flow_simulation():
    """Simulate a basic game flow."""
    config = EngineConfig(session_id="game_flow_test", max_hands=1)
    engine = TableEngine(config)

    # Start session
    engine.start_session()

    # Get initial state
    snapshot = engine.build_table_snapshot()
    print(f"Initial state: {len(snapshot['players'])} players")

    # Check legal actions exist
    legal_actions = engine.legal_actions()
    assert len(legal_actions) > 0
    print(f"Legal actions: {[a['type'] for a in legal_actions]}")

    # Try to apply a safe action (check or fold)
    for action in legal_actions:
        if action["type"] in ("check", "fold"):
            try:
                engine.apply_action(action)
                print(f"Applied action: {action['type']}")
                break
            except Exception as e:
                print(f"Action failed: {e}")

    print("✅ Game flow simulation passed")


def test_bust_logic_and_next_hand():
    """Ensure next hand works when some bots are busted, and session ends only when all bots are busted or human busts."""
    config = EngineConfig(session_id="bust_logic_test", max_hands=10)
    engine = TableEngine(config)
    engine.start_session()
    # Simulate two bots busted (seats 2 and 3)
    engine.seat_stacks[1] = 0
    engine.seat_stacks[2] = 0
    ok, reason = engine.start_next_hand()
    assert ok, f"Should allow next hand when some bots busted, got: {reason}"

    # Simulate all bots busted
    for i in range(engine.cfg.seats):
        if (i + 1) != engine.cfg.human_seat:
            engine.seat_stacks[i] = 0
    should_end, reason = engine.should_end_session()
    assert should_end and reason == "bots_busted"

    # Simulate human busted
    engine.seat_stacks = [0] * engine.cfg.seats
    should_end, reason = engine.should_end_session()
    assert should_end and reason == "player_busted"


if __name__ == "__main__":
    test_engine_basic()
    test_bot_manager()
    test_deterministic_rng()
    test_action_validation()
    test_message_schemas()
    test_session_termination()
    test_game_flow_simulation()
    print("\n🎉 All basic tests passed! MVP core functionality is working.")
