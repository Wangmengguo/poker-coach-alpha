# Log

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

Date: 2025-11-28

- V1.5 AI Coach backend integration:
  - Added `poker/ai_coach.py` with `AiAdvice` dataclass, heuristic-based action selection (using `DecisionContext.hand_strength_pct` vs `required_equity_pct`), and a pluggable `AiProvider` interface.
  - Introduced LiteLLM-backed `LitellmProvider` plus `DummyProvider`; provider selection is controlled via `AI_PROVIDER` env (e.g., `openai` vs `dummy`) and standard LiteLLM env vars (such as `OPENAI_API_KEY` / `OPENAI_API_BASE` for OpenAI-compatible gateways).
  - Defined whitelisted model aliases (`fast`, `strong`, `cheap`) mapped to concrete LiteLLM model ids in `ALLOWED_MODELS`, with helpers to get/set the current alias (`get_current_model_alias`, `set_current_model_alias`).
  - Updated `generate_ai_advice(...)` so that the LLM is used to generate natural-language explanations, while action selection remains purely heuristic and safe; on errors or misconfiguration, the coach falls back to heuristics only.
- AI advice protocol and FastAPI wiring:
  - Extended `ws/protocol.py` with `AiAdvicePayload` and `AiAdviceUpdate` types and added `ai_advice` to the `ServerMessage` union.
  - In `app/main.py`, added `_broadcast_ai_advice(...)` which builds a `DecisionContext` via `compose_analysis`, computes advice via `generate_ai_advice`, and broadcasts `ai_advice` messages whenever a human `prompt` is emitted or on reconnect when it is the human’s turn.
  - Introduced `/settings/ai_model` REST endpoints (`GET` to inspect current alias and allowed list, `POST` to change alias) to support runtime model switching during development and testing.
- Frontend AI Coach UI:
  - Extended the Coach drawer in `public/index.html` and `public/modules/renderer.js` with an “AI Coach” section that displays the recommended action, optional secondary action, confidence (as a percentage), and explanation text when available.
  - Updated `public/modules/state.js` and `public/app.js` to track `ai_advice` in `GameState.analysis` and handle `ai_advice` WebSocket messages, logging explanations for debugging.
- Model alias configuration for OpenAI-compatible gateway:
  - Replaced generic `fast/strong/cheap` aliases with real model names in `ALLOWED_MODELS` (e.g., `claude-4.5-sonnet`, `gpt-5.1-chat-latest`, `deepseek-chat`, `deepseek-reasoner`, `moonshotai/kimi-k2-instruct`, `kimi-k2-thinking`, `gemini-3-pro-preview`), keeping keys and underlying model ids identical so the UI and `/settings/ai_model` always expose the true model identifier used by the gateway.
  - Documented AI Coach / LiteLLM configuration in `README.md`, including environment variables (`AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_API_BASE`, `AI_MODEL_ALIAS`), the heuristic/LLM modes, and the `/settings/ai_model` endpoint for runtime model switching.
- LLM context refinement and model selector UI:
  - Extended `DecisionContext` with `hero_cards` and `board_cards`, and wired them from PokerKit state via `compose_analysis`, so the LLM sees HERO hole cards and the public board while never seeing opponents’ hidden cards.
  - Added per-hand `action_history` tracking to `TableEngine` (seat, position, street, action_type, amount, to_call_before) and included a compact recent history summary in the LLM prompt, giving better context about how the pot was built.
  - Implemented Plan B in `poker/ai_coach.py`: the LLM now returns a JSON object with `recommended`, `secondary`, `confidence`, and `explanation`; `_parse_llm_json` and `_match_action_spec` map these to current `legal_actions`, and the coach prefers LLM-selected actions when they are legal, falling back to heuristic actions otherwise.
  - Added `players_count` to the LLM context so the model can distinguish heads-up from multiway pots in a lightweight way.
  - Implemented a model selector UI in `public/index.html` / `public/style.css` / `public/app.js`: a compact “Model” pill with a `<select>` populated from `/settings/ai_model`, allowing runtime switching between configured models (e.g., `claude-4.5-sonnet`, `deepseek-chat`, `gpt-5.1-chat-latest`) with changes logged in the Game Log.

