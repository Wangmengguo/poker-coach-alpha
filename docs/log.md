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
