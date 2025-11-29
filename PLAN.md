# Poker Coach Alpha — Roadmap and Technical Plan

This document captures the staged plan from MVP to V3, with concrete interfaces, data structures, and deliverables.

## Phase 0 — Tech stack and principles
- Stack: FastAPI + WebSocket (Python), pokerkit for rules/engine, simple Python bots, static client (vanilla HTML or React). In-memory state for MVP; add Postgres/Redis later.
- Principles: server is source of truth; per-table lock; event-sourced state with snapshots; idempotent actions (action_id); deterministic RNG seeds per hand for auditability.

## MVP — Single-table NLHE (1 human + bots)
- Scope
  - Game: No-Limit Texas Hold’em, 6-max, fixed blinds/antes, no rake.
  - Session stop: human busts OR all bots bust OR max_hands reached.
  - Table: 1 in-memory table; 1 human seat; remaining seats auto-filled by server bots.
  - Bots: must choose from pokerkit-provided legal actions; simple policy.
  - UX: single page; join seat; render stacks/board/pot; show hole cards; choose among prompted legal actions; session progress panel.
  - Bet sizing: pot-based raise options (1/3, 1/2, 2/3, 1×, 2× pot). Enforce min-raise; remove fixed 2/4/6 buttons.
  - Showdown: reveal all live hands (exclude folded). Compute winners via pokerkit best-5 evaluation; display winners client-side.
  - Rotation: move button each hand; surface seat positions (BTN, SB, BB, UTG, MP, CO) in the client.
  - Hand flow: no auto-advance; add a "Continue Next Hand" button to proceed.

- Backend components
  - TableService: wraps pokerkit engine; owns TableState {players, stacks, button, board, pot, street, to_act, legal_actions, seq}.
  - SessionManager: runs the hand loop, enforces session termination conditions, manages RNG seed per hand.
  - ActionRouter: WebSocket handler per table; enforces per-table lock; validates actions; advances engine; broadcasts snapshots.
  - BotManager: executes bot turns when to_act is a bot.
  - RaiseSizer: derives candidate raise_to amounts from pot fractions and validates via pokerkit.
  - ShowdownEvaluator: determines best-5 for live hands and winners from pokerkit; emits showdown payload with winners.
  - PositionManager: tracks and rotates button; derives position labels per seat for 6-max.

- API surface
  - REST
    - POST /tables → {table_id} (MVP: returns "default")
    - POST /tables/{id}/join → {player_id, seat}
    - POST /tables/{id}/start → {hand_id}
    - POST /tables/{id}/next → {hand_id} (advance to next hand after hand_end)
    - GET /tables/{id}/state → snapshot (for initial load)
  - WebSocket
    - /ws/tables/{id}?player_id=...
    - Server→client messages: `snapshot`, `prompt`, `showdown`, `hand_end`, `session_end`, `error`
    - Client→server messages: `action`

- Message examples
```json
{
  "type": "snapshot",
  "seq": 42,
  "table": {
    "table_id": "default",
    "hand_id": "h_00123",
    "button_seat": 3,
    "blinds": {"sb": 1, "bb": 2},
    "players": [{"seat":1,"id":"p1","stack":198,"in_hand":true},{"seat":2,"id":"bot2","stack":202,"in_hand":true}],
    "street": "flop",
    "board": ["Ah","7d","2c"],
    "pot": 15,
    "bets": {"1": 4, "2": 2},
    "to_act": 1,
    "legal_actions": [
      {"type":"fold"},
      {"type":"call","amount":2},
      {"type":"raise_to","amount":9},
      {"type":"raise_to","amount":12},
      {"type":"raise_to","amount":15},
      {"type":"raise_to","amount":21},
      {"type":"raise_to","amount":33}
    ]
  }
}
```
```json
{ "type":"prompt", "seq":43, "to_act":1, "legal_actions":[{"type":"fold"},{"type":"call","amount":2},{"type":"raise_to","amount":12}] }
```
```json
{ "type":"showdown", "hand_id":"h_00123", "board":["Ah","7d","2c","Qs","2h"], "players":[{"seat":1,"id":"p1","hole":["Ad","Kh"],"in_hand":true},{"seat":2,"id":"bot2","hole":["9s","9c"],"in_hand":true}], "winners":[{"seat":1,"best5":["Ad","Ah","Qs","2h","2c"],"rank":"Two Pair"}] }
```
```json
{ "type":"hand_end", "hand_id":"h_00123", "results":[{"seat":1,"delta":25},{"seat":2,"delta":-25}], "next_button_seat":4 }
```
```json
{ "type":"session_end", "reason":"player_busted" }
```
- Data model (in-memory)
  - TableState, PlayerState, HandLog (append-only events), Snapshot(seq, hand_id, per-seat filtered view).
  - Deterministic RNG: seed = HMAC(session_id, hand_index).

