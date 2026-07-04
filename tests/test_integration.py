from fastapi.testclient import TestClient

from app.main import app
from poker.engine import EngineConfig, TableEngine
from ws.protocol import LegalAction


class TestPokerIntegration:
    """Integration tests for poker game flow."""

    def test_engine_basic_flow(self):
        """Test basic engine functionality without WebSocket."""
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

        # Should have legal actions initially
        legal_actions = engine.legal_actions()
        assert len(legal_actions) > 0

    def test_bot_manager_functionality(self):
        """Test bot manager with different bot types."""
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

    def test_deterministic_rng(self):
        """Test that RNG is deterministic for same session."""
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

    def test_action_validation(self):
        """Test action validation against legal actions."""
        from ws.protocol import validate_action_against_legal

        legal_actions = [
            LegalAction(type="check"),
            LegalAction(type="call", amount=10),
            LegalAction(type="raise_to", amount=20),
        ]

        # Valid actions
        assert validate_action_against_legal(LegalAction(type="check"), legal_actions)
        assert validate_action_against_legal(LegalAction(type="call", amount=10), legal_actions)
        assert validate_action_against_legal(LegalAction(type="raise_to", amount=20), legal_actions)

        # Invalid actions
        assert not validate_action_against_legal(LegalAction(type="fold"), legal_actions)
        assert not validate_action_against_legal(LegalAction(type="call", amount=5), legal_actions)
        assert not validate_action_against_legal(
            LegalAction(type="raise_to", amount=15), legal_actions
        )

    def test_message_schemas(self):
        """Test that message schemas work correctly."""
        from ws.protocol import Error, Snapshot

        # Test Snapshot
        snapshot_data = {
            "type": "snapshot",
            "seq": 1,
            "table": {
                "table_id": "test",
                "hand_id": "h_001",
                "button_seat": 1,
                "blinds": {"sb": 1, "bb": 2},
                "players": [],
                "street": "preflop",
                "board": [],
                "pot": 0,
                "bets": {},
                "to_act": 1,
                "legal_actions": [],
            },
        }
        snapshot = Snapshot(**snapshot_data)
        assert snapshot.type == "snapshot"
        assert snapshot.seq == 1

        # Test Error message
        error = Error(message="test error", trace="test trace")
        assert error.type == "error"
        assert error.message == "test error"

    def test_rest_endpoints(self):
        """Test REST API endpoints."""
        client = TestClient(app)

        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200

        # Test create table
        response = client.post("/tables")
        assert response.status_code == 200
        data = response.json()
        assert "table_id" in data

        # Test join table
        response = client.post("/tables/default/join")
        assert response.status_code == 200
        data = response.json()
        assert data["player_id"] == "human"
        assert data["seat"] == 1

        # Test start session
        response = client.post("/tables/default/start")
        assert response.status_code == 200
        data = response.json()
        assert "hand_id" in data

        # Test get state
        response = client.get("/tables/default/state")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "snapshot"
        assert "table" in data

    def test_websocket_basic_connection(self):
        """Test basic WebSocket connection and message handling."""
        client = TestClient(app)

        # Start a session first
        client.post("/tables")
        client.post("/tables/default/join")
        client.post("/tables/default/start")

        with client.websocket_connect("/ws/tables/default?player_id=human") as websocket:
            # Should receive initial snapshot
            data = websocket.receive_json()
            assert data["type"] == "snapshot"
            assert "table" in data

            # The table should have players
            table = data["table"]
            assert len(table["players"]) == 6
            assert table["players"][0]["id"] == "human"

    def test_websocket_receives_messages_when_session_started_after_connect(self):
        """WebSocket should receive snapshot/prompt if session starts after client connects.

        This mirrors the real frontend flow:
        - WebSocket connects on page load
        - REST /tables + /join + /start are called afterwards via the UI
        """
        client = TestClient(app)
        table_id = client.post("/tables", json={"session_id": "ws-flow-after-connect"}).json()[
            "table_id"
        ]

        # Connect WS first (as the browser does)
        with client.websocket_connect(f"/ws/tables/{table_id}?player_id=human") as websocket:
            start_res = client.post(f"/tables/{table_id}/start")
            assert start_res.status_code == 200

            # After starting the session, the WS should receive at least one message.
            # First should be a snapshot of the table.
            data = websocket.receive_json()
            assert data["type"] == "snapshot"
            assert "table" in data

            table = data["table"]
            assert len(table["players"]) == 6
            assert table["players"][0]["id"] == "human"

    def test_session_termination_conditions(self):
        """Test that session ends under correct conditions."""
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


if __name__ == "__main__":
    # Run a simple test to verify everything works
    test = TestPokerIntegration()
    test.test_engine_basic_flow()
    test.test_bot_manager_functionality()
    test.test_deterministic_rng()
    test.test_action_validation()
    test.test_message_schemas()
    test.test_rest_endpoints()
    print("✅ All integration tests passed!")
