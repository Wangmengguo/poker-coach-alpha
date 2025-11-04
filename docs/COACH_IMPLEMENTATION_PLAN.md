# Poker Coach Implementation Plan

**Status:** In Progress  
**Version:** 1.1  
**Last Updated:** 2025-10-31

---

## 1. Overview

This document specifies the current plan for delivering real-time coaching features. The design is strictly based on PokerKit for equity/odds calculations (including multiway), a drawer-style UI, and an incremental integration that prioritizes user-visible value with minimal risk.

Goals:
- Show core decision math in real time (pot odds, required equity, SPR).
- Provide hand description and board texture tags.
- Compute hero equity using PokerKit against configurable villain ranges, supporting multiway.
- Infer opponent style using a Tight/Loose × Aggressive/Passive model from in-session stats.
- Keep server authoritative, compute only when necessary, and maintain clean, modular code.

---

## 2. Key Metrics for No-Limit Hold’em

### 2.1 Core Decision Math (always visible when hero acts)

| Metric | Description | Formula/Source |
|--------|-------------|----------------|
| To Call | Amount needed to continue | `max(bets) - hero_bet` |
| Pot Size | Current pot amount | `sum(pot_amounts)` |
| Pot Odds (%) | Fraction of final pot to call | `to_call / (pot + to_call) * 100` |
| Required Equity (%) | Break-even win probability | Same as pot odds |
| Effective Stack | Min(hero, key opponent) | `min(hero_stack, villain_stack)` |
| SPR | Stack-to-pot ratio | `effective_stack / max(1, pot)` |

### 2.2 Hand Strength, Draws, Texture

| Metric | Description | Implementation |
|--------|-------------|----------------|
| Hand Description | Human-readable best-5 label | Reuse engine best-5 → text |
| Draws & Outs | Counts and draw types | Unseen-card enumeration (clean outs) |
| Board Texture | Paired / monotone / two-tone / straighty | Rank/suit pattern checks |

### 2.3 Position & Context

- Position label (BTN/SB/BB/UTG/MP/CO)
- Street (preflop/flop/turn/river)
- Legal action bounds (min/max raise)

### 2.4 Opponent Statistics (session)

We start with a minimal, robust set that supports style inference:

| Stat | Definition |
|------|------------|
| VPIP | Voluntarily put money in pot / hands dealt |
| PFR | Preflop raises / hands dealt |
| AFq | (bets + raises) / (bets + raises + calls + checks) |

Style inference: Tight vs Loose via VPIP thresholds; Aggressive vs Passive via AFq and PFR thresholds. Output per seat as `{looseness: Tight|Loose, aggression: Aggressive|Passive}`.

---

## 3. PokerKit APIs (authoritative source)

We rely exclusively on PokerKit for equity computations (heads-up and multiway) and range parsing.

Key APIs:
- `calculate_equities(hands_or_ranges, board_cards, num_simulations)`
- `parse_range(range_str)` → range combos
- State accessors (`bets`, `stacks`, `pot_amounts`, `board_cards`, `hole_cards`, `turn_index`, `street_index`)

Notes:
- Multiway equity is produced by passing all live opponents’ ranges alongside hero’s hand.
- Simulation count is configurable; we target snappy responses with caching.

---

## 4. Architecture & Integration

### 4.1 Package layout (modular, maintainable)

```
poker/
  analysis/
    core.py      # pot odds, required equity, SPR, texture, hand text
    equity.py    # PokerKit equity (HU + multiway), range parsing, caching
    ranges.py    # presets (Nit/Reg/Loose), validation, summaries
    stats.py     # VPIP, PFR, AFq tracking + style inference
    models.py    # dataclasses/Pydantic for analysis payloads
    cache.py     # small LRU keyed by (hand_id, street, hero, board, villains, ranges)
  engine.py      # integrate analysis at prompt-time (minimal touch)

app/
  main.py        # GET/POST /tables/{id}/ranges (seat-scoped)

public/
  index.html     # add drawer container + handle
  app.js         # render drawer when receiving prompt.analysis
  style.css      # drawer styles

tests/
  test_analysis.py  # core math, texture, outs, equity envelope checks
  test_stats.py     # VPIP/PFR/AFq and style mapping
```

### 4.2 Data flow (prompt-first integration)

```
engine builds human prompt
     ↓
compose_analysis(context)  # analysis/core + equity + stats
     ↓
WebSocket prompt message { type: 'prompt', analysis: {...} }
     ↓
Client opens/updates the drawer and renders analysis
```

Rationale:
- Compute only when it matters (hero to act, or when board changes before hero acts).
- Avoids bloating every snapshot; we can later promote analysis to `snapshot.table.analysis` once stable.

### 4.3 Performance & caching

- Trigger only on hero turns or board transitions.
- LRU cache for equity keyed by `(hand_id, street, hero_hole, board, villain_seats, ranges_hash)`.
- Configurable simulations (default 1000). If processing exceeds target budget (~100ms), mark payload with `degraded:true` and optionally lower simulations on the next attempt.

---

## 5. Implementation Steps (incremental)

