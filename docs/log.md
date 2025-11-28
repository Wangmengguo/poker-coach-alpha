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

- Frontend beautification plan / MVP alignment:
  - Updated `docs/FRONTEND_BEAUTIFICATION_PLAN.md` Phase 1.5 section to explicitly define MVP scope (P0 card formatting fix + P1 layout/action simplification) and mark P2+ tasks as post‑MVP progressive enhancements.
  - Documented a simplified MVP action bar strategy (retain custom raise + 2–3 core presets, defer slider UX to Phase 2+) and added a Frontend DoD note tying "done" to Phase 1 + P0 + P1 completion.

- Frontend Phase 1 visual baseline completed:
  - Added comprehensive CSS variable system with professional poker palette (felt greens, gold accents, status colors).
  - Implemented distinctive typography: Playfair Display (headers), DM Sans (body), JetBrains Mono (numbers/chips).
  - Added card suit color differentiation (red for hearts/diamonds, black for spades/clubs) via `data-suit` attribute in `renderer.js`.
  - Implemented focus states (`:focus-visible`), high contrast mode support, and `prefers-reduced-motion` accessibility.
  - Optimized responsive layout for tablet/mobile with touch target sizes ≥48px.

- Frontend Phase 1.5 (P0 + P1) completed:
  - **P0 - Card display format fix**: Updated `_card_to_str()` in `poker/engine.py` to extract short codes (e.g., "Ac" from "ACE OF CLUBS (Ac)"). Fixed all 6 locations using `str(c)` for card conversion: `build_table_snapshot` (human/bot holes, cache), showdown player holes, showdown cached holes, and winner best5.
  - **P1 - Player card compactification**: Reduced `.seat` width to 78px, `.player-info` max-width to 82px, shrunk font sizes for name/stack/cards.
  - **P1 - Action bar simplification**: Refactored `actions.js` to show primary actions (Fold/Call) separately from raise section. Added `_filterRaisePresets()` to limit raise buttons to max 3 (min, mid, all-in). Styled with new `.actions-primary`, `.actions-raise`, `.raise-presets`, `.raise-custom` CSS classes.

- Frontend Phase 1.5 (P1 continued) - Action bar Plan B (Slider + Quick Buttons):
  - Rewrote `_buildRaisePresets()` in `actions.js` to generate semantic presets (2x, 3x, Pot, All-in).
  - Implemented slider-based raise UI: `[2x][3x][Pot][All-in] | $min[slider]$max | $amt [Raise]`.
  - Preset buttons update slider value; slider shows real-time amount with fill percentage via CSS variable `--fill-percent`.
  - Optimized layout to single-row flex for compact display; responsive styles for tablet/mobile.

- Frontend Phase 1.5 (P2 + P3) completed:
  - **P2 - Poker table aspect-ratio**: Changed from fixed `width/height` to `aspect-ratio: 16/10` with `max-width: 640px`. Seat positions now use percentage values (e.g., `right: 5%`) for responsive scaling.
  - **P2 - Drawer doesn't overlap main content**: Added `body.drawer-open main { margin-right: 290px }` to push main content when drawer is open. `renderer.js` toggles `drawer-open` class on body in `openDrawer()`/`closeDrawer()`.
  - **P3 - Game Log collapsible**: Converted log section to native `<details>` element with styled `<summary>`. Arrow indicator rotates on open/close via CSS transform.

- Coach drawer toggle fix:
  - Added floating `#drawerOpenBtn` button (📊 Coach) visible when drawer is closed.
  - Button positioned at top-right (desktop) or bottom-right (mobile).
  - Hides automatically when `body.drawer-open` via CSS `opacity: 0; pointer-events: none`.
  - Separated close (×) and open button handlers in `bindDrawerToggle()` to fix reopening bug.

Date: 2025-11-27