Date: 2025-12-06

- AI model configuration and tooling updates:
  - Simplified and refreshed `ALLOWED_MODELS` in `poker/ai_coach.py` to reflect the current OpenAI-compatible gateway setup (e.g., `claude-4.5-sonnet`, `claude-opus-4-5`, `moonshotai/kimi-k2-instruct`, `gpt-5.1-chat-latest`, `deepseek-chat`, `grok-4-fast-reasoning`) and removed unstable/unavailable entries.
  - Renamed the LiteLLM-era test script to `test_ai_models.py` and updated messaging so it validates direct gateway calls (`AI_PROVIDER=openai/gateway` + `OPENAI_API_BASE/OPENAI_API_URL`) against the current model whitelist.
- LLM coach prompt and protocol redesign:
  - Switched the coach protocol to an id-based action selection schema: `build_prompt(...)` now serializes `legal_actions` as a JSON array with explicit integer `id`s and type/amount/min/max metadata, and the model is instructed to respond with `recommended_id` / `secondary_id` instead of hand-crafted `{type, amount}` specs.
  - Simplified `_parse_llm_json(...)` to resolve `recommended_id` and `secondary_id` directly into `legal_actions[idx]`, removing the older type/amount matching path and making the mapping between LLM output and engine actions deterministic and robust.
  - Enriched the prompt with clearer strategy framing (6-max 1/2 cash game, 50–200bb, long-term EV focus) and tightened output rules (JSON-only, 1–2 sentence explanation, secondary action used as a more conservative backup line).
  - Added an equity edge summary to `_format_core_metrics(...)`: when both `hand_strength_pct` and `required_equity_pct` are available, the context string now includes `Equity edge vs pot odds: +X%/-Y%` so the model can see at a glance how far above/below break-even the current spot is.
- LLM-only advice path and bot wrapper:
  - Added `generate_llm_actions_only(...)` to `poker/ai_coach.py`, a variant of `generate_ai_advice` that:
    - Calls the provider with a per-decision timeout (configurable, default ~5s) via `asyncio.wait_for`.
    - Parses the JSON using the new id-based schema.
    - On timeout, network/API error, or parse failure, returns an `AiAdvice` with `recommended_action=None` and a descriptive `reason` (`llm_timeout`, `llm_error`, `llm_parse_failed`) without falling back to heuristic actions, leaving fallback behavior to callers.
  - Introduced `poker/llm_bot.py` with `LlmBot`, an LLM-driven bot wrapper that:
    - Uses `compose_analysis(...)` to build a `DecisionContext` for the acting seat.
    - Calls `generate_llm_actions_only(...)` to obtain LLM advice and records whether the decision was LLM-driven or fell back.
    - Applies a safe fallback when LLM output is unusable (prefer `check` when `to_call == 0`, else `fold`, else `call`, else the first legal action), returning a structured `LlmDecisionResult` with `llm_failed` flag and optional `AiAdvice`.
- Offline LLM vs bot simulation tooling:
  - Added `tools/run_llm_simulation.py`, a CLI script to run offline simulations where a single LLM-controlled seat (via `LlmBot`) plays against existing `EquityBot` opponents using the real `TableEngine`:
    - Arguments: `--model-alias`, `--num-hands`, `--seed`, `--llm-timeout-seconds`, `--csv-output`.
    - Ensures the repo’s local `poker` package is used (prepends project root to `sys.path`) and refuses to run when `get_ai_provider_from_env()` resolves to `DummyProvider`.
    - For each hand, repeatedly calls `engine.advance(human_seat)` and:
      - Injects LLM decisions when it is the human/LLM seat’s turn.
      - Uses `EquityBot` for all other bot seats.
      - Tracks per-hand hero deltas from `hand_end.results` and counts per-hand LLM failures.
    - Prints per-hand progress (`[SIM] Hand X/Y started/finished: delta=..., llm_failures=...`) and session-level metrics (hands played, total net chips, BB/100, total LLM decision failures).
    - Optionally writes per-hand results (`hand_index`, `net_chips`, `llm_failures`) to a CSV file under a `logs/` directory for later analysis.
