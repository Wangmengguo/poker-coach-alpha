# Poker Coach Implementation Plan

**Status:** In Progress  
**Version:** 1.4 (Hand Strength function finalized)  
**Last Updated:** 2025-11-11

---

## 1. Overview

This document specifies the current plan for delivering real-time coaching features. Design is strictly based on PokerKit for calculations, a drawer-style UI, and incremental integration that prioritizes user-visible value.

MVP scope (agreed decisions):
- Metrics: adopt clarified formulas and edge cases below; unambiguous definitions for pot odds, effective stack, and SPR. Required Equity will not be displayed in MVP.
- Hand info: provide human‑readable hand description and board texture; draws/outs consider only hero’s own improvement (no multiway/dirty‑outs adjustments in MVP).
- Hand Strength: display hero’s current hand strength using PokerKit `calculate_hand_strength` with the actual number of live players at the table; no seat selector in MVP.
- Ranges: not implemented in MVP (no presets, no seat ranges, no Range API).
- Stats: track only the human player this session; TL×AP mapping may be deferred or shown as “human only”.
- Performance: correctness first; caching and strict time budgets are optional; compute on demand.
- Schema/UI: extend Prompt with an analysis payload matching the implemented features; UI uses a simple right‑side drawer.

---

## 2. Key Metrics for No-Limit Hold’em (clarified)

### 2.1 Core Decision Math (always visible when hero acts)

| Metric | Description | Formula/Source |
|--------|-------------|----------------|
| To Call | Amount hero must invest to continue | `to_call = max(state.bets) - state.bets[hero_idx]` clamped to `>= 0` |
| Pot Size (base) | Pot excluding current street’s unpulled bets | `pot = sum(state.pot_amounts)` |
| Pot at Decision | Pot after hero calls (final pot for call) | `pot_decision = pot + sum(state.bets) + to_call` |
| Pot Odds (%) | Fraction of pot hero invests to call | `to_call / pot_decision * 100` (if `to_call==0` → `0%`) |
| Required Equity (%) | Break‑even win probability for a call | Equal to Pot Odds (%). Not displayed in MVP. |
| Effective Stack (vs MaxCoverOpponent) | Min(hero stack, largest opposing stack among live seats) | `min(hero_stack, max_opp_stack)` |
| SPR | Stack‑to‑pot ratio at decision | `SPR = effective_stack / max(1, pot)`; use base pot (excludes current street unpulled bets) |

Notes and edges:
- Clamp `to_call` to 0; if `pot_decision == 0`, display `pot_odds = 0`. Required Equity is equal to Pot Odds but is not displayed in MVP.
- MaxCoverOpponent selection is deterministic: among live opponents, choose the seat with the largest stack; tie‑break by lowest seat number. SPR is reported vs this opponent in MVP.

### 2.2 Hand Description, Draws/Outs, Texture

| Metric | Description | Implementation |
|--------|-------------|----------------|
| Hand Description | Human‑readable label from hero’s best 5 at current street | Evaluate best 5 from hero hole + board; map to labels (e.g., Overpair, TPTK, Two Pair, Set, etc.) |
| Draws & Outs (hero‑only) | Counts for standard draws only | Simplified clean‑outs: Flush draw = 9, OESD = 8, Combo FD+OESD = 15; ignore dirty/anti‑outs and multiway effects in MVP |
| Board Texture | Paired / monotone / two‑tone / straighty | Deterministic checks: Paired if any rank count ≥ 2; Monotone if ≥ 3 same suit; Two‑tone if exactly 2 suits on board; Straighty if longest consecutive rank chain (A‑5 wrap allowed) ≥3 on flop or ≥4 on turn/river |

### 2.3 Position & Context

- Position label (BTN/SB/BB/UTG/MP/CO)
- Street (preflop/flop/turn/river)
- Legal action bounds (min/max raise)

### 2.4 Session Statistics (human only in MVP)

Tracked for the human seat only (session‑scoped; resets on `/restart`):

| Stat | Definition | Notes |
|------|------------|-------|
| VPIP | Voluntarily put $ into pot preflop / hands dealt with opportunity | Exclude blinds/antes and hands without opportunity |
| PFR | Preflop raises / hands dealt with opportunity | — |
| AFq | (bets + raises) / (bets + raises + calls + checks) across all postflop streets | — |

Style mapping (TL×AP) may be displayed for the human only. For small samples (< 20 hands), label as `Unknown`.

---

## 3. PokerKit APIs (authoritative source)

We rely on PokerKit for hand evaluation and probability calculations.

Primary APIs for MVP (finalized):
- `calculate_hand_strength(...)` — Monte Carlo estimation of the probability that hero’s hand beats randomly dealt opponents, given the actual number of players, known hole cards and board, deck, and hand type(s). No manual opponent range construction is required; the function samples from the remaining deck after removing dead cards.
- State accessors: `bets`, `stacks`, `pot_amounts`, `board_cards`, `hole_cards`, `turn_index`, `street_index`.

