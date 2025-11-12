from __future__ import annotations

from pathlib import Path
from typing import Dict, Set
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from poker.engine import EngineConfig, TableEngine
from ws.protocol import ClientAction, Error, validate_action_against_legal
from poker.analysis.equity import compute_hand_strength, HandStrengthResult

APP_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = APP_ROOT / "public"

app = FastAPI(title="Poker Coach Alpha")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static client
if PUBLIC_DIR.exists():
    app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, table_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(table_id, set()).add(websocket)

    def disconnect(self, table_id: str, websocket: WebSocket):
        conns = self.active_connections.get(table_id)
        if conns and websocket in conns:
            conns.remove(websocket)

    async def broadcast(self, table_id: str, message: dict):
        for ws in list(self.active_connections.get(table_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                # Drop broken connections silently for now
                self.disconnect(table_id, ws)


manager = ConnectionManager()

# In-memory single table engine for MVP
DEFAULT_TABLE_ID = "default"
_engines: Dict[str, TableEngine] = {
    DEFAULT_TABLE_ID: TableEngine(EngineConfig(session_id=DEFAULT_TABLE_ID))
}


async def _broadcast_hand_strength(table_id: str, seat: int) -> None:
    """Compute hand strength asynchronously and broadcast an analysis update.

    Time-budgeted to ~100ms; if it times out or fails, send a degraded/null payload.
    """
    engine = _engines.get(table_id)
    if not engine or engine.state is None:
        return
    # Map seat -> current state index
    idx = engine._seat_to_state_index(seat)  # type: ignore[attr-defined]
    if idx is None:
        return
    # Compute with timeout and offload to a thread
    try:
        import anyio

        # Precompute live players for better fallback info
        try:
            statuses = list(getattr(engine.state, "statuses", []) or [])
            players = sum(1 for x in statuses if bool(x)) or 0
            if not players:
                stacks = list(getattr(engine.state, "stacks", []) or [])
                players = sum(1 for s in stacks if (s or 0) > 0)
        except Exception:
            players = 0

        with anyio.move_on_after(0.1) as scope:  # 100ms budget
            result: HandStrengthResult = await anyio.to_thread.run_sync(
                compute_hand_strength, engine.state, idx, 100
            )
        degraded = False
        if scope.cancel_called:  # timed out
            result = HandStrengthResult(
                hand_strength_pct=None,
                model="pokerkit.calculate_hand_strength",
                sample_count=100,
                players=players,
                degraded=True,
                reason="timeout",
            )
            degraded = True
        msg = {
            "type": "analysis",
            "seq": engine.next_sequence(),
            "to_act": seat,
            "hand_strength": {
                "hand_strength_pct": result.hand_strength_pct,
                "model": result.model,
                "sample_count": result.sample_count,
                "players": result.players,
                "degraded": result.degraded or degraded,
                "reason": result.reason,
            },
        }
        await manager.broadcast(table_id, msg)
    except Exception:
        try:
            await manager.broadcast(
                table_id,
                {
                    "type": "analysis",
                    "seq": engine.next_sequence(),
                    "to_act": seat,
                    "hand_strength": {
                        "hand_strength_pct": None,
                        "model": "pokerkit.calculate_hand_strength",
                        "sample_count": 100,
                        "players": players,
                        "degraded": True,
                        "reason": "error",
                    },
                },
            )
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = PUBLIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<h1>Poker Coach Alpha</h1><p>Server running. Add client at public/index.html</p>"
    )


@app.post("/tables")
def create_table():
    # MVP: single default table
    return {"table_id": DEFAULT_TABLE_ID}


@app.post("/tables/{table_id}/join")
def join_table(table_id: str):
    engine = _engines.get(table_id)
    if not engine:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    # MVP: fixed human seat 1
    return {"player_id": "human", "seat": 1}


@app.post("/tables/{table_id}/start")
def start_session(table_id: str):
    engine = _engines.get(table_id)
    if not engine:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    engine.start_session()
    # Advance until prompt or hand end and broadcast
    messages, _ = engine.advance(human_seat=1)
    for m in messages:
        # best-effort broadcast
        try:
            import anyio

            anyio.from_thread.run(manager.broadcast, table_id, m)
            # After broadcasting a prompt, compute hand strength asynchronously
            if isinstance(m, dict) and m.get("type") == "prompt":
                anyio.from_thread.run(_broadcast_hand_strength, table_id, m.get("to_act", 1))
        except Exception:
            pass
    return {"hand_id": f"h_{engine.hand_index:05d}"}


@app.post("/tables/{table_id}/next")
def next_hand(table_id: str):
    engine = _engines.get(table_id)
    if not engine or engine.state is None:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    ok, reason = engine.start_next_hand()
    if not ok:
        if reason:
            # If session ended or cannot proceed, notify caller
            return JSONResponse(status_code=400, content={"error": reason})
        return JSONResponse(status_code=400, content={"error": "cannot start next hand"})
    # Advance and broadcast
    messages, _ = engine.advance(human_seat=1)
    for m in messages:
        try:
            import anyio

            anyio.from_thread.run(manager.broadcast, table_id, m)
            if isinstance(m, dict) and m.get("type") == "prompt":
                anyio.from_thread.run(_broadcast_hand_strength, table_id, m.get("to_act", 1))
        except Exception:
            pass
    return {"hand_id": f"h_{engine.hand_index:05d}"}


@app.get("/tables/{table_id}/state")
def get_state(table_id: str):
    engine = _engines.get(table_id)
    if not engine or engine.state is None:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    snap = engine.build_table_snapshot()
    return {"type": "snapshot", "seq": 0, "table": snap}


@app.post("/tables/{table_id}/restart")
def restart_session(table_id: str):
    engine = _engines.get(table_id)
    if not engine:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    # Restart fresh session (keep same session_id)
    engine.restart_session()
    # Advance until prompt or hand end and broadcast
    messages, _ = engine.advance(human_seat=1)
    for m in messages:
        try:
            import anyio

            anyio.from_thread.run(manager.broadcast, table_id, m)
        except Exception:
            pass
    return {"hand_id": f"h_{engine.hand_index:05d}"}


@app.websocket("/ws/tables/{table_id}")
async def ws_table(websocket: WebSocket, table_id: str):
    await manager.connect(table_id, websocket)
    try:
        engine = _engines.get(table_id)
        if engine and engine.state is not None:
            await websocket.send_json(
                {"type": "snapshot", "seq": 0, "table": engine.build_table_snapshot()}
            )
            # If it's currently the human's turn, proactively compute hand strength
            try:
                idx = engine.state.turn_index  # state index
                if idx is not None:
                    seat_act = engine._state_index_to_seat(idx)
                    if seat_act == 1:
                        asyncio.create_task(_broadcast_hand_strength(table_id, seat_act))
            except Exception:
                pass
        # Main loop: receive client actions and advance engine
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "action":
                # Apply and advance
                engine = _engines.get(table_id)
                if not engine or engine.state is None:
                    error_msg = Error(message="table not ready")
                    await websocket.send_json(error_msg.model_dump())
                    continue

                # Validate and parse client action
                try:
                    client_action = ClientAction(**data)
                    action = client_action.action.model_dump(exclude_unset=True)

                    # Check action idempotency
                    if engine.bot_manager.is_action_processed(client_action.action_id):
                        continue  # Skip already processed action

                    # Validate against legal actions
                    legal_actions = engine.legal_actions()
                    if not validate_action_against_legal(client_action.action, legal_actions):
                        # Fallback: if it's a raise_to with amount and the engine accepts it, allow it
                        try:
                            if action.get("type") == "raise_to" and "amount" in action:
                                amt = int(action.get("amount"))
                                if engine._try_raise_to(amt):  # type: ignore[attr-defined]
                                    pass  # accept
                                else:
                                    error_msg = Error(message="illegal action")
                                    await websocket.send_json(error_msg.model_dump())
                                    continue
                            else:
                                error_msg = Error(message="illegal action")
                                await websocket.send_json(error_msg.model_dump())
                                continue
                        except Exception:
                            error_msg = Error(message="illegal action")
                            await websocket.send_json(error_msg.model_dump())
                            continue

                    # Mark action as processed for idempotency
                    engine.bot_manager.add_processed_action(client_action.action_id)

                except Exception as e:
                    error_msg = Error(message=f"invalid action format: {e}")
                    await websocket.send_json(error_msg.model_dump())
                    continue

                try:
                    engine.apply_action(action)
                except Exception as e:
                    import traceback as _tb

                    error_msg = Error(
                        message=f"apply_action failed: {e}", trace=_tb.format_exc(limit=10)
                    )
                    await websocket.send_json(error_msg.model_dump())
                    continue
                try:
                    msgs, _prompt = engine.advance(human_seat=1)
                except Exception as e:
                    import traceback as _tb

                    # Try to include a snapshot for context
                    try:
                        snap = engine.build_table_snapshot()
                    except Exception:
                        snap = None
                    error_msg = Error(
                        message=f"advance failed: {e}",
                        trace=_tb.format_exc(limit=20),
                        snapshot=snap,
                    )
                    await websocket.send_json(error_msg.model_dump())
                    continue
                for m in msgs:
                    await manager.broadcast(table_id, m)
                    if isinstance(m, dict) and m.get("type") == "prompt":
                        # Schedule async hand-strength compute without blocking UI
                        asyncio.create_task(_broadcast_hand_strength(table_id, m.get("to_act", 1)))
            else:
                await websocket.send_json({"type": "ack", "received": data})
    except WebSocketDisconnect:
        manager.disconnect(table_id, websocket)
    except Exception:
        manager.disconnect(table_id, websocket)
        return