- Preflop raise sizing and legal action improvements:
  - Refactored `TableEngine.legal_actions()` to introduce a dedicated `_preflop_raise_candidates(...)` path:
    - In unopened or blinds-only pots (preflop with `max_bet <= bb`), generate standard open sizes based on big blind multiples (e.g., ~2.5x, 3x, 4x) plus an all-in candidate, validating each via `_try_raise_to`.
    - When facing a preflop raise (`max_bet > bb`), generate a small set of 3-bet/4-bet candidates as multiples of the amount to call on top of the current max bet (e.g., ~2x, 2.5x, 3x of `to_call`), plus all-in.
  - Kept postflop raise sizing on the existing pot-fraction basis (1/3, 1/2, 2/3, 1x, 2x pot plus all-in), ensuring that:
    - Preflop `legal_actions` now expose more natural raise options (2.5x/3x/4x opens and simple 3-bet sizes) alongside a validated `{"type": "raise_to", "min": ..., "max": ...}` range.
    - The LLM (and any future UI) can choose between realistic preflop raise sizes while still having access to a conservative continuous range for fine-tuning.

Date: 2025-12-13

- Frontend raise presets aligned with backend / coach sizing:
  - Rewrote `_buildRaisePresets` in `public/modules/actions.js` to derive all preset raise amounts directly from `legal_actions` and classify them using the same sizing logic as the engine:
    - Preflop open spots (unraised pots with `max_bet <= bb`) now map fixed `raise_to.amount` values to BB-multiple labels (`2.5x`, `3x`, `4x`) based on `amount / bb`, picking the closest candidate for each label.
    - Preflop vs-raise spots (`max_bet > bb`) map fixed `raise_to.amount` values to multiples of the amount to call (`2x`, `2.5x`, `3x`) via `(amount - max_bet) / to_call`, again choosing the closest candidate per label.
    - Postflop raise candidates are classified by pot fractions (`1/3 pot`, `1/2 pot`, `2/3 pot`, `Pot`, `2x pot`) using `(amount - max_bet) / (pot + to_call)`, so UI labels match the coach’s underlying 1/3–2x pot sizing family.
  - Always surface an explicit `All-in` preset based on the validated `{"type": "raise_to", "min": ..., "max": ...}` range (`max` becomes the All-in amount), while excluding that amount from the other preset buckets.
- Postflop preset UX compaction:
  - Updated the raise presets rendering in `public/modules/actions.js` so that on postflop streets only a few core presets are shown inline (up to three primary sizes plus `All-in`), and any additional classified presets are hidden behind a `More`/`Less` toggle button that expands or collapses the extra raise buttons in place.
  - Preflop keeps all available presets visible (2.5x/3x/4x or 2x/2.5x/3x plus All-in) to emphasize the limited but meaningful open/3-bet sizing choices commonly used by the coach.

- Frontend raise UI collapsible custom controls:
  - Refactored raise action section in `public/modules/actions.js` to address UI bloat concerns: preset buttons (`2.5x`, `3x`, `Pot`, `All-in`) now directly submit raise actions on click, while the custom slider + amount display + submit button are collapsed into a `Custom...` toggle.
  - Default collapsed state shows a single row: `[Fold] [Call $X] [Preset1] [Preset2] [Preset3] [All-in] [Custom...]`.
  - Clicking `Custom...` expands a secondary section with the slider control (`$min [slider] $max`), real-time amount display, and a `Raise` submit button; button label changes to `Hide` when expanded and auto-focuses the slider for keyboard users.
  - Updated `public/style.css` with new classes (`.raise-custom-toggle`, `.raise-custom-section`) and a `slideDown` animation; custom section displays as a bordered, semi-transparent panel below the preset row.
  - Optimized responsive styles for tablet/mobile to maintain compact layout and appropriate touch target sizes (≥40px on touch devices).
  - Result: reduced action bar from 3–4 rows to 1 row (collapsed) or 2 rows (expanded), significantly improving visual clarity without losing functionality.

