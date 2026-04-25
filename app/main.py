from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Set
import asyncio
from dataclasses import dataclass
import os

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from poker.engine import EngineConfig, TableEngine
from ws.protocol import ClientAction, Error, validate_action_against_legal
from poker.analysis.equity import compute_hand_strength, HandStrengthResult
from poker.analysis.compose import compose_analysis
from poker.ai_coach import (
    generate_ai_advice,
    get_allowed_model_tiers,
    get_ai_provider_from_env,
    get_allowed_model_aliases,
    get_current_model_alias,
    set_current_model_alias,
    select_actions_heuristic,
    DummyProvider,
    use_model_alias,
)
from poker.invite_codes import InviteCodeStore
from poker.llm_config import (
    list_gateway_models,
    public_config,
    resolve_model_id,
    save_llm_config,
    test_gateway_model,
)

APP_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = APP_ROOT / "public"
APP_PREFIX = os.getenv("APP_PREFIX", "/cards").strip() or "/cards"
if not APP_PREFIX.startswith("/"):
    APP_PREFIX = "/" + APP_PREFIX
APP_PREFIX = APP_PREFIX.rstrip("/") or "/cards"

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
    # Back-compat: keep /public for local dev / older clients.
    app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
    # Preferred deployment prefix for isolation under a subpath (e.g. /cards).
    app.mount(
        f"{APP_PREFIX}/public",
        StaticFiles(directory=str(PUBLIC_DIR), html=True),
        name="public_prefixed",
    )


