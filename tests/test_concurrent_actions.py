"""Tests for per-table lock and concurrent action handling.

Verifies that:
1. Lock is properly created and used
2. Sequential operations work correctly with locks
3. State remains consistent

Note: TestClient is sync-only; for true concurrency we use httpx.AsyncClient
with ASGITransport and asyncio.gather.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
import httpx

from app.main import app, _engines, _table_locks, DEFAULT_TABLE_ID, _get_table_lock
from poker.engine import EngineConfig, TableEngine


class TestPerTableLock:
    """Test suite for per-table lock functionality."""

    def _reset_table(self):
        """Reset table state."""
        _engines[DEFAULT_TABLE_ID] = TableEngine(EngineConfig(session_id=DEFAULT_TABLE_ID))
        _table_locks.clear()

    def test_lock_creation(self):
        """Verify lock is created on first access."""
        self._reset_table()
        assert DEFAULT_TABLE_ID not in _table_locks

        lock = _get_table_lock(DEFAULT_TABLE_ID)
        assert lock is not None
        assert isinstance(lock, asyncio.Lock)
        assert DEFAULT_TABLE_ID in _table_locks

    def test_lock_reuse(self):
        """Verify same lock is returned for same table_id."""
        self._reset_table()

        lock1 = _get_table_lock(DEFAULT_TABLE_ID)
        lock2 = _get_table_lock(DEFAULT_TABLE_ID)
        assert lock1 is lock2

    def test_different_tables_different_locks(self):
        """Verify different tables get different locks."""
        self._reset_table()

        lock1 = _get_table_lock("table1")
        lock2 = _get_table_lock("table2")
        assert lock1 is not lock2

    def test_start_creates_lock(self):
        """Verify lock is created when starting a session."""
        self._reset_table()

        with TestClient(app) as client:
            # Before start, lock may or may not exist
            client.post("/tables/default/start")

        # After start, lock should exist
        assert DEFAULT_TABLE_ID in _table_locks
        assert isinstance(_table_locks[DEFAULT_TABLE_ID], asyncio.Lock)

    def test_sequential_start_restart(self):
        """Verify sequential start/restart operations work correctly."""
        self._reset_table()

        with TestClient(app) as client:
            # Start
            r1 = client.post("/tables/default/start")
            assert r1.status_code == 200

            # Second start should fail
            r2 = client.post("/tables/default/start")
            assert r2.status_code == 400
            assert r2.json().get("error") == "session already active"

            # Restart should succeed
            r3 = client.post("/tables/default/restart")
            assert r3.status_code == 200

            # Start should still fail (restart keeps session active)
            r4 = client.post("/tables/default/start")
            assert r4.status_code == 400

    def test_state_readable_after_operations(self):
        """Verify state is readable after locked operations."""
        self._reset_table()

        with TestClient(app) as client:
            client.post("/tables/default/start")

            # State should be readable
            state = client.get("/tables/default/state")
            assert state.status_code == 200
            data = state.json()
            assert "table" in data
            assert "players" in data["table"]
            assert len(data["table"]["players"]) == 6

    def test_restart_after_start(self):
        """Verify restart works after start."""
        self._reset_table()

        with TestClient(app) as client:
            client.post("/tables/default/start")

            # Multiple restarts should work
            for _ in range(3):
                r = client.post("/tables/default/restart")
                assert r.status_code == 200

            # State should still be valid
            state = client.get("/tables/default/state")
            assert state.status_code == 200

    def test_next_returns_valid_response(self):
        """Verify next returns a valid response (200 if hand ended, 400 if still active)."""
        self._reset_table()

        with TestClient(app) as client:
            client.post("/tables/default/start")

            # Next should return either 200 (hand ended) or 400 (hand active)
            # depending on game state after bot actions
            r = client.post("/tables/default/next")
            assert r.status_code in (200, 400)

            if r.status_code == 400:
                # Error should indicate why
                error = r.json().get("error")
                assert error is not None

    def test_seq_increments(self):
        """Verify sequence numbers increment properly."""
        self._reset_table()

        with TestClient(app) as client:
            client.post("/tables/default/start")

            # Get engine and verify seq
            engine = _engines.get(DEFAULT_TABLE_ID)
            assert engine is not None

            seq1 = engine.next_sequence()
            seq2 = engine.next_sequence()
            seq3 = engine.next_sequence()

            assert seq2 == seq1 + 1
            assert seq3 == seq2 + 1

    def test_concurrent_start_serialized(self):
        """Two concurrent /start calls should not both succeed."""

        async def _run() -> None:
            self._reset_table()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                r1, r2 = await asyncio.gather(
                    client.post("/tables/default/start"),
                    client.post("/tables/default/start"),
                )

            codes = sorted([r1.status_code, r2.status_code])
            assert codes == [200, 400]

            bad = r1 if r1.status_code == 400 else r2
            assert bad.json().get("error") == "session already active"

        asyncio.run(_run())

    def test_concurrent_restart_does_not_crash(self):
        """Concurrent /restart calls should be safe and return 200."""

        async def _run() -> None:
            self._reset_table()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                r1, r2 = await asyncio.gather(
                    client.post("/tables/default/restart"),
                    client.post("/tables/default/restart"),
                )

            assert r1.status_code == 200
            assert r2.status_code == 200

        asyncio.run(_run())


class TestActionIdempotency:
    """Test that duplicate action_ids are handled correctly."""

    def _reset_table(self):
        """Reset table state."""
        _engines[DEFAULT_TABLE_ID] = TableEngine(EngineConfig(session_id=DEFAULT_TABLE_ID))
        _table_locks.clear()

    def test_action_id_tracking(self):
        """Verify action_id tracking works."""
        self._reset_table()

        engine = _engines.get(DEFAULT_TABLE_ID)
        assert engine is not None

        action_id = "test-action-001"

        # Should not be processed initially
        assert not engine.bot_manager.is_action_processed(action_id)

        # Mark as processed
        engine.bot_manager.add_processed_action(action_id)

        # Should now be processed
        assert engine.bot_manager.is_action_processed(action_id)

        # Different action_id should not be affected
        assert not engine.bot_manager.is_action_processed("different-action")