Deferred/Not used in MVP:
- `calculate_equities(...)` — Standard equity (ties split 0.5) vs specific hands/ranges. Reserved for future “EV/多对手权益”扩展，不在 MVP 显示中使用。

---

## 4. Architecture & Integration

### 4.1 Package layout (modular, maintainable)

```
poker/
  analysis/
    core.py      # pot odds, SPR, texture, hand text (Required Equity computed but not displayed in MVP)
    equity.py    # hero hand strength via PokerKit (calculate_hand_strength)
    stats.py     # VPIP, PFR, AFq tracking for human + optional TL×AP mapping
    models.py    # dataclasses/Pydantic for analysis payloads
  engine.py      # integrate analysis at prompt-time (minimal touch)

public/
  index.html     # add drawer container + handle
  app.js         # render drawer when receiving prompt.analysis
  style.css      # drawer styles

tests/
  test_analysis.py  # core math, texture, outs, hero hand-strength envelope checks
  test_stats.py     # VPIP/PFR/AFq (human-only) and style mapping
```

### 4.2 Data flow (prompt-first integration)

```
engine builds human prompt
     ↓
compose_analysis(context)  # analysis/core + hand strength + human stats
     ↓
WebSocket prompt message { type: 'prompt', analysis: {...} }
     ↓
Client opens/updates the drawer and renders analysis
```

Rationale:
- Compute only when it matters (hero to act, or when board changes before hero acts).
- Avoid bloating every snapshot; we can later promote analysis to `snapshot.table.analysis` once stable.

### 4.3 Performance

- MVP favors correctness over performance; compute on demand at hero prompts.
- No dedicated cache in MVP; if slower, the UI briefly shows "computing…".
- Monte Carlo sampling: `sample_count` is configurable; default 2000 (tune for end-to-end latency). If degraded, annotate `hand_strength.degraded=true`.

### 4.4 Definitions and Boundaries (MVP-precise)

- Hand Strength semantics: probability that hero’s hand does not lose against randomly dealt opponents given the current number of live players, known hole cards/board, deck, and hand type(s). Ties follow PokerKit semantics.
- Players (N): count of seats still in the hand (`state.statuses[j] is True`); if absent, approximate with `state.stacks[j] > 0`. N includes hero.
- NLHE constants: `hole_count=2`, `board_count=5`, `deck=STANDARD`, `hand_types=(StandardHighHand,)`.
- Draws/Outs (simplified): Flush Draw=9 outs if hero+board reach 4 to a flush and hero holds ≥1 of that suit; OESD=8 outs if a 4‑long open chain exists (A‑5 wrap allowed); Combo FD+OESD=15 outs; no tainted/reverse outs in MVP.
- Hand labels: Overpair/TPTK/Set only when they are the best relevant description and not superseded by higher made hands (e.g., Straight/Flush/Full House/Quads).
- Human stats: VPIP excludes blinds/antes; PFR counts preflop raises (incl. 3bet+); AFq = (bets+raises)/(bets+raises+calls+checks) across postflop; show `Unknown` for `<20` hands.
- Payload types: integers for chip amounts, floats for percentages (Hand Strength: one decimal; SPR: two decimals). Missing fields must be tolerated by clients.
- Triggering: compute analysis when hero is to act or when the board changes immediately before hero’s turn. Deduplicate by `(hand_id, street, to_act, bets_hash, board_hash)`.
- Required Equity: equals Pot Odds (%) but is explicitly not displayed in MVP.

### 4.5 Error Handling & Nulls

- If hero hole cards are unknown or N < 2, return `hand_strength_pct=null` with `reason="insufficient_info"` (UI shows "—").
- On Monte Carlo failure or timeout, return `hand_strength_pct=null`, set `degraded=true`, and log the exception; the rest of the analysis still renders.

### 4.6 Acceptance Criteria (MVP)

- Drawer opens on hero turn and shows Core Math (without Required Equity), Hand/Texture, Hand Strength, and Human Stats.
- Hand Strength payload includes `model="pokerkit.calculate_hand_strength"`, `sample_count`, and `players`.
- Deterministic math: pot odds/SPR match formulas including edge cases (to_call=0, empty pot).
- Texture and outs match simplified rules; combination draw returns `outs=15`.
- Performance: P50 compute time ≤60ms, P95 ≤120ms for Hand Strength at default sample_count on a typical dev machine; if exceeded, degrade and annotate.

---

## 5. Implementation Steps (incremental)

1) Backend analysis scaffolding
- Create `poker/analysis/{core,equity,stats,models}.py` with minimal implementations.
- Add unit tests for core math, texture, outs, and hero win‑rate envelope checks.