- Flow
  1. join → start → create pokerkit engine.
  2. Post blinds, deal.
  3. Loop streets/actions:
     - If `to_act` is bot: BotManager picks from `legal_actions` and applies.
     - If `to_act` is human: send `prompt`, await WS `action`; check idempotency by `action_id`; validate against `legal_actions`; apply.
     - After each state change: broadcast `snapshot`.
  4. On `showdown`: emit all live hands and winners.
  5. On `hand_end`: update stacks, rotate button; if session-stop condition hit (human busts OR all bots bust OR max_hands), emit `session_end`; else wait for REST `POST /tables/{id}/next` to start the next hand.

- Acceptance criteria
  - Pot-based raise options appear and are legal; min-raise enforced; no 2/4/6 buttons.
  - Showdown reveals all live hole cards; winners computed and included; ties handled.
  - Button rotates correctly; client shows seat positions.
  - No auto-advance; next hand only after "Continue Next Hand".
  - Session ends when human busts or all bots bust or max_hands reached.

- Test plan
  - Unit: action validation and raise sizing; side pot math; split pots; winner computation cross-check vs pokerkit.
  - Integration: full hand playthrough incl. showdown payload correctness; rotation across multiple hands; manual next-hand gating; session termination cases.

- Milestone deliverables
  - `app/main.py` (FastAPI, REST + WS)
  - `poker/table.py` (pokerkit wrapper and state machine)
  - `poker/bots.py` (simple bot policies)
  - `ws/protocol.py` (schemas, validation, diffing)
  - `public/index.html` (minimal client)

## V1 — Coach (explain-only)
- Server-side CoachService
  - Real-time metrics per prompt: equity to showdown (MC sims), pot-win%, hand-strength percentile, outs (clean/tainted), pot odds, SPR, required equity to call.
  - Range modeling: default opponent ranges by position; configurable; cache on (street, board, hole, stacks, pot, positions).
- Deterministic sim seeds; adaptive time budget (e.g., 50–100ms avg; degrade gracefully).
- Observability & errors
  - Enhanced error handling and structured logging across backend.
- Client UX
  - Coach panel shows win%, pot-win%, hand strength rank, outs, pot odds, SPR.
  - No advice; descriptive only.
- Tests
  - Validate equity against known calculators for sampled states; snapshot tests for UI.

## V1.5 — LLM Coach (language advice layer)
- Goals
  - Build a lightweight “AI coach” that turns existing numeric metrics (DecisionContext + analysis payload) into human-readable advice.
  - Keep decision logic and model provider decoupled: the LLM never auto-acts; it only explains and suggests.
  - Support multiple LLM providers (OpenAI, Anthropic, Azure, local, etc.) via a thin adapter layer and environment-based configuration.
- Backend: AiCoachService
  - Introduce an `AiProvider` interface (e.g., `generate(prompt: str) -> str` / async equivalent) and provide concrete adapters per provider (OpenAI-style, Anthropic-style, local).
  - Configure provider via env vars: `AI_PROVIDER` (e.g. `openai`, `anthropic`, `dummy`), `AI_MODEL`, and provider-specific keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).
  - Reuse `DecisionContext` + `legal_actions` to build a provider-neutral prompt that includes:
    - Street, positions, pot, to_call, pot odds, required equity, SPR, effective stack.
    - Hero hand label, hand_strength_pct (if available), draws/outs, board texture.
    - Players count and human session stats (VPIP/PFR/AFq/style) plus preflop range equity when applicable.
  - Parse LLM output into a structured advice object:
    - `recommended_action` (restricted to current `legal_actions`, including sizing when relevant).
    - Optional `secondary_action`, `confidence`, and a short `explanation`.
  - Enforce strict timeouts and fallbacks: if provider is disabled, misconfigured, or times out, return a degraded/null advice payload without impacting gameplay.
