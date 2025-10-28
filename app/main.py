from __future__ import annotations

from pathlib import Path
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from poker.engine import EngineConfig, TableEngine
from ws.protocol import ClientAction, Error, validate_action_against_legal

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
            # If session ended, notify caller
            return JSONResponse(status_code=400, content={"error": reason})
        return JSONResponse(status_code=400, content={"error": "cannot start next hand"})
    # Advance and broadcast
    messages, _ = engine.advance(human_seat=1)
    for m in messages:
        try:
            import anyio

            anyio.from_thread.run(manager.broadcast, table_id, m)
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


@app.websocket("/ws/tables/{table_id}")
async def ws_table(websocket: WebSocket, table_id: str):
    await manager.connect(table_id, websocket)
    try:
        engine = _engines.get(table_id)
        if engine and engine.state is not None:
            await websocket.send_json(
                {"type": "snapshot", "seq": 0, "table": engine.build_table_snapshot()}
            )
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
            else:
                await websocket.send_json({"type": "ack", "received": data})
    except WebSocketDisconnect:
        manager.disconnect(table_id, websocket)
    except Exception:
        manager.disconnect(table_id, websocket)
        return