- AI Coach model support + gateway robustness:
  - Extended `poker/ai_coach.py` model whitelist to include `gpt-5.2` and `gpt-5.2-pro` (removed the incorrect `gpt-5.2-chat-latest` alias) and added lightweight tests to ensure aliases are present and switchable.
  - Hardened LLM output parsing to reduce false fallbacks: extract the first balanced `{...}` object from mixed text/code-fences and accept python-literal-ish dict outputs via `ast.literal_eval` as a backup when strict JSON fails.
  - Improved fallback diagnostics by replacing the generic `heuristic` reason with explicit reasons (`dummy_provider`, `llm_empty_response`, `llm_parse_failed_heuristic_actions`, `llm_error_heuristic_actions`) so UI payloads reveal why the LLM wasn’t used.
  - Investigated `gpt-5.2` returning empty `message.content` with `finish_reason=length` and fixed it by increasing `max_tokens` and automatically retrying via the Responses API when chat completions produce an empty content string.
  - Increased `chat.completions` `max_tokens` from 512 to 1024 and Responses fallback `max_output_tokens` from 512 to 1024 to further reduce truncation on platforms where `gpt-5.2` can consume token budget without emitting a final JSON payload.
  - Added an opt-in `AI_COACH_DEBUG=1` mode to print per-request extraction diagnostics (finish_reason, content type/length, and whether Responses fallback was used) to accelerate gateway troubleshooting.

Date: 2025-12-15

- LLM toggle isolation per browser session:
  - Added "per-browser isolated" LLM toggle: disabled by default, so even if `OPENAI_API_KEY` is configured on the backend, paid models are not automatically invoked.
  - Backend now maintains `client_settings` (`llm_enabled` / `model_alias`) per WebSocket connection; LLM is called only when that connection has it enabled, otherwise returns heuristic advice with `reason=client_disabled_llm`.
  - Implemented on-demand paid call endpoint: `POST /tables/{table_id}/ai_advice/llm` (frontend triggers one call per `Ask once` click).
  - Frontend added `LLM` toggle and `Ask once` button; settings persisted to `localStorage` (browser-level) and synced to backend via WS.
  - Added `use_model_alias(...)` concurrency lock to prevent model aliasing conflicts during concurrent calls.
  - UI: Changed `LLM` toggle to a toggle-switch style; renamed `Ask` to `Ask once`.
  - UI: Added interaction feedback for `Ask once` (loading spinner / Done / Failed), disabled repeat clicks, and added 15s timeout.
  - Self-check: `pytest -q` (53 passed).

- Frontend table layout + bet label improvements:
  - Fixed overlap between right-side seats (SB/BB) by increasing separation in CSS seat positioning:
    - Adjusted `.seat-2` and `.seat-3` in `public/style.css` so the two player cards no longer stack on top of each other.
  - Moved per-player bet amount (`.player-bet`) out of the player info card to better use empty felt space:
    - Updated `public/index.html` so each `.seat` contains a sibling `.player-bet` element (no longer inside `.player-info`).
    - Updated `public/modules/renderer.js` to query bet elements from the seat container (`container.querySelector('.player-bet')`).
  - Repositioned bet labels closer to the table (toward the center) without cluttering the player card:
    - `.player-bet` is now absolutely positioned, uses CSS variables `--bet-x/--bet-y`, and applies per-seat offsets in `public/style.css` so bet amounts appear near the table edge for each seat.

Date: 2025-12-20

- AI Coach model whitelist:
  - Added `gemini-3-flash-preview` to `poker/ai_coach.py` `ALLOWED_MODELS` so it can be selected via `AI_MODEL_ALIAS` / `/settings/ai_model`.
  - Updated `README.md` model list and extended `tests/test_ai_coach_models.py` to cover the new alias.