2) Prompt‑time analysis injection
- In `engine.advance()`, when building the human `prompt`, call `compose_analysis(...)` and attach the result to `prompt['analysis']`.
- Include: `pot_math`, `stack_spr`, `board_texture`, `hand`, `hand_strength`（基于 `calculate_hand_strength`，按场上实际人数采样），以及 `stats_human`（VPIP/PFR/AFq，TL×AP 可选）。

3) Drawer UI (MVP)
- Add a right‑side drawer; default collapsed; auto‑expand on hero’s turn.
- Sections: Core Math; Hand + Texture; Hand Strength（单一百分比数值）; Human Stats.

4) Human stats tracking
- Track VPIP/PFR/AFq for the human seat; sample‑size handling (`Unknown` < 20 hands).

-5) Tests & polish
- `test_analysis.py`: pot odds and SPR boundaries (Required Equity equals Pot Odds but is not rendered in MVP); texture samples; outs (flush=9, OESD=8); hero hand‑strength envelope checks (e.g., river locked ≈ 0/100%).
- `test_stats.py`: VPIP/PFR/AFq accumulation (human only) and style mapping.

---

## 6. API & Payloads

### 6.1 Ranges endpoints (Deferred)

Ranges configuration and endpoints are out of MVP scope and will be revisited post‑MVP.

### 6.2 WebSocket prompt extension (example)

```json
{
  "type": "prompt",
  "seq": 123,
  "to_act": 1,
  "legal_actions": [ ... ],
  "analysis": {
    "pot_math": {"to_call": 12, "pot": 36, "pot_odds_pct": 25.0},
    "stack_spr": {"effective_stack": 180, "spr": 5.0, "vs": "MaxCoverOpponent"},
    "board_texture": {"paired": false, "monotone": false, "two_tone": true, "straighty": false},
    "hand": {"label": "Top Pair, Top Kicker"},
    "hand_strength": {"hand_strength_pct": 41.2, "model": "pokerkit.calculate_hand_strength", "sample_count": 2000, "players": 6},
    "stats_human": {"vpip": 28, "pfr": 14, "afq": 48, "style": "Loose-Aggressive", "hands": 25}
  }
}
```

Note: We will formalize Pydantic models after stabilization; for now, the client reads these fields opportunistically. The Prompt schema adds an optional `analysis` field for MVP.

---

## 7. UI: Drawer behavior (MVP)

- Drawer opens automatically on hero’s turn; collapses after hand end or by user.
- Compact sections: Core Math; Hand/Texture; Hand Strength; Human Stats. Do not display Required Equity in MVP.
- 文案：**“基于场上实际人数的手牌强度（PokerKit Monte Carlo）”**。
- Persist UI state locally; no ranges persistence in MVP.

---

## 8. Testing Plan

- Core math: pot odds and SPR (including zero/edge cases and MaxCoverOpponent selection). Required Equity is validated indirectly via formula but not rendered in UI during MVP.
- Texture: paired, monotone, two‑tone, straighty sample boards incl. A‑5 wrap.
- Outs: flush (9), OESD (8), combo (15) using simplified clean‑outs.
- Hand Strength（基于 `calculate_hand_strength`）:
  - 河牌定死场景：明显赢≈100%、明显输≈0%。
  - 典型强听牌/强成牌示例（如 AsKs 在 QsJsTs 翻牌）：强度应接近 100%。
  - 负载字段校验：`model='pokerkit.calculate_hand_strength'`、包含 `sample_count` 与 `players`。
- Stats (human): VPIP/PFR/AFq accumulation across synthetic hands; style `Unknown` for < 20 hands; threshold mapping sanity.

---

## 9. Delivery Checklist

- [ ] `poker/analysis/` scaffolding (`core/equity/stats/models.py`).
- [ ] Prompt‑time analysis injection in `engine` with optional `analysis` field on `Prompt`.
- [ ] Drawer UI (HTML/CSS/JS) and prompt handler for analysis.
- [ ] Unit tests for core/hand-strength envelopes and human stats/style mapping.
- [ ] Manual QA: run a session, verify drawer behavior and live updates.

---

## 10. Notes & Constraints

1) Hand strength strictly uses PokerKit `calculate_hand_strength` with the actual number of live players; no manual opponent range construction. `sample_count` is tunable. Required Equity is not presented in MVP.
2) Compute analysis only when hero acts or board changes; keep snapshots lean.
3) Performance is secondary in MVP; caching is optional and may be introduced later.
4) Style classification avoids subjective labels; use Tight/Loose and Aggressive/Passive; show `Unknown` for small samples.
5) Accessibility and mobile behavior will be iterated post‑MVP; drawer is keyboard‑operable。

Open notes:
- 兼容性：确保 `Deck`/手牌类型（如 `StandardHighHand`）与 NLHE 参数一致；如遇版本差异，封装适配层统一入口参数。

---

## 11. References

- PokerKit Documentation: https://pokerkit.org
- HUD stat conventions: PokerTracker/Hold’em Manager
- Strategy references: Janda, “Applications of No-Limit Hold’em”