1) Backend package scaffolding
- Create `poker/analysis/{core,equity,ranges,stats,models,cache}.py` with minimal implementations.
- Add unit tests for core math, texture, and range validation.

2) Ranges API
- `POST /tables/{id}/ranges {seat, range, preset?}` to set seat-specific ranges.
- `GET /tables/{id}/ranges` returns summaries for the table.
- Validate ranges via PokerKit `parse_range`.

3) Prompt-time analysis injection
- In `engine.advance()`, when building the human `prompt`, call `compose_analysis(...)` and attach the result to `prompt['analysis']`.
- Include: `pot_math`, `stack_spr`, `board_texture`, `hand`, `equity` (vs single seat and vs all live opponents), and `styles` (per-seat TL×AP).

4) Drawer UI
- Add a right-side drawer with a handle button. Default collapsed; auto-expand when hero is to act.
- Keyboard accessible (`aria-expanded`, focus trapping not required for MVP).
- Sections: Core math, Hand/Texture, Equity (vs seat selector + “vs All”), Opponent styles.

5) Stats tracking and style inference
- Track VPIP, PFR, AFq per seat using hand boundaries and action parsing.
- Infer `{looseness, aggression}` per seat from thresholds (configurable; e.g., Tight if VPIP < 18%, Loose if > 30%; Aggressive if AFq ≥ 45% or PFR ≥ 12%).

6) Tests & polish
- `test_analysis.py`: pot odds/required equity/SPR boundaries; texture samples; outs (flush=9, OESD=8); equity envelope checks (e.g., river-locked outcomes = 0/100%).
- `test_stats.py`: VPIP/PFR/AFq increment and style mapping.

---

## 6. API & Payloads

### 6.1 Ranges endpoints

- `POST /tables/{id}/ranges`
  - Body: `{ seat: int, range: str, preset?: 'Nit'|'Reg'|'Loose' }`
  - Returns 200 on success; persisted in-session.

- `GET /tables/{id}/ranges`
  - Returns `{ [seat]: { range: str, source: 'preset'|'custom' } }`.

### 6.2 WebSocket prompt extension (example)

```json
{
  "type": "prompt",
  "seq": 123,
  "to_act": 1,
  "legal_actions": [ ... ],
  "analysis": {
    "pot_math": {"to_call": 12, "pot": 36, "pot_odds_pct": 25.0, "required_equity_pct": 25.0},
    "stack_spr": {"effective_stack": 180, "spr": 5.0, "vs_seat": 3},
    "board_texture": {"paired": false, "monotone": false, "two_tone": true, "straighty": false},
    "hand": {"label": "Top Pair, Top Kicker"},
    "equity": {"vsSeat": {"seat": 3, "pct": 41.2}, "vsAll": {"pct": 38.7}, "simulations": 1000, "degraded": false},
    "styles": {"2": {"vpip": 28, "pfr": 14, "afq": 48, "looseness": "Loose", "aggression": "Aggressive"}}
  }
}
```

Note: We will formalize Pydantic models after stabilization; for now, the client reads these fields opportunistically.

---

## 7. UI: Drawer behavior

- Drawer opens automatically on hero’s turn; otherwise remains in last state.
- Compact layout with clear sections; equity bar with percentage; texture tags.
- Seat selector to switch “vs Seat” equity; “vs All” always shown when multiway opponents exist.
- Persist user-set ranges per seat in `localStorage` and sync to server via the ranges API.

---

## 8. Testing Plan

- Core math: pot odds, required equity, and SPR (including zero/edge cases).
- Texture: paired, monotone, two-tone, straighty sample boards.
- Outs: flush (9), OESD (8), simple combos (e.g., flush+OESD = 15) with clean-outs definition.
- Equity: river-locked outcomes (0/100%), multiway length matches number of live opponents; heads-up sanity cases.
- Stats & styles: counters accumulate across synthetic hands; thresholds map to TL×AP as expected.

---

## 9. Delivery Checklist

- [ ] `poker/analysis/` package scaffolding (`core/equity/ranges/stats/models/cache.py`).
- [ ] Prompt-time analysis injection in `engine`.
- [ ] Ranges API (`GET/POST`).
- [ ] Drawer UI (HTML/CSS/JS) and prompt handler.
- [ ] Unit tests for core/ranges/equity envelopes and stats/style mapping.
- [ ] Manual QA: run a session, verify drawer behavior and live updates.

---

## 10. Notes & Constraints

1) Equity strictly uses PokerKit (`calculate_equities`, `parse_range`). No custom Monte Carlo or alternative evaluators for equity.
2) Compute analysis only when hero acts or board changes; keep snapshots lean.
3) Time budget target ~100ms for analysis; use caching and optional simulation tuning.
4) Style classification avoids subjective labels; use Tight/Loose and Aggressive/Passive only.
5) Accessibility and mobile behavior will be iterated post-MVP; drawer is keyboard-operable.

---

## 11. References

- PokerKit Documentation: https://pokerkit.org
- HUD stat conventions: PokerTracker/Hold’em Manager
- Strategy references: Janda, “Applications of No-Limit Hold’em”