- Frontend card rendering: text -> minimal SVG (readability-first):
  - Inlined an SVG suit sprite in `public/index.html` (4 symbols: `suit-heart`, `suit-diamond`, `suit-club`, `suit-spade`) so cards can reference local `#suit-*` via `<use>` without extra fetches or cross-file `<use>` issues.
  - Updated `public/modules/renderer.js` to render cards as SVG instead of text:
    - Added `_parseCard(...)` to support `Ah/Kd/10h/Ts/??` and normalize `T -> 10` display.
    - Added `_makeCardSvg(rank, suit)` to draw only top-left rank + a large center suit symbol (no bottom-right).
    - Replaced all card `textContent` rendering in board / hole / showdown paths with the SVG renderer; kept `??` as face-down via `.card.hidden`.
  - Updated `public/style.css` to support SVG card layout and readability:
    - `.card` becomes a fixed-size SVG container; `.card-svg` fills 100%.
    - Rank uses `var(--font-mono)` and `tabular-nums`, and uses `paint-order: stroke fill` with a light stroke to stay legible at small sizes.
    - Added hand-only overrides (`.player-cards ...`) to further boost rank size and suit scale without increasing card box size; board sizing kept stable.
  - Follow-up tweaks for alignment and readability:
    - Updated `public/modules/renderer.js` rank positioning to use a fixed `x` and `dominant-baseline="hanging"` so rank top alignment stays consistent.
    - Removed the special-case `10` font-size overrides in `public/style.css`; `10` now keeps the same font-size as other ranks and uses tighter `letter-spacing` to fit, ensuring baseline/height consistency across ranks.

- Frontend feel + depth (core hand feedback + visual polish):
  - Renderer diff-based micro-animations:
    - Added lightweight render caches in `public/modules/renderer.js` (last board/pot/bets/to_act/hand_id) so animations trigger only on state changes and reset cleanly per hand.
    - Added prefers-reduced-motion-aware helpers for one-shot bumps and number tweening.
  - Board deal-in animation:
    - New community cards now animate in (deal-in) via `.card.deal-in` / `.deal-in-active` and a requestAnimationFrame class toggle in `public/modules/renderer.js`.
  - Pot feedback:
    - Pot amount now “bumps” and smoothly counts to the new value on changes (`.pot-bump` + JS tween), while respecting reduced-motion preferences.
  - Bet label polish:
    - Updated `.player-bet` styling to feel like a chip pill (glass/highlight + shadow) and added `bet-pop` (appear) / `bet-bump` (value change) animations.
  - Turn indicator (no timer):
    - Enhanced `.player-info.active` with a pulsing ring to make “who’s to act” obvious without introducing an inaccurate countdown.
  - Message queue pacing:
    - Tweaked `public/modules/messageQueue.js` default delays (slightly faster `action_taken`/`snapshot`, still-paused `board_change`) so new animations have time to read without slowing the game too much.
  - Table texture + glass panels:
    - Added subtle felt texture + vignette to `.poker-table` using pseudo-elements, plus z-index isolation to keep overlays behind content.
    - Added optional glassmorphism (`backdrop-filter` with fallback) to `.pot-info`, `.model-selector`, `.llm-controls`, and `.drawer-section-body`.
  - Card polish:
    - Improved `.card` borders/highlights and added a simple patterned back for `.card.hidden`.

Date: 2025-12-30

- Deployment / subpath isolation (MVP):
  - Added configurable backend path prefix via `APP_PREFIX` (default `/cards`) and exposed a fully-isolated route set under the prefix:
    - HTML entry: `GET /cards/` (plus `GET /cards` redirect to `/cards/`).
    - Static assets: `/cards/public/...` mounted alongside the existing `/public/...` for backwards compatibility.
    - REST: `/cards/tables...`, `/cards/settings...` in addition to the existing root routes.
    - WebSocket: `/cards/ws/tables/{table_id}` in addition to the existing `/ws/...` route.
  - Frontend routing/base-path hardening:
    - Removed hardcoded `/cards` base from `public/index.html` and switched asset URLs to relative paths so the same build works under `/` or any subpath.
    - Updated frontend to infer base path from the current URL (first path segment) when `<meta name="app-base">` is empty, avoiding 404s when `APP_PREFIX` is not `/cards` (e.g. `/poker`).
    - Centralized path building helpers (`withBase`, `wsAbsoluteUrl`) and migrated all REST fetches, audio file URLs, and WebSocket URL construction to use them.
    - Fixed HTTPS mixed-content by switching WS scheme automatically (`ws://` vs `wss://`) based on `location.protocol`.
  - Notes:
    - Existing root routes are kept for local dev/tests; isolation is achieved at the reverse-proxy layer by only exposing the `/cards/...` routes.
    - Lints checked for touched files; no issues. Pytest was not runnable on this machine (pytest not installed).

