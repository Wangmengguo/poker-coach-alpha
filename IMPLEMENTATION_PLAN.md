# Implementation Plan — Real Game MVP updates

This plan details the concrete changes to deliver a more realistic single-table NLHE experience for MVP.

Goals (MVP):
- Pot-based raise options: 1/3, 1/2, 2/3, 1×, 2× pot; enforce min raise; remove 2/4/6 fixed buttons.
- Showdown: reveal all live hands; compute winners via pokerkit best-5 and include in payload.
- Rotation: move button each hand; expose position labels per seat (BTN, SB, BB, UTG, MP, CO) to the client.
- Manual hand progression: a Continue Next Hand button; no auto-advance.
- Session termination: end when human busts OR all bots bust OR max_hands reached; remove auto-refill behavior.

## Protocol and model updates

1) Table snapshot
- Keep existing fields; ensure `button_seat` rotates each hand.
- Optional: include `positions: {"1":"BTN","2":"SB",...}` for 6-max mapping derived from `button_seat`.

2) Legal actions
- Only `check`, `call`, `fold`, and multiple `raise_to` candidates based on pot fractions; no `min/max` range exposure; no fixed +2/+4.

3) Showdown message
- Extend with `winners`:
  - Showdown.winners: [{ seat: int, best5: [str;5], rank: str }]
  - Only include seats still in hand (exclude folded).

4) Hand flow control
- No diff/resume for MVP (snapshots only).
- Add REST: POST /tables/{id}/next → server starts next hand and broadcasts until prompt/hand_end.

## Backend changes

Files:
- poker/engine.py
- app/main.py
- ws/protocol.py

1) Pot-based raise sizing (poker/engine.py)
- Replace `legal_actions` raise candidates with pot-fraction targets.
- Algorithm (for acting index i):
  - to_call = amount needed to call.
  - pot = int(sum(state.pot_amounts)) if available, else derive from stacks/bets.
  - max_bet = max(state.bets).
  - fractions = [1/3, 1/2, 2/3, 1.0, 2.0]. For each f:
    - target_to = max_bet + round((pot + to_call) * f)
    - keep if target_to > max_bet and `_try_raise_to(target_to)` is True.
  - Always de-dup, sort ascending, and include all-in (`_max_bet_to(i)`) if `_try_raise_to` permits and it’s not already present.
- Keep min-raise enforcement by relying on `_try_raise_to` validity from pokerkit.

2) Showdown winners (poker/engine.py)
- At hand end (when `is_hand_over()`), compute winners before emitting `hand_end`:
  - Collect live seats (status True at showdown) and their hole cards.
  - Use pokerkit to evaluate best 5-card hand per seat against the final board.
    - Preferred: `pokerkit.lookups.StandardLookup` or hold’em hand API to obtain (rank_label, best5_cards).
  - Determine winner set (handle splits) and append `winners` into the `showdown` payload.

3) Rotation and positions (poker/engine.py)
- Track `button_seat` across hands; on `start_session()` set an initial button (e.g., 1), and on each `_start_new_hand()` advance `(button_seat % seats) + 1`.
- Add helper to map seats→positions for 6-max ordered as: BTN, SB, BB, UTG, MP, CO.
- Include `button_seat` in snapshots; optionally include `positions` map.

4) No auto-advance; manual next hand
- Change `advance()` so that after emitting `hand_end` (and possibly `session_end`) it does NOT call `_start_new_hand()`.
- Add `start_next_hand()` method which:
  - Validates session is active and not ended; rotates button; creates a new pokerkit state with current stacks; broadcasts initial snapshot/prompt when called.

5) Session termination (poker/engine.py)
- Update `should_end_session()` to return True when:
  - human stack <= 0, OR
  - all bot stacks <= 0, OR
  - hand_index >= max_hands.
- Remove auto-refill: do not force busted seats back to `starting_stack` inside `_start_new_hand()`.
  - If continuing with fewer players is required before final bust condition, seats with 0 stack should be excluded from the next state (optional for MVP; we can end session when any seat reaches 0 for simplicity of MVP if needed, but target the spec above).

6) REST hook to continue (app/main.py)
- Add POST /tables/{id}/next:
  - Calls `engine.start_next_hand()`; then runs `engine.advance(human_seat=1)`; broadcasts messages like `/start`.
  - Returns `{ hand_id }`.
- Guard: return 400 if session inactive or already ended.

7) Protocol schemas (ws/protocol.py)
- Extend `Showdown` Pydantic model with optional `winners: List[{seat:int, best5:List[str], rank:str}]`.
- Optionally extend `TableSnapshot` with optional `positions: Dict[str,str]` (stringified seat → position label).

## Frontend changes

Files:
- public/index.html
- public/app.js
- public/style.css

1) Continue Next Hand button
- Add a header button (id: `nextHandBtn`, label: "Continue Next Hand"). Hidden by default; shown on `hand_end`.
- On click: POST `/tables/default/next`; disable button until next `prompt/snapshot` arrives.

2) Action buttons
- Render whatever `legal_actions` the server sends; there will be multiple `raise_to` amounts (no static 2/4/6).
- Optional: label `raise_to` buttons as `Raise to $X` for MVP; later we can add `(≈ 1/2 pot)` annotations.

3) Showdown rendering
- Log all live hands at showdown; if `winners` present, highlight winners and their best5 and rank.

4) Positions UI
- Show position badge per seat using `table.positions` or by computing from `button_seat`.

## Tests

- tests/test_integration.py
  - Pot-sizing: assert `legal_actions` contains ascending `raise_to` targets for typical states and that `_try_raise_to` accepts them.
  - Showdown: assert `showdown` message includes all live hands and `winners` is non-empty with 5 cards and rank.
  - Rotation: across two hands, `button_seat` increments and positions mapping updates.
  - Continue gating: after `hand_end`, no auto-start; POST `/next` starts new hand.
  - Session termination: session ends when human stack <= 0 or all bots <= 0 or `max_hands` reached.

## Acceptance
- The UI offers pot-based raise options; showdown shows all hands; winners and best5 are visible; button rotates; positions are shown; next hand only proceeds via the Continue button; session ends per rules.

## Notes / Risks
- pokerkit best-5 API surface may vary by version: isolate winner computation in a helper with try/fallbacks.
- If pokerkit requires positive stacks for state creation, ensure we don’t start a new hand when a termination condition is met (eliminates need to represent 0-stack seats in MVP).