from __future__ import annotations

from pathlib import Path
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from poker.table import TableState

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

# In-memory single table stub for MVP scaffold
DEFAULT_TABLE_ID = "default"
_tables: Dict[str, TableState] = {DEFAULT_TABLE_ID: TableState.default()}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = PUBLIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Poker Coach Alpha</h1><p>Server running. Add client at public/index.html</p>")


@app.post("/tables")
def create_table():
    # MVP: single default table
    return {"table_id": DEFAULT_TABLE_ID}


@app.post("/tables/{table_id}/join")
def join_table(table_id: str):
    table = _tables.get(table_id)
    if not table:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    # MVP skeleton: assign human to seat 1 if free
    if table.human_player_id is None:
        table.human_player_id = "human"
        seat = 1
    else:
        seat = 1
    return {"player_id": table.human_player_id, "seat": seat}


@app.post("/tables/{table_id}/start")
def start_session(table_id: str):
    table = _tables.get(table_id)
    if not table:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    # TODO: hook into pokerkit engine and start hand loop
    table.session_active = True
    return {"hand_id": "h_00001"}


@app.get("/tables/{table_id}/state")
def get_state(table_id: str):
    table = _tables.get(table_id)
    if not table:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    return table.snapshot()


@app.websocket("/ws/tables/{table_id}")
async def ws_table(websocket: WebSocket, table_id: str):
    await manager.connect(table_id, websocket)
    try:
        # Send initial snapshot
        table = _tables.get(table_id) or TableState.default()
        await websocket.send_json({"type": "snapshot", "seq": table.seq, "table": table.snapshot()["table"]})
        # Echo loop (placeholder until engine + bots are wired)
        while True:
            data = await websocket.receive_json()
            # For now, just acknowledge any action message
            await websocket.send_json({"type": "ack", "received": data})
    except WebSocketDisconnect:
        manager.disconnect(table_id, websocket)
    except Exception:
        manager.disconnect(table_id, websocket)
        # Don't crash the server on WS errors in scaffold
        return