Date: 2026-01-24

- Invite code system (API protection for paid LLM calls):
  - Added `poker/invite_codes.py` with `InviteCodeStore` (SQLite-backed) to create/list/revoke/validate invite codes; stores data in `DATA_DIR` (default `./data`) and updates `last_used_at` on successful validation.
  - Added CLI tooling `tools/manage_invites.py`:
    - `create --note ...`, `list`, `revoke <CODE>`, `check <CODE>`.
- Backend gating for AI Coach LLM usage:
  - Updated `app/main.py` WebSocket `client_settings` flow to accept `invite_code` and return `client_settings_ack` with `invite_valid`.
  - Updated `_broadcast_ai_advice(...)` to only call the LLM when `llm_enabled` is true, provider is configured, and `invite_valid` is true; otherwise falls back to heuristic advice with `reason=invite_code_required` (or existing reasons).
  - Updated `POST /tables/{table_id}/ai_advice/llm` to require `invite_code` (returns `403 {"error":"invite_code_required"}` when missing/invalid).
- Frontend invite code UX:
  - Updated `public/index.html` / `public/style.css` / `public/app.js` to add an Invite input pill, persist it in `localStorage`, send it via `client_settings`, and show validation status (✓/✗/…).
  - Updated `Ask once` paid-call request to include `invite_code` in the POST body.
- Docker deployment support:
  - Added `Dockerfile`, `docker-compose.yml`, and `.env.example` for 2C2G deployment with persistent `./data` volume and env-based AI provider configuration.
  - Updated `.gitignore` to ignore `data/` (SQLite persistence) and `.env`.
- Self-check:
  - `pytest -q` (53 passed).

- Invite code / Docker deploy hardening (follow-up):
  - Fixed async-path invite validation in `app/main.py` by offloading SQLite validation to a thread (`anyio.to_thread.run_sync`) and re-validating per WS advice broadcast so revoked codes stop working without reconnect.
  - Reduced SQLite write amplification: `InviteCodeStore.validate_code(...)` now rate-limits `last_used_at` updates (at most once per minute per code).
  - Docker safety + correctness:
    - `Dockerfile` now installs `build-essential` to avoid build failures when wheels need compilation.
    - `docker-compose.yml` now binds to `127.0.0.1:8010` by default (configurable via `POKER_BIND_ADDR`) to avoid exposing port 8010 publicly when using Nginx.
    - `.env.example` no longer uses key-shaped placeholders; added `POKER_BIND_ADDR` and clarified default `AI_PROVIDER=dummy`.
  - Docs updates:
    - Expanded `docs/DEPLOY_EXPLAIN1THING_TOP_CARDS.md` with Docker + "directly enable LLM" steps (`AI_PROVIDER=openai`, `.env` permissions), plus an end-to-end "LLM + invite" verification checklist.
  - Tooling/compat:
    - Updated `uv.lock` `requires-python` to `>=3.10` to match repo/runtime expectations.
  - Self-check:
    - `.venv/bin/pytest -q` (53 passed).

- MVP hardening plan (pre-cloud rollout):
  - Updated `PLAN.md` with a new "MVP hardening" section that prioritizes:
    - 1) per-table `asyncio.Lock` to serialize *all* state mutations across WS actions, REST lifecycle endpoints, and bot turns.
    - 2) a Docker + LLM + invite end-to-end rollout checklist with concrete smoke tests.
  - Added explicit acceptance criteria to the plan:
    - Concurrency: no interleaved state mutations, resilient under multi-client spam, idempotent `action_id` preserved, plus a new concurrent-actions integration test.
    - Deployment: `llm_available=true` check, invite required/valid paths, revoke takes effect, and `./data/invites.db` persists across restarts.

