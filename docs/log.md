# Work Log

Date: 2025-11-22

- Phase 1 (P0) completed:
  - Fixed call EV to return net EV; `compute_pot_math` now exposes `effective_stack`; added pot_odds computation and front-end display; engine injects `compose_analysis` payload into Prompt.
- Phase 2 partially done:
  - Added `DecisionContext` / `compose_analysis`, wired into engine; added a minimal integration test; kept outs as dict for UI compatibility.
- Phase 3 bootstrapped:
  - Added `ranges.py` with non-empty default ranges; implemented `compute_equity_vs_range` (HU Monte Carlo vs range) plus a basic test (AA vs 72o).
- Tests:
  - New/updated tests added; pytest not run on this machine (pytest not installed).

- Outs / draws fixes (MVP):
  - Updated `compute_outs` to add a simple gutshot detection (4 outs when hero+board are one rank short of a 5-long straight window involving hero), restrict draw detection to flop/turn only, and include a `gutshot` flag in the outs payload; added `test_compute_outs_gutshot_simple` to cover the 78 vs TJ gutshot scenario.

Date: 2025-11-25

- Frontend Phase 1 modularization and UX polish:
  - Split `public/app.js` into ES modules: `modules/websocket.js` (WebSocketManager), `modules/state.js` (GameState), `modules/renderer.js` (DOM rendering + analysis drawer + showdown highlighting), `modules/actions.js` (REST + action wiring), `modules/analysis.js` (AnalysisDrawer), plus `utils/dom.js` and `utils/constants.js`.
  - Implemented basic WebSocket reconnect manager with event callbacks and wired `snapshot/prompt/showdown/hand_end/session_end/analysis` handling through the new modules.
  - Optimized DOM access by caching high‑frequency elements (seats, pot/board/street, controls, analysis drawer) in Renderer; higher‑order render queues are explicitly deferred to later phases.
- Frontend connection state and accessibility:
  - Added a visible connection status chip in the header (`Connecting/Connected/Reconnecting/Failed/Disconnected`) driven by WebSocketManager events and GameState.connection.
  - Added an `srAnnouncer` aria‑live region and `Renderer.announce` to narrate key events (connect/disconnect, your turn, hand/session end, errors) for screen readers.
  - Enriched action and control buttons with `aria-label` attributes, including custom raise input/button, without changing interaction behavior.
- Table positions fix:
  - Updated `PokerEngine._positions_map` to assign BTN/SB/BB/UTG/MP/CO only to active seats (positive stacks) by rotating over `_active_seats()` from `button_seat`, so busted players no longer show SB/BB in the client while still appearing as $0 seats.
