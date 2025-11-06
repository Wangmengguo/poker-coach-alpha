# Poker Coach Implementation Plan

**Status:** In Progress  
**Version:** 1.3 (Equity function finalized)  
**Last Updated:** 2025-11-06

---

## 1. Overview

This document specifies the current plan for delivering real-time coaching features. Design is strictly based on PokerKit for calculations, a drawer-style UI, and incremental integration that prioritizes user-visible value.

MVP scope (agreed decisions):
- Metrics: adopt clarified formulas and edge cases below; unambiguous definitions for pot odds, required equity, effective stack, and SPR.
- Hand info: provide human‑readable hand description and board texture; draws/outs consider only hero’s own improvement (no multiway/dirty‑outs adjustments in MVP).
- Equity: show only hero’s current win rate using PokerKit built‑ins; no seat selector and no “vs all” in MVP.
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
| Required Equity (%) | Break‑even win probability for a call | Equal to Pot Odds (%) |
| Effective Stack (vs MaxCoverOpponent) | Min(hero stack, largest opposing stack among live seats) | `min(hero_stack, max_opp_stack)` |
| SPR | Stack‑to‑pot ratio at decision | `SPR = effective_stack / max(1, pot)`; use base pot (excludes current street unpulled bets) |

Notes and edges:
- Clamp `to_call` to 0; if `pot_decision == 0`, display `pot_odds = 0`, `required_equity = 0`.
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

We rely exclusively on PokerKit for equity/win‑rate calculations and hand evaluation.

Primary APIs for MVP (finalized):
- `calculate_equities(hands_or_ranges, board=(), num_iterations=int)` — Monte Carlo equities with ties split (standard equity). Used as the sole source of “胜率/权益”。
- `parse_range(range_str)` — 用于表达“随机对手”范围，采用 `'XX'`（任意两张）并自动剔除死牌（Hero 手牌与公共牌）。
- State accessors: `bets`, `stacks`, `pot_amounts`, `board_cards`, `hole_cards`, `turn_index`, `street_index`。

Rejected for MVP:
- `calculate_hand_strength(hand, board=(), num_players=2)` — 计算“赢或平局”的概率（非标准 equity，平局按 1 计而非 0.5），且为完全枚举，早期街道性能不可控；因此不用于 UI 的“胜率”展示。

---

## 4. Architecture & Integration

### 4.1 Package layout (modular, maintainable)

```
poker/
  analysis/
    core.py      # pot odds, required equity, SPR, texture, hand text
    equity.py    # hero win rate via PokerKit (prefer calculate_hand_strength)
    stats.py     # VPIP, PFR, AFq tracking for human + optional TL×AP mapping
    models.py    # dataclasses/Pydantic for analysis payloads
  engine.py      # integrate analysis at prompt-time (minimal touch)

public/
  index.html     # add drawer container + handle
  app.js         # render drawer when receiving prompt.analysis
  style.css      # drawer styles

tests/
  test_analysis.py  # core math, texture, outs, hero win-rate envelope checks
  test_stats.py     # VPIP/PFR/AFq (human-only) and style mapping
```

### 4.2 Data flow (prompt-first integration)

```
engine builds human prompt
     ↓
compose_analysis(context)  # analysis/core + hero win rate + human stats
     ↓
WebSocket prompt message { type: 'prompt', analysis: {...} }
     ↓
Client opens/updates the drawer and renders analysis
```

Rationale:
- Compute only when it matters (hero to act, or when board changes before hero acts).
- Avoid bloating every snapshot; we can later promote analysis to `snapshot.table.analysis` once stable.

### 4.3 Performance

- MVP favors correctness over performance; compute on demand at hero prompts。
- No dedicated equity cache in MVP。若较慢，UI 短暂显示“computing…”。
- Monte Carlo 采样：`num_iterations` 可配置；默认 2000（可根据端到端延迟调优）。

---

## 5. Implementation Steps (incremental)

1) Backend analysis scaffolding
- Create `poker/analysis/{core,equity,stats,models}.py` with minimal implementations.
- Add unit tests for core math, texture, outs, and hero win‑rate envelope checks.

2) Prompt‑time analysis injection
- In `engine.advance()`, when building the human `prompt`, call `compose_analysis(...)` and attach the result to `prompt['analysis']`.
- Include: `pot_math`, `stack_spr`, `board_texture`, `hand`, `equity`（hero win rate only，源自 `calculate_equities` + `'XX'`），以及 `stats_human`（VPIP/PFR/AFq，TL×AP 可选）。