@dataclass
class ClientSettings:
    llm_enabled: bool = False
    model_alias: str = ""
    invite_code: str = ""
    invite_valid: bool = False


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._settings: Dict[WebSocket, ClientSettings] = {}

    async def connect(self, table_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(table_id, set()).add(websocket)
        # Per-browser defaults: LLM off by default, even if server has a key configured.
        self._settings[websocket] = ClientSettings(
            llm_enabled=False,
            model_alias=get_current_model_alias(),
        )

    def disconnect(self, table_id: str, websocket: WebSocket):
        conns = self.active_connections.get(table_id)
        if conns and websocket in conns:
            conns.remove(websocket)
        self._settings.pop(websocket, None)

    async def broadcast(self, table_id: str, message: dict):
        for ws in list(self.active_connections.get(table_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                # Drop broken connections silently for now
                self.disconnect(table_id, ws)

    async def send(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            # Best-effort: if a send fails, try to remove from all tables.
            for tid, conns in list(self.active_connections.items()):
                if websocket in conns:
                    self.disconnect(tid, websocket)

    def get_settings(self, websocket: WebSocket) -> ClientSettings:
        return self._settings.get(websocket, ClientSettings())

    def update_settings(
        self,
        websocket: WebSocket,
        *,
        llm_enabled: Optional[bool] = None,
        model_alias: Optional[str] = None,
        invite_code: Optional[str] = None,
        invite_valid: Optional[bool] = None,
    ) -> ClientSettings:
        cur = self.get_settings(websocket)
        if llm_enabled is not None:
            cur.llm_enabled = bool(llm_enabled)
        if model_alias is not None and model_alias in set(get_allowed_model_aliases()):
            cur.model_alias = model_alias
        if invite_code is not None:
            cur.invite_code = str(invite_code).strip()
        if invite_valid is not None:
            cur.invite_valid = bool(invite_valid)
        self._settings[websocket] = cur
        return cur


manager = ConnectionManager()

# In-memory single table engine for MVP
DEFAULT_TABLE_ID = "default"
_engines: Dict[str, TableEngine] = {
    DEFAULT_TABLE_ID: TableEngine(EngineConfig(session_id=DEFAULT_TABLE_ID))
}

# Per-table locks for serializing state mutations.
# NOTE: Only works with --workers 1 (single process). Multi-worker deployments
# would need Redis/DB-based locking.
_table_locks: Dict[str, asyncio.Lock] = {}


def _get_table_lock(table_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for a specific table."""
    return _table_locks.setdefault(table_id, asyncio.Lock())


# Simple in-memory cache for hand-strength results keyed by table/hand/street/hero state
_hand_strength_cache: Dict[tuple, HandStrengthResult] = {}
_ai_provider = get_ai_provider_from_env()

# Invite code store for API access control
_invite_store = InviteCodeStore()


def _refresh_ai_provider() -> None:
    global _ai_provider
    _ai_provider = get_ai_provider_from_env()


def _client_host(request: Request) -> str:
    if request.client is None:
        return ""
    return request.client.host or ""


def _is_local_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def _is_admin_request(request: Request) -> bool:
    token = os.getenv("ADMIN_TOKEN", "").strip()
    if token:
        supplied = request.headers.get("x-admin-token", "").strip()
        supplied = supplied or request.query_params.get("admin_token", "").strip()
        if supplied == token:
            return True
    allow_local = os.getenv("LOCAL_ADMIN_BYPASS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return allow_local and _is_local_host(_client_host(request))


def _local_invite_bypass_enabled(request: Optional[Request] = None) -> bool:
    enabled = os.getenv("LOCAL_INVITE_BYPASS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled or request is None:
        return False
    return _is_local_host(_client_host(request))


async def _validate_invite_code_async(invite_code: str) -> bool:
    code = str(invite_code or "").strip()
    if not code:
        return False
    try:
        import anyio

        return await anyio.to_thread.run_sync(_invite_store.validate_code, code)
    except Exception:
        return False


class AiModelAliasBody(BaseModel):
    model_alias: str


class AiAdviceRequestBody(BaseModel):
    seat: int = 1
    model_alias: Optional[str] = None
    invite_code: Optional[str] = None


ADMIN_LLM_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>LLM Admin - Poker Coach Alpha</title>
    <style>
      :root { color-scheme: dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      body { margin: 0; background: #0b1520; color: #e6eef5; }
      main { max-width: 980px; margin: 0 auto; padding: 24px 16px 48px; }
      header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 20px; }
      h1 { font-size: 24px; margin: 0; }
      h2 { font-size: 16px; margin: 0 0 12px; color: #d4af37; }
      section { border-top: 1px solid rgba(255,255,255,.12); padding: 18px 0; }
      label { display: grid; gap: 6px; color: #9ca3af; font-size: 13px; }
      input, select { width: 100%; border: 1px solid #2f4863; border-radius: 6px; background: #101c29; color: #e6eef5; padding: 9px 10px; font: inherit; }
      button { border: 1px solid rgba(212,175,55,.45); border-radius: 6px; background: rgba(212,175,55,.12); color: #e6eef5; padding: 9px 12px; cursor: pointer; }
      button:disabled { opacity: .55; cursor: not-allowed; }
      .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
      .tiers { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
      .tier { border: 1px solid rgba(255,255,255,.1); border-radius: 8px; padding: 12px; background: #101c29; display: grid; gap: 10px; }
      .tier-title { display: flex; justify-content: space-between; gap: 8px; align-items: center; font-weight: 700; }
      .actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
      .status { min-height: 22px; color: #9ca3af; white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
      .models { max-height: 220px; overflow: auto; border: 1px solid rgba(255,255,255,.1); border-radius: 6px; padding: 8px; background: #101c29; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
      @media (max-width: 760px) { .grid, .tiers { grid-template-columns: 1fr; } header { align-items: flex-start; flex-direction: column; } }
    </style>
  </head>
  <body>
    <main>
      <header>
        <h1>LLM Admin</h1>
        <a href="../" style="color:#d4af37">Back to app</a>
      </header>
      <section>
        <h2>Gateway</h2>
        <div class="grid">
          <label>Provider
            <select id="provider">
              <option value="dummy">dummy</option>
              <option value="openai">openai-compatible</option>
              <option value="gateway">gateway</option>
            </select>
          </label>
          <label>API Base
            <input id="apiBase" placeholder="https://gateway.example.com/v1" />
          </label>
          <label>API Key
            <input id="apiKey" type="password" placeholder="leave blank to keep current key" />
          </label>
          <label>Default Tier
            <select id="defaultTier">
              <option value="smart">smart</option>
              <option value="balanced">balanced</option>
              <option value="fast">fast</option>
            </select>
          </label>
        </div>
      </section>
      <section>
        <h2>Tiers</h2>
        <div class="tiers" id="tiers"></div>
      </section>
      <section>
        <div class="actions">
          <button id="saveBtn">Save config</button>
          <button id="listBtn">Fetch model list</button>
          <button id="testBtn">Test all tiers</button>
        </div>
        <p id="status" class="status"></p>
        <div id="models" class="models" hidden></div>
      </section>
    </main>
    <script>
      const tierIds = ["smart", "balanced", "fast"];
      let loaded = null;
      const adminToken = new URLSearchParams(window.location.search).get("admin_token") || "";
      function api(path, opts = {}) {
        const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
        if (adminToken) headers["x-admin-token"] = adminToken;
        return fetch(path, { ...opts, headers });
      }
      function setStatus(text) { document.getElementById("status").textContent = text || ""; }
      function tierCard(id, data) {
        return `<div class="tier" data-tier="${id}">
          <div class="tier-title"><span>${id}</span><label style="display:flex;grid-template-columns:auto;gap:6px;align-items:center"><input type="checkbox" class="tier-enabled" ${data.enabled ? "checked" : ""}/> enabled</label></div>
          <label>Label <input class="tier-label" value="${data.label || id}" /></label>
          <label>Model <input class="tier-model" value="${data.model || ""}" /></label>
          <label>Cost
            <select class="tier-cost">
              ${["low","medium","high"].map(v => `<option value="${v}" ${data.cost_level === v ? "selected" : ""}>${v}</option>`).join("")}
            </select>
          </label>
          <label>Timeout seconds <input class="tier-timeout" type="number" min="1" max="120" value="${data.timeout_seconds || 20}" /></label>
        </div>`;
      }
      function collect() {
        const tiers = {};
        document.querySelectorAll(".tier").forEach((el) => {
          const id = el.dataset.tier;
          tiers[id] = {
            enabled: el.querySelector(".tier-enabled").checked,
            label: el.querySelector(".tier-label").value.trim(),
            model: el.querySelector(".tier-model").value.trim(),
            cost_level: el.querySelector(".tier-cost").value,
            timeout_seconds: Number(el.querySelector(".tier-timeout").value || 20),
          };
        });
        const apiKeyInput = document.getElementById("apiKey").value.trim();
        return {
          provider: document.getElementById("provider").value,
          api_base: document.getElementById("apiBase").value.trim(),
          api_key: apiKeyInput || (loaded && loaded.api_key_set ? undefined : ""),
          default_tier: document.getElementById("defaultTier").value,
          tiers,
        };
      }
      async function load() {
        const res = await api("llm/config");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        loaded = await res.json();
        document.getElementById("provider").value = loaded.provider || "dummy";
        document.getElementById("apiBase").value = loaded.api_base || "";
        document.getElementById("apiKey").placeholder = loaded.api_key_set ? `current: ${loaded.api_key_preview}` : "required for openai/gateway";
        document.getElementById("defaultTier").value = loaded.default_tier || "balanced";
        document.getElementById("tiers").innerHTML = tierIds.map((id) => tierCard(id, loaded.tiers[id] || {})).join("");
      }
      document.getElementById("saveBtn").onclick = async () => {
        setStatus("Saving...");
        const res = await api("llm/config", { method: "POST", body: JSON.stringify(collect()) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { setStatus(`Save failed: ${data.error || res.status}`); return; }
        document.getElementById("apiKey").value = "";
        loaded = data;
        setStatus("Saved.");
      };
      document.getElementById("listBtn").onclick = async () => {
        setStatus("Fetching models...");
        const res = await api("llm/models", { method: "POST", body: JSON.stringify(collect()) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { setStatus(`Fetch failed: ${data.error || res.status}`); return; }
        const box = document.getElementById("models");
        box.hidden = false;
        box.textContent = (data.models || []).join("\\n") || "(no models returned)";
        setStatus(`Fetched ${data.models.length} model(s).`);
      };
      document.getElementById("testBtn").onclick = async () => {
        const btn = document.getElementById("testBtn");
        const payload = collect();
        const lines = [];
        btn.disabled = true;
        try {
          for (const tierId of tierIds) {
            const tier = payload.tiers && payload.tiers[tierId];
            const modelName = tier && tier.model ? String(tier.model).trim() : "";
            if (!modelName) {
              lines.push(`${tierId}: skipped (no model in form)`);
              continue;
            }
            setStatus(`Testing ${tierId} (${modelName})...`);
            const testPayload = { ...payload, tier: tierId, model: modelName };
            const res = await api("llm/test", { method: "POST", body: JSON.stringify(testPayload) });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.ok) {
              lines.push(`${tierId}: FAILED — ${data.error || res.status || "error"}`);
            } else {
              lines.push(`${tierId}: ok — ${data.model} -> ${data.response || ""}`);
            }
          }
          setStatus(lines.join("\\n") || "Nothing to test.");
        } catch (e) {
          setStatus(`Test error: ${e}`);
        } finally {
          btn.disabled = false;
        }
      };
      load().catch((err) => setStatus(`Load failed: ${err}`));
    </script>
  </body>
</html>
"""


async def _broadcast_ai_advice(table_id: str, seat: int) -> None:
    """Generate and broadcast AI advice for the acting seat.

    Acquires per-table lock only for reading state and getting seq number.
    LLM calls and broadcasting happen outside the lock.
    """
    # Gather state under lock
    async with _get_table_lock(table_id):
        engine = _engines.get(table_id)
        if not engine or engine.state is None:
            return
        idx = engine._seat_to_state_index(seat)  # type: ignore[attr-defined]
        if idx is None:
            return
        try:
            positions_map = None
            try:
                positions_map = engine._positions_map()  # type: ignore[attr-defined]
            except Exception:
                positions_map = None
            dc, _payload = compose_analysis(
                engine.state,
                idx,
                seat,
                session_stats=getattr(engine, "session_stats", None),
                positions_map=positions_map,
                include_hand_strength=False,
            )
            legal_actions = engine.legal_actions()
            history = getattr(engine, "action_history", None)
            conns = list(manager.active_connections.get(table_id, []))
            # Get seq numbers for each connection under lock
            conn_seqs = [(ws, engine.next_sequence()) for ws in conns]
        except Exception:
            # On error, get a seq for error broadcast
            try:
                error_seq = engine.next_sequence()
            except Exception:
                error_seq = 0
            conn_seqs = []
            dc = None  # type: ignore
            legal_actions = []
            history = None

    # If we failed to gather state, broadcast error
    if dc is None:
        try:
            msg = {
                "type": "ai_advice",
                "seq": error_seq,
                "to_act": seat,
                "advice": {
                    "recommended_action": None,
                    "secondary_action": None,
                    "confidence": None,
                    "explanation": None,
                    "reason": "error",
                },
            }
            await manager.broadcast(table_id, msg)
        except Exception:
            pass
        return

    # Process each connection outside the lock (LLM calls are slow)
    for ws, seq in conn_seqs:
        try:
            settings = manager.get_settings(ws)
            advice = None
            # Only call the LLM if:
            # 1. Browser explicitly enabled it
            # 2. Provider is configured (not DummyProvider)
            # 3. Valid invite code is present
            invite_ok = False
            try:
                ws_host = ws.client.host if ws.client is not None else ""
                invite_ok = os.getenv("LOCAL_INVITE_BYPASS", "0").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                } and _is_local_host(ws_host)
            except Exception:
                invite_ok = False
            if settings.invite_code and not invite_ok:
                invite_ok = await _validate_invite_code_async(settings.invite_code)
                if invite_ok != settings.invite_valid:
                    manager.update_settings(ws, invite_valid=invite_ok)

            if settings.llm_enabled and not isinstance(_ai_provider, DummyProvider) and invite_ok:
                async with use_model_alias(settings.model_alias):
                    advice = await generate_ai_advice(dc, legal_actions, _ai_provider, history)
            else:
                advice = select_actions_heuristic(dc, legal_actions)
                if not invite_ok:
                    advice.reason = "invite_code_required"
                elif not settings.llm_enabled:
                    advice.reason = "client_disabled_llm"
                elif isinstance(_ai_provider, DummyProvider):
                    advice.reason = "dummy_provider"
            msg = {
                "type": "ai_advice",
                "seq": seq,
                "to_act": seat,
                "advice": {
                    "recommended_action": advice.recommended_action,
                    "secondary_action": advice.secondary_action,
                    "confidence": advice.confidence,
                    "explanation": advice.explanation,
                    "reason": advice.reason,
                },
            }
            await manager.send(ws, msg)
        except Exception:
            pass


async def _broadcast_hand_strength(table_id: str, seat: int) -> None:
    """Compute hand strength asynchronously and broadcast an analysis update.

    Time-budgeted to ~300ms; if it times out or fails, send a degraded/null payload.
    Acquires per-table lock only for reading state and getting seq number.
    """
    import anyio

    # Gather state and seq under lock
    async with _get_table_lock(table_id):
        engine = _engines.get(table_id)
        if not engine or engine.state is None:
            return
        # Map seat -> current state index
        idx = engine._seat_to_state_index(seat)  # type: ignore[attr-defined]
        if idx is None:
            return

        # Precompute live players for better fallback info
        try:
            statuses = list(getattr(engine.state, "statuses", []) or [])
            players = sum(1 for x in statuses if bool(x)) or 0
            if not players:
                stacks = list(getattr(engine.state, "stacks", []) or [])
                players = sum(1 for s in stacks if (s or 0) > 0)
        except Exception:
            players = 0

        # Build a stable cache key for current decision state
        cache_key = None
        try:
            street_idx = getattr(engine.state, "street_index", None)
            board_cards: list[str] = []
            for cards in getattr(engine.state, "board_cards", []) or []:
                for c in cards or []:
                    board_cards.append(str(c))
            hole_cards = []
            all_holes = list(getattr(engine.state, "hole_cards", []) or [])
            if 0 <= idx < len(all_holes):
                hole_cards = [str(c) for c in (all_holes[idx] or [])]
            hand_id = getattr(engine, "hand_index", 0)
            cache_key = (
                table_id,
                hand_id,
                seat,
                street_idx,
                tuple(board_cards),
                tuple(hole_cards),
                players,
            )
        except Exception:
            cache_key = None

        # Per-street sample_count budget
        try:
            street_idx = getattr(engine.state, "street_index", None)
        except Exception:
            street_idx = None
        if street_idx == 0:  # preflop
            sample_count = 400
        elif street_idx == 1:  # flop
            sample_count = 400
        elif street_idx == 2:  # turn
            sample_count = 400
        else:  # river or unknown
            sample_count = 400

        # Get seq under lock
        seq = engine.next_sequence()

        # Copy state reference for computation outside lock
        state_for_compute = engine.state

    # Compute outside the lock (this is the slow part)
    try:
        # Cache hit: reuse previous result
        if cache_key is not None and cache_key in _hand_strength_cache:
            result = _hand_strength_cache[cache_key]
            degraded = False
        else:
            # Compute with timeout and offload to a thread
            with anyio.move_on_after(0.3) as scope:  # 300ms budget
                result = await anyio.to_thread.run_sync(
                    compute_hand_strength, state_for_compute, idx, sample_count
                )
            degraded = False
            if scope.cancel_called:  # timed out
                result = HandStrengthResult(
                    hand_strength_pct=None,
                    model="pokerkit.calculate_hand_strength",
                    sample_count=sample_count,
                    players=players,
                    degraded=True,
                    reason="timeout",
                )
                degraded = True
            # Only cache non-degraded successful results
            if cache_key is not None and not (result.degraded or degraded):
                _hand_strength_cache[cache_key] = result

        msg = {
            "type": "analysis",
            "seq": seq,
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
                    "seq": seq,
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


@app.get(f"{APP_PREFIX}", include_in_schema=False)
def index_prefixed_redirect() -> RedirectResponse:
    # Ensure relative paths resolve correctly under the prefix (trailing slash).
    return RedirectResponse(url=f"{APP_PREFIX}/", status_code=307)


@app.get(f"{APP_PREFIX}/", response_class=HTMLResponse)
def index_prefixed() -> HTMLResponse:
    # Serve the same index.html but under the /cards (or APP_PREFIX) mount.
    return index()


@app.get("/admin/llm", response_class=HTMLResponse)
@app.get(f"{APP_PREFIX}/admin/llm", response_class=HTMLResponse)
def llm_admin_page(request: Request) -> HTMLResponse:
    if not _is_admin_request(request):
        return HTMLResponse("Forbidden", status_code=403)
    return HTMLResponse(ADMIN_LLM_HTML)


@app.get("/admin/llm/config")
@app.get(f"{APP_PREFIX}/admin/llm/config")
def get_llm_admin_config(request: Request):
    if not _is_admin_request(request):
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    return public_config()


@app.post("/admin/llm/config")
@app.post(f"{APP_PREFIX}/admin/llm/config")
async def set_llm_admin_config(request: Request):
    if not _is_admin_request(request):
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    try:
        payload = await request.json()
        cfg = save_llm_config(payload if isinstance(payload, dict) else {})
        _refresh_ai_provider()
        if cfg.get("default_tier"):
            set_current_model_alias(str(cfg["default_tier"]))
        return public_config()
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception:
        return JSONResponse(status_code=500, content={"error": "save_failed"})


@app.post("/admin/llm/models")
@app.post(f"{APP_PREFIX}/admin/llm/models")
async def get_llm_gateway_models(request: Request):
    if not _is_admin_request(request):
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    try:
        payload = await request.json()
        models = await list_gateway_models(payload if isinstance(payload, dict) else None)
        return {"models": models}
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/admin/llm/test")
@app.post(f"{APP_PREFIX}/admin/llm/test")
async def test_llm_gateway(request: Request):
    if not _is_admin_request(request):
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
        model = str(payload.get("model") or "").strip()
        if not model:
            model = resolve_model_id(str(payload.get("tier") or payload.get("default_tier") or ""))
        result = await test_gateway_model(model, payload)
        status = 200 if result.get("ok") else 400
        return JSONResponse(status_code=status, content=result)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})


@app.post("/tables")
@app.post(f"{APP_PREFIX}/tables")
def create_table():
    table_id = DEFAULT_TABLE_ID
    _engines[table_id] = TableEngine(EngineConfig(session_id=table_id))
    return {"table_id": table_id}


@app.get("/settings/ai_model")
@app.get(f"{APP_PREFIX}/settings/ai_model")
def get_ai_model_settings(request: Request):
    return {
        "model_alias": get_current_model_alias(),
        "allowed": get_allowed_model_aliases(),
        "tiers": get_allowed_model_tiers(),
        "llm_available": not isinstance(_ai_provider, DummyProvider),
        "invite_required": not _local_invite_bypass_enabled(request),
        # Per-browser default is OFF; this is informational only for the UI.
        "default_llm_enabled": False,
    }


@app.post("/settings/ai_model")
@app.post(f"{APP_PREFIX}/settings/ai_model")
def set_ai_model_settings(body: AiModelAliasBody):
    alias = body.model_alias
    if not set_current_model_alias(alias):
        return JSONResponse(status_code=400, content={"error": "invalid_model_alias"})
    return {"model_alias": alias}


@app.post("/tables/{table_id}/join")
@app.post(f"{APP_PREFIX}/tables/{{table_id}}/join")
def join_table(table_id: str):
    engine = _engines.get(table_id)
    if not engine:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    # MVP: fixed human seat 1
    return {"player_id": "human", "seat": 1}


@app.post("/tables/{table_id}/ai_advice/llm")
@app.post(f"{APP_PREFIX}/tables/{{table_id}}/ai_advice/llm")
async def request_llm_ai_advice(request: Request, table_id: str, body: AiAdviceRequestBody):
    if isinstance(_ai_provider, DummyProvider):
        return JSONResponse(status_code=400, content={"error": "llm_not_configured"})

    # Validate invite code
    invite_code = body.invite_code
    invite_ok = _local_invite_bypass_enabled(request)
    if not invite_ok and invite_code:
        invite_ok = await _validate_invite_code_async(invite_code)
    if not invite_ok:
        return JSONResponse(status_code=403, content={"error": "invite_code_required"})

    seat = int(body.seat or 1)

    alias = body.model_alias
    if alias is not None and alias not in set(get_allowed_model_aliases()):
        return JSONResponse(status_code=400, content={"error": "invalid_model_alias"})

    # Gather state under lock (fast) so we don't hold it during the LLM call.
    async with _get_table_lock(table_id):
        engine = _engines.get(table_id)
        if not engine or engine.state is None:
            return JSONResponse(status_code=404, content={"error": "table not found"})

        idx = engine._seat_to_state_index(seat)  # type: ignore[attr-defined]
        if idx is None:
            return JSONResponse(status_code=400, content={"error": "invalid_seat"})

        try:
            positions_map = None
            try:
                positions_map = engine._positions_map()  # type: ignore[attr-defined]
            except Exception:
                positions_map = None
            dc, _payload = compose_analysis(
                engine.state,
                idx,
                seat,
                session_stats=getattr(engine, "session_stats", None),
                positions_map=positions_map,
                include_hand_strength=False,
            )
            legal_actions = engine.legal_actions()
            history = getattr(engine, "action_history", None)
        except Exception:
            return JSONResponse(status_code=500, content={"error": "llm_request_failed"})

    # LLM call outside lock.
    try:
        async with use_model_alias(alias):
            advice = await generate_ai_advice(dc, legal_actions, _ai_provider, history)
    except Exception:
        return JSONResponse(status_code=500, content={"error": "llm_request_failed"})

    # Get seq under lock (next_sequence mutates engine state).
    async with _get_table_lock(table_id):
        engine = _engines.get(table_id)
        seq = engine.next_sequence() if engine is not None else 0

    return {
        "type": "ai_advice",
        "seq": seq,
        "to_act": seat,
        "advice": {
            "recommended_action": advice.recommended_action,
            "secondary_action": advice.secondary_action,
            "confidence": advice.confidence,
            "explanation": advice.explanation,
            "reason": advice.reason,
        },
    }


async def _schedule_prompt_tasks(table_id: str, seat_act: int) -> None:
    asyncio.create_task(_broadcast_hand_strength(table_id, seat_act))
    asyncio.create_task(_broadcast_ai_advice(table_id, seat_act))


@app.post("/tables/{table_id}/start")
@app.post(f"{APP_PREFIX}/tables/{{table_id}}/start")
async def start_session(table_id: str):
    # Acquire lock for state mutation
    async with _get_table_lock(table_id):
        engine = _engines.get(table_id)
        if not engine:
            return JSONResponse(status_code=404, content={"error": "table not found"})
        # Prevent starting a new session while one is already active; callers
        # should use /restart if they need to force-reset mid-session.
        if getattr(engine, "session_active", False):
            return JSONResponse(status_code=400, content={"error": "session already active"})
        engine.start_session()
        # Advance until prompt or hand end
        messages, _ = engine.advance(human_seat=1)
        hand_id = f"h_{engine.hand_index:05d}"

    # Broadcast outside the lock
    for m in messages:
        try:
            await manager.broadcast(table_id, m)
            # After broadcasting a prompt, schedule async tasks
            if isinstance(m, dict) and m.get("type") == "prompt":
                asyncio.create_task(_schedule_prompt_tasks(table_id, m.get("to_act", 1)))
        except Exception:
            pass
    return {"hand_id": hand_id}


@app.post("/tables/{table_id}/next")
@app.post(f"{APP_PREFIX}/tables/{{table_id}}/next")
async def next_hand(table_id: str):
    # Acquire lock for state mutation
    async with _get_table_lock(table_id):
        engine = _engines.get(table_id)
        if not engine or engine.state is None:
            return JSONResponse(status_code=404, content={"error": "table not found"})
        ok, reason = engine.start_next_hand()
        if not ok:
            if reason:
                # If session ended or cannot proceed, notify caller
                return JSONResponse(status_code=400, content={"error": reason})
            return JSONResponse(status_code=400, content={"error": "cannot start next hand"})
        # Advance
        messages, _ = engine.advance(human_seat=1)
        hand_id = f"h_{engine.hand_index:05d}"

    # Broadcast outside the lock
    for m in messages:
        try:
            await manager.broadcast(table_id, m)
            if isinstance(m, dict) and m.get("type") == "prompt":
                asyncio.create_task(_schedule_prompt_tasks(table_id, m.get("to_act", 1)))
        except Exception:
            pass
    return {"hand_id": hand_id}


@app.get("/tables/{table_id}/state")
@app.get(f"{APP_PREFIX}/tables/{{table_id}}/state")
def get_state(table_id: str):
    engine = _engines.get(table_id)
    if not engine or engine.state is None:
        return JSONResponse(status_code=404, content={"error": "table not found"})
    snap = engine.build_table_snapshot()
    return {"type": "snapshot", "seq": 0, "table": snap}


@app.post("/tables/{table_id}/restart")
@app.post(f"{APP_PREFIX}/tables/{{table_id}}/restart")
async def restart_session(table_id: str):
    # Acquire lock for state mutation
    async with _get_table_lock(table_id):
        engine = _engines.get(table_id)
        if not engine:
            return JSONResponse(status_code=404, content={"error": "table not found"})
        # Restart fresh session (keep same session_id)
        engine.restart_session()
        # Advance until prompt or hand end
        messages, _ = engine.advance(human_seat=1)
        hand_id = f"h_{engine.hand_index:05d}"

    # Broadcast outside the lock
    for m in messages:
        try:
            await manager.broadcast(table_id, m)
            if isinstance(m, dict) and m.get("type") == "prompt":
                asyncio.create_task(_schedule_prompt_tasks(table_id, m.get("to_act", 1)))
        except Exception:
            pass
    return {"hand_id": hand_id}


@app.websocket("/ws/tables/{table_id}")
@app.websocket(f"{APP_PREFIX}/ws/tables/{{table_id}}")
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
                        asyncio.create_task(_schedule_prompt_tasks(table_id, seat_act))
            except Exception:
                pass
        # Main loop: receive client actions and advance engine
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "client_settings":
                llm_enabled = data.get("llm_enabled")
                model_alias = data.get("model_alias")
                invite_code = data.get("invite_code")

                if model_alias is not None and model_alias not in set(get_allowed_model_aliases()):
                    await websocket.send_json(
                        {"type": "client_settings_ack", "error": "invalid_model_alias"}
                    )
                    continue

                # Validate invite code if provided
                invite_valid: Optional[bool] = None
                try:
                    ws_host = websocket.client.host if websocket.client is not None else ""
                    if os.getenv("LOCAL_INVITE_BYPASS", "0").strip().lower() in {
                        "1",
                        "true",
                        "yes",
                        "on",
                    } and _is_local_host(ws_host):
                        invite_valid = True
                except Exception:
                    invite_valid = None
                if invite_code is not None:
                    invite_code_str = str(invite_code).strip()
                    if invite_valid is True:
                        pass
                    elif invite_code_str:
                        invite_valid = await _validate_invite_code_async(invite_code_str)
                    else:
                        # Empty string means user cleared the code
                        invite_valid = False

                new_settings = manager.update_settings(
                    websocket,
                    llm_enabled=bool(llm_enabled) if llm_enabled is not None else None,
                    model_alias=str(model_alias) if model_alias is not None else None,
                    invite_code=str(invite_code) if invite_code is not None else None,
                    invite_valid=invite_valid,
                )
                await websocket.send_json(
                    {
                        "type": "client_settings_ack",
                        "llm_enabled": bool(new_settings.llm_enabled),
                        "model_alias": new_settings.model_alias,
                        "llm_available": not isinstance(_ai_provider, DummyProvider),
                        "invite_valid": new_settings.invite_valid,
                    }
                )
                continue
            if data.get("type") == "action":
                # Process action under lock
                msgs_to_broadcast: list = []
                action_notification: Optional[dict] = None
                error_to_send: Optional[Error] = None
                skip_action = False

                async with _get_table_lock(table_id):
                    engine = _engines.get(table_id)
                    if not engine or engine.state is None:
                        error_to_send = Error(message="table not ready")
                    else:
                        # Validate and parse client action
                        try:
                            client_action = ClientAction(**data)
                            action = client_action.action.model_dump(exclude_unset=True)

                            # Check action idempotency
                            if engine.bot_manager.is_action_processed(client_action.action_id):
                                skip_action = True  # Skip already processed action
                            else:
                                # Validate against legal actions
                                legal_actions = engine.legal_actions()
                                if not validate_action_against_legal(
                                    client_action.action, legal_actions
                                ):
                                    # Fallback: if it's a raise_to with amount and the engine accepts it, allow it
                                    try:
                                        if action.get("type") == "raise_to" and "amount" in action:
                                            amt = int(action.get("amount"))
                                            if not engine._try_raise_to(amt):  # type: ignore[attr-defined]
                                                error_to_send = Error(message="illegal action")
                                        else:
                                            error_to_send = Error(message="illegal action")
                                    except Exception:
                                        error_to_send = Error(message="illegal action")

                                if error_to_send is None and not skip_action:
                                    # Mark action as processed for idempotency
                                    engine.bot_manager.add_processed_action(client_action.action_id)

                                    # Apply action
                                    try:
                                        engine.apply_action(action)
                                        action_notification = {
                                            "type": "action_taken",
                                            "seat": client_action.seat,
                                            "player_id": engine.player_ids[client_action.seat - 1],
                                            "action_type": action.get("type", "unknown"),
                                            "amount": action.get("amount"),
                                            "is_bot": False,
                                        }
                                    except Exception as e:
                                        import traceback as _tb

                                        error_to_send = Error(
                                            message=f"apply_action failed: {e}",
                                            trace=_tb.format_exc(limit=10),
                                        )

                                    # Advance engine if apply succeeded
                                    if error_to_send is None:
                                        try:
                                            msgs_to_broadcast, _prompt = engine.advance(
                                                human_seat=1
                                            )
                                        except Exception as e:
                                            import traceback as _tb

                                            try:
                                                snap = engine.build_table_snapshot()
                                            except Exception:
                                                snap = None
                                            error_to_send = Error(
                                                message=f"advance failed: {e}",
                                                trace=_tb.format_exc(limit=20),
                                                snapshot=snap,
                                            )

                        except Exception as e:
                            error_to_send = Error(message=f"invalid action format: {e}")

                # Outside lock: send responses and broadcast
                if skip_action:
                    continue
                if error_to_send is not None:
                    await websocket.send_json(error_to_send.model_dump())
                    continue
                if action_notification is not None:
                    await websocket.send_json(action_notification)
                for m in msgs_to_broadcast:
                    await manager.broadcast(table_id, m)
                    if isinstance(m, dict) and m.get("type") == "prompt":
                        # Schedule async hand-strength compute without blocking UI
                        asyncio.create_task(_schedule_prompt_tasks(table_id, m.get("to_act", 1)))
            else:
                await websocket.send_json({"type": "ack", "received": data})
    except WebSocketDisconnect:
        manager.disconnect(table_id, websocket)
    except Exception:
        manager.disconnect(table_id, websocket)
        return