- P0: Per-table lock implementation:
  - Added `_table_locks: Dict[str, asyncio.Lock]` and `_get_table_lock(table_id)` helper using `setdefault` pattern.
  - Converted REST endpoints `/start`, `/next`, `/restart` from sync `def` to `async def`.
  - Removed `anyio.from_thread.run(...)` calls; now use direct `await manager.broadcast()` and `asyncio.create_task()`.
  - Lock coverage:
    - `/start`, `/next`, `/restart`: lock inside for state mutation, broadcast outside.
    - WS `action` handling: lock inside for validate→apply→advance, broadcast outside.
    - `_broadcast_ai_advice`, `_broadcast_hand_strength`: lock inside for `next_sequence()` and state reads, LLM/compute/broadcast outside.
  - Added note in code: "Only works with --workers 1 (single process)."
  - Added `tests/test_concurrent_actions.py` with 10 tests covering lock creation, reuse, sequential operations, and idempotency.
  - Self-check: `pytest -q` (63 passed).

- P1: E2E check script:
  - Created `tools/e2e_check.py` with full verification flow:
    - Health check (`GET /`), AI model settings, start session.
    - WS snapshot and invite validation (requires `websockets` package).
    - LLM REST advice with/without invite code, revoke invalidation check.
  - CLI options: `--base-url`, `--timeout`, `--skip-llm`, `--skip-ws`, `-v/--verbose`.
  - Important caveat documented: script must run on same machine/container (SQLite access).
  - Usage: `python -m tools.e2e_check` or `docker compose exec poker python -m tools.e2e_check`.

- Follow-up fixes (verification pass):
  - Fixed `tools/e2e_check.py` WS invite validation to ignore interleaved `analysis/ai_advice` messages and wait for `client_settings_ack`.
  - Locked `POST /tables/{table_id}/ai_advice/llm` seq generation (`engine.next_sequence()`) and moved state reads under per-table lock (LLM call remains outside lock).
  - Self-check: `pytest -q` (65 passed); `python -m tools.e2e_check` passes against a local dummy-provider server.

- MVP hardening execution + review-team amendments (P0/P1):
  - Agent implementation (initial):
    - Implemented per-table lock (`_table_locks` + `_get_table_lock(table_id)`) to serialize all in-memory engine mutations for a single table.
    - Converted state-mutating REST endpoints to `async def` and ensured: mutate under lock, broadcast outside lock:
      - `POST /tables/{id}/start`, `POST /tables/{id}/next`, `POST /tables/{id}/restart`.
    - Updated WS action path to do: validate/apply/advance under lock, broadcast outside lock.
    - Updated `_broadcast_ai_advice` / `_broadcast_hand_strength` to acquire seq/state under lock, and keep LLM/compute/send outside lock.
    - Added `tools/e2e_check.py` to standardize pre-rollout checks (health, WS snapshot, invite validation, LLM REST gating, revoke invalidation).
    - Added test coverage for lock/idempotency behaviors in `tests/test_concurrent_actions.py`.
  - Dev/Review team fixes (stability + completeness):
    - Fixed `tools/e2e_check.py` to ignore interleaved WS messages and wait for `client_settings_ack` (protocol-level stability).
    - Fixed `POST /tables/{id}/ai_advice/llm` to avoid `engine.next_sequence()` outside lock by moving seq generation (and state reads) under the per-table lock while keeping the LLM call outside lock.
    - Updated concurrency-oriented tests to use `httpx.AsyncClient` + `ASGITransport` where appropriate, improving determinism of acceptance checks.
  - Verified in workspace:
    - Tests: `.venv/bin/pytest -q` (65 passed).
    - E2E (dummy provider server): `python -m tools.e2e_check --base-url http://127.0.0.1:8012/cards` (passes; LLM checks are skip/ok under dummy provider).