3) Drawer UI (MVP)
- Add a right‑side drawer; default collapsed; auto‑expand on hero’s turn.
- Sections: Core Math; Hand + Texture; Equity (single “Win Rate” bar/number); Human Stats.

4) Human stats tracking
- Track VPIP/PFR/AFq for the human seat; sample‑size handling (`Unknown` < 20 hands).

5) Tests & polish
- `test_analysis.py`: pot odds/required equity/SPR boundaries; texture samples; outs (flush=9, OESD=8); hero win‑rate envelope checks (e.g., river locked = 0/100%).
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
    "pot_math": {"to_call": 12, "pot": 36, "pot_odds_pct": 25.0, "required_equity_pct": 25.0},
    "stack_spr": {"effective_stack": 180, "spr": 5.0, "vs": "MaxCoverOpponent"},
    "board_texture": {"paired": false, "monotone": false, "two_tone": true, "straighty": false},
    "hand": {"label": "Top Pair, Top Kicker"},
    "equity": {"hero_win_rate_pct": 41.2, "model": "pokerkit.calculate_equities", "num_iterations": 2000, "opponent": "XX"},
    "stats_human": {"vpip": 28, "pfr": 14, "afq": 48, "style": "Loose-Aggressive", "hands": 25}
  }
}
```

Note: We will formalize Pydantic models after stabilization; for now, the client reads these fields opportunistically. The Prompt schema adds an optional `analysis` field for MVP.

---

## 7. UI: Drawer behavior (MVP)

- Drawer opens automatically on hero’s turn; collapses after hand end or by user.
- Compact sections: Core Math; Hand/Texture; Equity (single Win Rate); Human Stats.
- No seat selector and no “vs All” in MVP；文案：**“对抗单个随机对手的胜率（基于 Monte Carlo 模拟）”**。
- Persist UI state locally; no ranges persistence in MVP.

---

## 8. Testing Plan

- Core math: pot odds, required equity, and SPR (including zero/edge cases and MaxCoverOpponent selection).
- Texture: paired, monotone, two‑tone, straighty sample boards incl. A‑5 wrap.
- Outs: flush (9), OESD (8), combo (15) using simplified clean‑outs.
- Equity（基于 `calculate_equities`）:
  - 河牌定死场景：明显赢=1.0、明显输=0.0、完全平局≈0.5（允许模拟误差）。
  - 预翻：AA vs 随机手 ≈ 0.85（±0.02）。
  - 翻牌：标准 OESD vs 随机手 ≈ 0.32（±0.03）。
  - 转牌：同花听牌（9 outs）vs 随机手 ≈ 0.196–0.205（±0.02）。
  - 负载字段校验：`model='pokerkit.calculate_equities'` 且带 `num_iterations`。
- Stats (human): VPIP/PFR/AFq accumulation across synthetic hands; style `Unknown` for < 20 hands; threshold mapping sanity.

---

## 9. Delivery Checklist

- [ ] `poker/analysis/` scaffolding (`core/equity/stats/models.py`).
- [ ] Prompt‑time analysis injection in `engine` with optional `analysis` field on `Prompt`.
- [ ] Drawer UI (HTML/CSS/JS) and prompt handler for analysis.
- [ ] Unit tests for core/equity envelopes and human stats/style mapping.
- [ ] Manual QA: run a session, verify drawer behavior and live updates.

---

## 10. Notes & Constraints

1) Equity/win‑rate strictly uses PokerKit `calculate_equities` + `'XX'` 随机对手。无自定义评估器；`num_iterations` 可调优。
2) Compute analysis only when hero acts or board changes; keep snapshots lean.
3) Performance is secondary in MVP; caching is optional and may be introduced later.
4) Style classification avoids subjective labels; use Tight/Loose and Aggressive/Passive; show `Unknown` for small samples.
5) Accessibility and mobile behavior will be iterated post‑MVP; drawer is keyboard‑operable.

Open notes:
- 兼容性：确保当前锁定版本的 PokerKit 接受 `'XX'` 作为“任意两张”的范围表达；若版本差异导致不支持，回退为以所有两张组合构造全量范围。

---

## 11. References

- PokerKit Documentation: https://pokerkit.org
- HUD stat conventions: PokerTracker/Hold’em Manager
- Strategy references: Janda, “Applications of No-Limit Hold’em”