- Session controls simplification + auto-join:
  - Removed `Join Table` and `Restart Session` buttons from `public/index.html`, leaving a single primary `Start Session` CTA plus `Next Hand` and reconnect/audio controls.
  - Updated `ActionHandler` in `public/modules/actions.js` to drop `joinBtn`/`restartBtn` wiring, keep a single `startBtn`, and rely on `join()` only programmatically.
  - Added `hasAutoJoined` flag in `public/app.js` and, on `wsManager.on('open')`, automatically call `actionHandler.join()` once so the user is seated at the default table without clicking Join.
  - Adjusted `Renderer.updateSessionInfo()` in `public/modules/renderer.js` to treat `sessionActive` as the single source of truth for showing/hiding `startBtn` and hiding `nextHandBtn` whenever the session is inactive.
  - Tightened `/tables/{table_id}/start` in `app/main.py` to return `400 {"error": "session already active"}` when `engine.session_active` is true so clients must use `/restart` for mid-session resets.

- Coach drawer persistence across hands/sessions:
  - Changed `public/app.js` so `hand_end` and `session_end` handlers no longer call `renderer.closeDrawer()`, allowing the Coach drawer to remain open or closed based solely on explicit user actions.

- Snapshot-aware UI after page reload (no-button bug fix):
  - Extended `TableEngine.build_table_snapshot()` in `poker/engine.py` to include `session_active` and `awaiting_next_hand` flags derived from `session_active` and `is_hand_over()`.
  - Updated `Renderer.renderState()` in `public/modules/renderer.js` to infer `sessionActive` from `table.session_active` instead of always assuming an active session, ensuring `Start Session` reappears when a session is no longer active.
  - Enhanced the `snapshot` handler in `public/app.js` to, after rendering state and clearing analysis, inspect `table.awaiting_next_hand` and `table.legal_actions`:
    - If `awaiting_next_hand` is true, show `Next Hand` so a page refresh at showdown still lets the user continue the session.
    - Else, if there are legal actions and `to_act === 1`, immediately call `actionHandler.renderActions()` so a mid-hand refresh restores the Fold/Call/Raise controls.
  - Together, these changes fix the scenario where reloading the page in a finished hand or between hands left the user with no visible session/next-hand buttons despite being in a valid session.

- Session controls layout alignment:
  - Moved `Start Session` and `Continue Next Hand` buttons from the top `.controls` bar into a new `.session-controls` row inside `.game-controls` in `public/index.html`, directly above the main `#actions` area.
  - Added `.session-controls` styles in `public/style.css` (horizontal flex layout, centered, with small vertical spacing) so session-level controls visually live in the same region as per-hand actions under the table, while the top bar is reserved for connection/audio/utility controls.

- Message queue indicator alignment and button overlap fixes:
  - Fixed queue indicator (⏳) vertical alignment with control buttons by adding `align-items: center` to `.controls` container and setting consistent `height: 44px`, `font-size: 1.1rem` on `.queue-indicator`.
  - Separated hourglass emoji and count number into distinct styled elements (`<span class="queue-count">`) for better visual control.
  - Fixed race condition where Continue button and action buttons (Fold/Call/Raise) could appear simultaneously during queue processing:
    - `renderActions()` in `actions.js` now hides `nextHandBtn` before rendering action buttons.
    - `snapshot` handler in `app.js` now clears action buttons before showing Continue button.

- Message queue count logic improvement:
  - Changed `getStatus()` in `messageQueue.js` to return `actionCount` that only counts `action_taken` messages (actual player moves like fold/call/raise).
  - Excludes `snapshot` (state updates), `hand_end`, `session_end` etc. from the count, so the indicator shows only pending bot actions.

- Message queue animation pacing improvements:
  - Removed special `prompt` handling that was flushing the entire queue, causing bot actions to be skipped. All messages now queue normally so bot action animations play properly before showing user's turn.
  - Added `board_change` delay (1200ms) for community card deals: tracks `_lastBoardLength` in MessageQueue, detects when snapshot contains new board cards (flop/turn/river), and applies longer pause so players can see the new cards.
  - Reset board tracking on `hand_end` to prepare for next hand.

- Action button UX improvement:
  - Clear action buttons immediately in `sendAction()` after user acts (fold/call/raise), so the UI shows blank space while waiting for the hand to continue or end, rather than leaving stale buttons visible.
