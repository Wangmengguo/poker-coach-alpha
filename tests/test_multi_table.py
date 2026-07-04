from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import (
    DEFAULT_TABLE_ID,
    _evict_idle_tables,
    _table_id_from_session,
    _table_last_activity,
    _engines,
    app,
)


def test_create_table_distinct_sessions() -> None:
    client = TestClient(app)
    r1 = client.post("/tables", json={"session_id": "session-alpha"})
    r2 = client.post("/tables", json={"session_id": "session-beta"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    t1 = r1.json()["table_id"]
    t2 = r2.json()["table_id"]
    assert t1 != t2
    assert t1 == _table_id_from_session("session-alpha")
    assert t2 == _table_id_from_session("session-beta")


def test_create_table_same_session_is_idempotent() -> None:
    client = TestClient(app)
    r1 = client.post("/tables", json={"session_id": "stable-session"})
    r2 = client.post("/tables", json={"session_id": "stable-session"})
    assert r1.json()["table_id"] == r2.json()["table_id"]


def test_create_table_without_session_uses_default() -> None:
    client = TestClient(app)
    res = client.post("/tables")
    assert res.status_code == 200
    assert res.json()["table_id"] == DEFAULT_TABLE_ID


def test_separate_tables_have_independent_sessions() -> None:
    client = TestClient(app)
    t1 = client.post("/tables", json={"session_id": "iso-a"}).json()["table_id"]
    t2 = client.post("/tables", json={"session_id": "iso-b"}).json()["table_id"]

    assert client.post(f"/tables/{t1}/start").status_code == 200
    assert client.post(f"/tables/{t2}/start").status_code == 200

    s1 = client.get(f"/tables/{t1}/state").json()
    s2 = client.get(f"/tables/{t2}/state").json()
    assert s1["table"] is not None
    assert s2["table"] is not None
    assert s1["table"]["table_id"] == t1
    assert s2["table"]["table_id"] == t2


def test_get_state_empty_engine_returns_null_table() -> None:
    client = TestClient(app)
    table_id = client.post("/tables", json={"session_id": "empty-state"}).json()["table_id"]
    res = client.get(f"/tables/{table_id}/state")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "snapshot"
    assert data["table"] is None


def test_evict_idle_tables_removes_stale_but_keeps_default(monkeypatch) -> None:
    client = TestClient(app)
    table_id = client.post("/tables", json={"session_id": "ttl-target"}).json()["table_id"]
    assert table_id in _engines
    _table_last_activity[table_id] = 0.0
    evicted = _evict_idle_tables(now=10_000.0)
    assert table_id in evicted
    assert table_id not in _engines
    assert DEFAULT_TABLE_ID in _engines


def test_table_limit_returns_503(monkeypatch) -> None:
    monkeypatch.setenv("TABLE_LIMIT", str(len(_engines)))
    client = TestClient(app)
    res = client.post("/tables", json={"session_id": "overflow-new-unique"})
    assert res.status_code == 503
    assert res.json()["error"] == "table_limit"


def test_websocket_ping_pong() -> None:
    client = TestClient(app)
    table_id = client.post("/tables", json={"session_id": "ws-ping"}).json()["table_id"]
    with client.websocket_connect(f"/ws/tables/{table_id}?player_id=human") as websocket:
        websocket.send_json({"type": "ping", "t": 123})
        data = websocket.receive_json()
        assert data == {"type": "pong", "t": 123}