- Model selection & LiteLLM integration
  - Use LiteLLM as the primary provider adapter when `AI_PROVIDER=openai` and a valid `OPENAI_API_KEY` is present; otherwise fall back to a `DummyProvider`.
  - Define a small, whitelisted set of model aliases (e.g., `fast`, `strong`, `cheap`) mapped to concrete LiteLLM model strings (e.g., `openai/gpt-4.1-mini`, `openai/gpt-4.1`).
  - Keep a process-local `current_model_alias` with a sensible default (`AI_MODEL_ALIAS` env or `fast`); use it inside the provider to choose the underlying model.
  - Expose lightweight helpers to get/set the current alias (`get_current_model_alias()`, `set_current_model_alias(alias)`) with validation against the whitelist.
  - Provide development-only REST endpoints:
    - `GET /settings/ai_model` → `{model_alias, allowed}` for debugging/testing.
    - `POST /settings/ai_model` with `{model_alias}` → update `current_model_alias` if allowed; otherwise return 400.
  - For initial integration, keep action selection heuristic-based (using `DecisionContext`), and use the LLM primarily to generate the natural-language `explanation` text, ensuring stability and safety while still allowing model comparison.
- Protocol: WebSocket messages
  - Add a server→client message type `ai_advice` that carries:
    - `to_act` seat; structured advice payload (recommended/secondary action, confidence, explanation); optional `reason` on degradation.
  - Only emit `ai_advice` for the human seat when it is their turn; advice is non-binding and never used for bot decisions.
- Client UX
  - Extend the existing Coach drawer with an “AI Coach” section:
    - Show recommended action + confidence (when available) and a 1–3 line explanation referencing core metrics (pot odds, SPR, hand strength, draws).
    - Make AI coach toggleable in the UI (e.g., “Enable AI Coach”) without breaking the numeric Coach panel.
  - Log AI advice events in the client log for debugging and user learning.
- Tests & observability
  - Unit-test prompt construction and response parsing independently of any real provider (using a dummy `AiProvider`).
  - Add logging hooks (backend) to record anonymized decision context + AI advice for spot-checks, respecting privacy and avoiding storage of raw hole cards where not needed.

## V2 — Coach with advice
- Approach A: Search-based advisor (fast approximate)
  - Depth-limited lookahead; opponent range; rollout EV via MC; sizes ∈ {0.33, 0.66, 1.0 pot, all-in}; CFR-lite few iterations under ~200ms budget.
- Approach B: GTO-informed policy
  - Preflop charts (6-max, 100bb) + interpolation by stack; postflop: pre-solved toy trees or offline CFR→small NN policy with bucketing.
- Output
  - Top-2 actions with EV, frequency, confidence, and “Why”. Toggle advice on/off. Advice disabled for bot seats.
- Evaluation
  - A/B vs baseline across large sims; latency budget <150ms incremental.

## V3 — Online multiplayer + powerful bot mixing
- Backend evolution
  - Postgres (users, tables, hands, events); Redis (pub/sub, locks); JWT auth; per-table processes; horizontal scaling; spectating with restricted hole-card visibility.
  - Observability: metrics, tracing; Sentry.
  - Fairness: audited RNG with logged per-hand seeds; anti-collusion signals (IP, timing patterns).
- Frontend
  - Lobby, multi-table routing, reconnect, mobile-friendly; spectate mode; coach as a feature flag.
- Bots
  - Pluggable policies: simple, search-based, CFR/GTO.
- Security
  - Input validation, WS auth, rate limiting, backpressure, DoS protections.
- Compliance
  - Hand histories export; configurable rake; data retention/GDPR.

## Proposed timeline
- Week 1: MVP backend (raise sizing, rotation, showdown winners) + minimal client; stable hand loop; tests.
- Week 2: MVP UX polish (positions, Continue button), deterministic seeds; alpha demo.
- Week 3: V1 coach metrics + structured logging; UI panel; validation tests.
- Week 4: V1.5 LLM Coach (AiCoachService, AiProvider abstraction, `ai_advice` WS message, basic AI Coach UI section, env-based provider selection).
- Week 5–6: V2 advisor A (search/CFR-lite), EV-based action ranking and explanations, perf tuning; explore offline policy experiments.
- Week 7+: V3 foundations (auth, DB, Redis, lobby), multi-table, production hardening.

## Immediate next steps (MVP)
- Implement pot-based raise sizing and validation.
- Emit full showdown with winners via pokerkit best-5; update client log/UI.
- Add button rotation and position labels to snapshots; render in client.
- Add Continue Next Hand flow (REST endpoint + client button); remove auto-advance between hands.
- Update session termination: human busts OR all bots bust OR max_hands.

## Non-goals (MVP)
- No auth, no persistence, no money handling, no rake, no multi-table.
- No action timeouts, no reconnect/diff-resume.

## Glossary
- Snapshot: full seat-filtered table view with seq.
- Prompt: message to the acting seat with legal_actions.
- Legal actions: list emitted by pokerkit, with raise_to candidates derived from pot fractions.
