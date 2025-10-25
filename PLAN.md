# Poker Coach Alpha — Roadmap and Technical Plan

This document captures the staged plan from MVP to V3, with concrete interfaces, data structures, and deliverables.

## Phase 0 — Tech stack and principles
- Stack: FastAPI + WebSocket (Python), pokerkit for rules/engine, simple Python bots, static client (vanilla HTML or React). In-memory state for MVP; add Postgres/Redis later.
- Principles: server is source of truth; per-table lock; event-sourced state with snapshots + diffs; idempotent actions (action_id); deterministic RNG seeds per hand for auditability.

## MVP — Single-table NLHE (1 human + bots)
- Scope
  - Game: No-Limit Texas Hold’em, 6-max, fixed blinds/antes, no rake.
  - Session stop: human busts OR max_hands reached.
  - Table: 1 in-memory table; 1 human seat; remaining seats auto-filled by server bots.
  - Bots: must choose from pokerkit-provided legal actions; simple policy (pot-odds-aware call/fold, small random raises within allowed bounds).
  - UX: single page; join seat; render stacks/board/pot; show hole cards; choose among prompted legal actions; session progress panel.

- Backend components
  - TableService: wraps pokerkit engine; owns TableState {players, stacks, button, board, pot, street, to_act, legal_actions, seq}.
  - SessionManager: runs the hand loop, enforces session termination conditions, manages RNG seed per hand.
  - ActionRouter: WebSocket handler per table; enforces per-table lock; validates actions; advances engine; broadcasts snapshot/diffs.
  - BotManager: executes bot turns (immediate or with small delay) when to_act is a bot.
  - Clock: per-action deadline (e.g., 15s); folds on timeout.
  - Serializer: seat-aware view, snapshot + diff with monotonically increasing seq; supports resume_from_seq.

- API surface
  - REST
    - POST /tables → {table_id} (MVP: returns "default")
    - POST /tables/{id}/join → {player_id, seat}
    - POST /tables/{id}/start → {hand_id}
    - GET /tables/{id}/state → snapshot (for initial load/reconnect)
  - WebSocket
    - /ws/tables/{id}?player_id=...
    - Server→client messages: `snapshot`, `diff`, `prompt`, `hand_end`, `session_end`, `error`
    - Client→server messages: `action`, `resume`

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
    "players": [{"seat":1,"id":"p1","stack":198,"in_hand":true}, {"seat":2,"id":"bot2","stack":202,"in_hand":true}],
    "street": "flop",
    "board": ["Ah","7d","2c"],
    "pot": 15,
    "bets": {"1": 4, "2": 2},
    "to_act": 1,
    "legal_actions": [
      {"type":"fold"},
      {"type":"call","amount":2},
      {"type":"raise","min":6,"max":200}
    ]
  }
}
```
```json
{ "type":"prompt", "seq":43, "to_act":1, "deadline":"2025-10-25T05:12:00Z", "legal_actions":[{"type":"fold"},{"type":"call","amount":2},{"type":"raise","min":6,"max":200}] }
```
```json
{ "type":"action", "action_id":"c3f1", "hand_id":"h_00123", "seat":1, "action":{"type":"raise","amount":10} }
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
     - If `to_act` is bot: BotManager picks from `legal_actions` (policy bounded by min/max constraints) and applies.
     - If `to_act` is human: send `prompt`, await WS `action`; check idempotency by `action_id`; validate against `legal_actions`; apply.
     - After each state change: broadcast `diff` (or snapshot initially).
  4. On `hand_end`: update stacks, move button; check session stop; either emit `session_end` or start next hand.
  5. Reconnect: client GET state, then WS `{type:"resume", from_seq}` to receive missed diffs.

- Acceptance criteria
  - Continuous play vs bots until session end; no illegal actions; handles all-ins, side pots, split pots; action timeouts fold; reconnect from snapshot + diffs works.

- Test plan
  - Unit: action validation, idempotency, timeout fold, side pot math, split pots.
  - Integration: scripted WS session covering a full hand; property tests with randomized seeds.

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
- Client UX
  - Coach panel shows win%, pot-win%, hand strength rank, outs, pot odds, SPR.
  - No advice; descriptive only.
- Tests
  - Validate equity against known calculators for sampled states; snapshot tests for UI.

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
  - Observability: structured logs, metrics, tracing; Sentry.
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
- Week 1: MVP backend (TableService, bots, WS protocol) + minimal client; stable hand loop; tests.
- Week 2: UX polish, reconnect/timeouts, deterministic seeds, logging; Docker packaging; alpha demo.
- Week 3: V1 coach metrics + caching; UI panel; validation tests.
- Week 4–6: V2 advisor A (search/CFR-lite), explanations, perf tuning; explore offline policy experiments.
- Week 7+: V3 foundations (auth, DB, Redis, lobby), multi-table, production hardening.

## Immediate next steps (MVP)
- Confirm MVP parameters:
  - Blinds: default 1/2
  - Starting stack: default 200bb (400 chips)
  - Max hands per session: default 100
  - Action timeout: default 15s
- Scaffold FastAPI app, WS protocol, pokerkit wrapper, bots, and a tiny client.
- Implement per-table lock, idempotent actions, deterministic RNG per hand.
- Write integration test that plays a full hand (human scripted) vs bots.

## Non-goals (MVP)
- No auth, no persistence, no money handling, no rake, no multi-table.

## Glossary
- Snapshot: full seat-filtered table view with seq.
- Diff: minimal change set since prior seq.
- Prompt: message to the acting seat with legal_actions and deadline.
- Legal actions: list emitted by pokerkit, optionally with sizing bounds for raises.
