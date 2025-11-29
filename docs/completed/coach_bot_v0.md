# Poker Coach / Bot v0 计划（基于现有 MVP 教练功能）

**目标版本**：coach_bot_v0  
**状态**：✅ **已完成**（2025-01-XX）  
**背景**：在当前 MVP（pot math + hand strength + human stats + 基础 hand/texture/outs）基础上，补齐“解释用数学核心函数”和“统一决策上下文”，为后续 V1/ V2 Coach（含建议）以及 Bot 决策提供可复用的基础设施。

---

## 1. 总体目标与范围

- 面向目标：
  - 短期：让 Coach 面板能用统一的数学函数给出更清晰、可解释的指标（特别是 pot odds 与 call EV）。
  - 中期：为后续“给出建议”的 Coach / Bot 提前准备好核心数学原语（EV、范围、equity vs range）。
- 明确非目标（本计划不做）：
  - 不实现完整的搜索树 / CFR / GTO advisor（属于 V2+）。
  - 不引入复杂的范围编辑 UI，只在后端建立 Range/Equity 原语。
  - 不改变现有游戏流程、REST / WS 协议主体结构，只是补充 `analysis` 相关字段。

---

## 2. 阶段划分与优先级

按 ROI 和依赖关系，将工作拆为三个阶段：

- Phase 1（P0：立即实施）
  - 在 `poker.analysis.core` 中新增/扩展三个核心函数：
    1. `compute_pot_odds_and_equity_need`
    2. `compute_pot_math` 返回 `effective_stack`
    3. `compute_call_ev`
  - 不改动整体架构，只向现有 `engine.advance()` 注入更多分析字段。

- Phase 2（P1：强烈建议，提升架构可维护性）
  - 新增统一的决策上下文 `DecisionContext` dataclass。
  - 新增 `compose_analysis(...)`，集中完成从 PokerKit `state` 到 Coach/Bot 特征的抽取。
  - 让 `engine.advance()`/Coach UI/Bot 都依赖同一套特征抽取逻辑。

- Phase 3（P2：为 V2 Advisor / Bot 提前打基础）
  - 定义简化的 Range 表示与默认 preflop 范围构造函数。
  - 新增 `compute_equity_vs_range(...)`，在当前 `compute_hand_strength` 的基础上支持指定对手范围。

---

## 3. Phase 1（P0）—— 核心指标函数

### 3.1 新增 compute_pot_odds_and_equity_need()

**位置**：`poker/analysis/core.py`  
**接口草案**：

```python
def compute_pot_odds_and_equity_need(
    pot: int,
    to_call: int,
    current_street_bets_sum: int,
) -> Dict[str, float]:
    """计算 pot_odds 及所需胜率（Required Equity）。

    Args:
        pot: 底池基数（通常为 state.pot_amounts 之和，不含当前街未收集筹码）
        to_call: 英雄当前需要投入的筹码（max(state.bets) - hero_bet，经 clamp>=0）
        current_street_bets_sum: 当前街所有玩家已在桌面但尚未收集的筹码总和，
                                 即 sum(state.bets)，call 后这些会并入底池。
    """
    pot_decision = pot + current_street_bets_sum + to_call
    if pot_decision <= 0 or to_call <= 0:
        pot_odds_pct = 0.0
    else:
        pot_odds_pct = to_call / float(pot_decision) * 100.0
    required_equity_pct = pot_odds_pct
    return {
        "pot_decision": float(pot_decision),
        "pot_odds_pct": round(pot_odds_pct, 1),
        "required_equity_pct": round(required_equity_pct, 1),
    }
```

**用途**：
- Coach UI：展示 `pot_odds_pct`（例如“你需要投入底池的 25%”）。
- 解释层面：`required_equity_pct` 后续用于说明“只要赢 X% 就不亏”。
- 代码一致性：统一 pot odds/required equity 的计算公式，避免散落在前/后端的重复实现。

**集成点（初始）**：
- 在 `TableEngine.build_table_snapshot()` 或 `advance()` 内部，基于 `compute_pot_math` 的结果及 `state.bets` 计算 `current_street_bets_sum`，并扩展 `Prompt.analysis`：
  - `analysis.pot_math` 仍返回 `to_call`/`pot`/`spr`/`effective_stack`。
  - 新增 `analysis.pot_extra = {"pot_decision", "pot_odds_pct", "required_equity_pct"}` 或直接合入 `pot_math` 子字段（需保持向后兼容）。

**测试**：
- 在 `tests/test_analysis.py` 中新增：
  - 空底池/`to_call=0` 时 pot_odds 为 0。
  - 标准场景：`pot=30, to_call=10, current_street_bets_sum=0` → `pot_decision=40, pot_odds_pct=25.0`。

---

### 3.2 在 compute_pot_math() 中暴露 effective_stack

**现状**：`compute_pot_math` 已在内部计算有效筹码并用于求 SPR，但未在返回值中暴露。  
**修改**：在 `return` dict 中增加 `effective_stack`：

```python
return {
    "to_call": int(to_call),
    "pot": int(pot),
    "effective_stack": int(effective_stack),  # 新增
    "spr": float(spr),
}
```

**收益**：
- Coach 解释：可以直接用 `effective_stack` + SPR 解释“深筹码 vs 浅筹码”的决策差异。
- Bot 策略：后续 preflop/简单策略中，用 `effective_stack`（以 bb 为单位）快速切换不同策略表（如 <20BB 全推范围）。
- 成本：实现几乎为 0，只是字段透出。

**测试**：
- 在既有 `test_compute_pot_math_*` 用例基础上，断言 `effective_stack` 与注释中的期望一致。

---

### 3.3 新增 compute_call_ev()

**位置**：`poker/analysis/core.py`  
**接口草案**：

```python
def compute_call_ev(
    to_call: int,
    pot_decision: int,
    win_pct: float,
    tie_pct: float = 0.0,
) -> float:
    """一街近似 *净* EV 计算（单位：筹码）。

    定义：`pot_decision` 已包含英雄跟注后的总底池。
      - 赢：+ (pot_decision - to_call)
      - 平：+ (pot_decision / 2 - to_call)
      - 输：- to_call

    因此：EV = win% * pot_decision + tie% * (pot_decision / 2) - to_call
    """
```

**设计考量**：
- 纯函数、无副作用，易于单元测试。
- 可双向复用：
  - Coach 解释：展示“在当前胜率 ~X% 下，call 的期望是 +Y 筹码”。
  - Bot 策略：与 fold EV（0）对比，作为最基础的决策信号之一。

**集成思路**（可选，先只在后端计算，不一定立刻展示）：
- 当已有 `hand_strength_pct` 时：
  - `win_pct ≈ hand_strength_pct / 100.0`（多方局为近似）。
  - `tie_pct` 暂可设为 0 或预留。
  - 计算 `call_ev` 并放入 `analysis` 的 `ev` 字段中，方便后续 Coach/Bot 使用。

**测试**：
- 在 `tests/test_analysis.py` 新增：
  - `win_pct=0.5, tie_pct=0, pot_decision=100, to_call=50` → EV≈0。
  - `win_pct=0.6, tie_pct=0, pot_decision=100, to_call=40` → EV>0。

---

## 4. Phase 2（P1）—— 统一决策上下文

### 4.1 新增 DecisionContext dataclass

**位置**：`poker/analysis/models.py`（新文件）  
**目标**：让 Coach 解释与 Bot 策略共享同一份“决策特征”，避免重复抽取与不一致。

**接口草案**：

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class DecisionContext:
    """统一的决策上下文，供 Coach 解释和 Bot 策略共享。"""

    # 基本局面
    street: str  # "preflop", "flop", "turn", "river"
    hero_seat: int
    hero_position: str  # "BTN", "SB", "BB", "UTG", "MP", "CO"

    # 底池数学
    to_call: int
    pot: int
    current_street_bets_sum: int  # sum(state.bets) 当前街所有已下筹码
    pot_decision: float
    pot_odds_pct: float
    required_equity_pct: float

    # 筹码深度
    effective_stack: int
    spr: float

    # 手牌信息
    hand_strength_pct: Optional[float]
    hand_label: Optional[str]
    outs: int
    board_texture: Dict[str, bool]

    # 上下文
    players_count: int
    human_stats: Optional[Dict[str, Any]] = None

    # 预留字段（后续 V2/V3 使用）
    villain_ranges: Optional[Dict[int, Any]] = None  # seat -> range
    degraded: bool = False  # 任一关键值为近似/降级时标记
```

### 4.2 新增 compose_analysis(state, hero_idx, hero_seat, session_stats)

**位置**：`poker/analysis/compose.py`（新文件）  
**职责**：从底层 `state` 抽取全部 Coach/Bot 需要的特征，并返回一个 `DecisionContext`。

**接口草案**（伪代码）：

```python
from typing import Any, Optional

from .core import (
    compute_pot_math,
    compute_pot_odds_and_equity_need,
    compute_outs,
    describe_hand,
    compute_board_texture,
)
from .equity import compute_hand_strength
from .stats import HumanStats, build_stats_payload
from .models import DecisionContext


def compose_analysis(
    state: Any,
    hero_idx: int,
    hero_seat: int,
    session_stats: Optional[HumanStats] = None,
) -> DecisionContext:
    """从 PokerKit state 构建完整的决策上下文。

    - 仅依赖 state/hero_idx/hero_seat，不触发副作用。
    - VPIP/PFR/AFq 的累积更新仍由 engine 负责，这里只做读取与封装。
    """
    # 1) 基础数学
    pot_math = compute_pot_math(state, hero_idx)
    # 注意：当前街所有已下筹码总和 = sum(state.bets)
    current_bets = _sum_current_street_bets(state)  # 内部通常实现为 sum(state.bets)
    pot_extra = compute_pot_odds_and_equity_need(
        pot=pot_math["pot"],
        to_call=pot_math["to_call"],
        current_street_bets_sum=current_bets,
    )

    # 2) 手牌与牌面
    hero_cards, board_cards = _extract_cards(state, hero_idx)
    hand_label = describe_hand(hero_cards, board_cards) if hero_cards else None
    board_texture = compute_board_texture(board_cards)
    outs_payload = compute_outs(hero_cards, board_cards) if hero_cards else {"outs": 0}

    # 3) 胜率估计（可选：由上层决定是否调用 MC）
    hs_res = compute_hand_strength(state, hero_idx, sample_count=100)

    # 4) 人类统计
    stats_payload = build_stats_payload(session_stats) if session_stats else None

    # 5) 其他上下文（street/position/players_count）
    street = _extract_street(state)
    hero_position = _derive_position(state, hero_seat)
    players_count = _count_live_players(state)

    return DecisionContext(
        street=street,
        hero_seat=hero_seat,
        hero_position=hero_position or "",
        to_call=pot_math["to_call"],
        pot=pot_math["pot"],
        pot_decision=pot_extra["pot_decision"],
        pot_odds_pct=pot_extra["pot_odds_pct"],
        required_equity_pct=pot_extra["required_equity_pct"],
        effective_stack=pot_math["effective_stack"],
        spr=pot_math["spr"],
        hand_strength_pct=hs_res.hand_strength_pct,
        hand_label=hand_label,
        outs=int(outs_payload.get("outs", 0)),
        board_texture=board_texture,
        players_count=players_count,
        human_stats=stats_payload,
        degraded=bool(hs_res.degraded),
    )
```

### 4.3 与 engine / UI / Bot 的集成方式

1. `TableEngine.advance()`  
   - 现状：直接在内部拼接 `prompt["analysis"] = {...}`。  
   - 目标：改为：
     - 调用 `compose_analysis(...)` 获得 `DecisionContext`。
     - 将 `DecisionContext` 映射为 `Prompt.analysis` 的嵌套 dict（保持向后兼容，字段可分层放在 `pot_math`/`board_texture`/`hand`/`outs`/`stats` 等子对象中）。

2. UI（`public/app.js`）  
   - 现状：从 `msg.analysis` 中读取 `pot_math`、`board_texture`、`hand.label`、`outs`、`stats`、`context.hero_position`。  
   - 增量改动：
     - 读取并显示 `pot_extra.pot_odds_pct`（或从 `pot_math` 中新字段取出）。
     - 预留 `call_ev`/`required_equity_pct` 的展示位置，但可以先不 UI 化。

3. Bot（未来）  
   - Bot 策略层直接消费 `DecisionContext`，不再自己解读 `state`。
   - 有利于保证解释一致性：“Bot 决策基于的指标，就是你在 Coach 面板中看到的那些字段”。

### 4.4 Phase 2 验收标准

- 所有与 Coach/Bot 相关的分析字段，都通过 `DecisionContext` 统一抽取。
- `engine.advance()` 不再手写一堆分析字段逻辑，只做：
  - 更新 VPIP/PFR/AFq counters（写），
  - 调用 `compose_analysis(...)`（读），
  - 将结果注入 `Prompt.analysis`。
- 现有前端 Coach 抽屉行为不回退（兼容老字段），并可以新增 pot odds 展示。

---

## 5. Phase 3（P2）—— Range + Equity 原语

### 5.1 Range 表示与默认构造

**位置**：`poker/analysis/ranges.py`（新文件）  
**目标**：提供简洁的 Range 表示与默认 preflop 范围，为后续 advisor/Bot 复用。

**接口草案**：

```python
from dataclasses import dataclass
from typing import Dict


Range = Dict[str, float]  # "AKs" -> weight in [0, 1]

"""
Range 的 value 表示频率权重（frequency weight），范围 [0.0, 1.0]。

语义：
- "AA": 1.0 表示 100% 持有 AA（6 种组合）。
- "AKs": 0.5 表示 50% 的频率，即约一半的同花 AK 组合会出现在范围中。
- 权重不要求归一化为 1.0；在采样或计算 equity 时，会先根据所有权重归一化为概率分布。

Rationale：
- 便于人类配置（例如：“AKs 以 50% 频率 3-bet”）。
- 与常见工具（PokerTracker / PioSolver 等）的 range 表示方式兼容。
"""


def build_default_preflop_range(position: str, stack_bb: int) -> Range:
    """极简默认 preflop 范围（按位置+筹码深度）。

    - position: "BTN", "SB", "BB", "UTG", "MP", "CO"
    - stack_bb: 有效筹码深度（以 BB 为单位）
    """
    # 占位实现：20BB- 全推范围
    if stack_bb <= 20:
        return {
            "AA": 1.0,
            "KK": 1.0,
            "QQ": 1.0,
            "JJ": 1.0,
            "TT": 1.0,
            "AKs": 1.0,
            "AKo": 1.0,
            "AQs": 0.8,
            "AJs": 0.7,
        }
    # TODO: 100BB 开池范围（按位置细化）
    return {}
```

> 备注：后续可以引入更结构化的表示，如 `@dataclass WeightedHand`，但 v0 阶段先从 `Dict[str, float]` 开始，易于序列化与演进。

### 5.2 compute_equity_vs_range()

**位置**：`poker/analysis/equity.py`  
**目标**：在现有 `compute_hand_strength`（vs random）基础上，扩展出 vs 指定对手范围的 equity 计算，用于：
- 解释：“如果对手范围是 X，你的胜率是 ~Y%。”
- Bot：在简单单街决策中评估 call/raise 的 EV。

**接口草案**（高层伪代码）：

```python
from typing import Any

from .ranges import Range


@dataclass
class EquityResult:
    win_pct: float
    tie_pct: float
    lose_pct: float
    sample_count: int
    players: int
    degraded: bool = False
    reason: Optional[str] = None


def compute_equity_vs_range(
    state: Any,
    hero_idx: int,
    villain_range: Range,
    sample_count: int = 100,
) -> EquityResult:
    """基于给定对手范围的胜率估计。

    实现思路：
    1. 从 state 中提取 hero hole / board / 剩余牌堆。
    2. 将 villain_range 展开/采样为具体起手牌组合。
    3. Monte Carlo：
       - 每次从范围中采样一手 villain hole（确保不与 hero/board 冲突）
       - 随机补足剩余 board
       - 比较 showdown 结果，累积 win/tie/lose 计数
    4. 超时/异常时，返回 degraded=True，并带上 reason。
    """
    ...
```

**性能与降级策略**：
- `sample_count` 控制精度与性能（确保在 ~100ms 内完成）。
- 可按 `(street, board, hero_hole, villain_range_hash)` 进行缓存。
- 若发生超时或异常：
  - 设置 `degraded=True`，`reason="timeout"` 或具体错误信息。
  - 上层可选择使用默认 `compute_hand_strength` 结果作为近似。

### 5.3 Phase 3 验收标准

- 能基于简单的默认 Range 在后台计算 equity（可不立即暴露在 UI）。
- 接口稳定：后续 V2 search-based advisor 可以直接复用 `Range` + `EquityResult`。
- 有基础单元测试覆盖：
  - 简单对局（AA vs random）下，道理上高胜率。
  - 超时/异常时会设置 `degraded` 并不崩溃。

---

## 6. 测试策略（跨所有阶段）

### 6.1 单元测试

- 所有纯函数（`compute_*`, `build_*`, `compose_analysis` 等）必须有独立测试。  
- 覆盖关键边界条件：
  - 零值 / 空值 / 极端值（`to_call=0`、`pot=0`、`effective_stack=1` 等）。
  - pot_odds 与 EV 计算的数学正确性（手工推导对比）。  
- 对浮点结果使用 `pytest.approx(...)` 做近似断言，避免 CI 环境差异造成脆弱测试。

### 6.2 集成测试

- 在现有集成测试基础上，增加至少一个“带 Coach 分析”的端到端场景，例如：
  - 设定 6-max 桌，hero 在 BTN，持有强 draw（如 nut flush + OESD），flop 面对一个 bet。  
  - 验证：
    - `analysis.pot_math.to_call` / `pot` 与引擎状态一致。  
    - `analysis.pot_extra.pot_odds_pct` 与手工计算一致（如 25.0%）。  
    - `analysis.outs.outs` = 9/8/15（flush / OESD / combo）。  
    - 若有 hand_strength，则 `hand_strength_pct` 落在合理区间。  

### 6.3 性能与降级路径

- 性能：  
  - 将 hand strength / compose_analysis 的性能目标写在文档中（例如 P50 < 60ms、P95 < 120ms），作为基准参考。  
  - 不在 CI 中使用硬性时间断言，而是留给本地/手工基准测试脚本。  
- 降级路径测试：  
  - 模拟 `compute_hand_strength` 超时或异常时，确认：
    - `HandStrengthResult.degraded=True` 且 `reason` 合理。  
    - `DecisionContext.degraded=True`，并在日志中保留原因。  
    - UI 在降级状态下不崩溃，必要时以「~」或说明文案呈现近似值。  

### 6.4 测试数据与复用

- 在 `tests/fixtures/`（或等价模块）集中维护标准场景，例如：
  - `preflop_allin`：AA vs random，验证 preflop hand strength 与 pot odds。  
  - `flop_nut_flush_draw`：nut flush draw + OESD，验证 outs=15 与 pot odds。  
- 所有单元/集成测试优先复用这些场景，避免重复构造相同局面。

---

## 7. 向后兼容与版本演进

### 7.1 `Prompt.analysis` 字段演进策略

- 当前版本（v0.3，已实现）：  

```json
{
  "analysis": {
    "pot_math": {"to_call": 10, "pot": 30, "spr": 5.0},
    "stats": { "vpip_pct": 25.0, "...": "..." }
  }
}
```

- 目标版本（v0.4，新增 pot_odds / effective_stack；保持向后兼容）：  

```json
{
  "analysis": {
    "pot_math": {
      "to_call": 10,
      "pot": 30,
      "effective_stack": 180,
      "spr": 5.0
    },
    "pot_extra": {
      "pot_decision": 40.0,
      "pot_odds_pct": 25.0,
      "required_equity_pct": 25.0
    },
    "stats": { "vpip_pct": 25.0, "...": "..." }
  }
}
```

- 约束：  
  - 不移除既有字段，只增量添加新字段或新子对象。  
  - 新字段命名尽量局部化（如 `pot_extra`），避免污染顶层命名空间。

### 7.2 前端兼容策略

- `public/app.js` 渲染分析数据时，需要具备容错能力：  

```js
function renderAnalysisDrawerFromPayload(analysis) {
  const potMath = analysis?.pot_math || {};
  const potExtra = analysis?.pot_extra || {};

  const effectiveStack =
    typeof potMath.effective_stack === 'number'
      ? potMath.effective_stack
      : (typeof potMath.spr === 'number' && typeof potMath.pot === 'number'
          ? potMath.spr * potMath.pot
          : null);

  const potOdds = typeof potExtra.pot_odds_pct === 'number'
    ? potExtra.pot_odds_pct
    : null;

  // 有 potOdds 就展示；没有则保持当前 UI 行为。
}
```

- 旧客户端在没有 `pot_extra` 的情况下仍按原逻辑工作，新客户端可利用新字段展示更多解释信息。

### 7.3 API 版本管理（预留）

目前阶段不在 URL 中引入显式版本号；当未来存在多种 Coach 版本并行时，可考虑：  

- 在 WebSocket URL 上附加参数（例如 `&coach_version=0.4`）以便服务器按需调整 payload。  
- 或在 `Prompt.analysis` 中增加一个轻量的 `version` 字段，仅用于调试与灰度观察。

---

## 8. 实施顺序与预估工作量

| 阶段 | 内容                                        | 预估工作量（工程向） | 即时价值              | 未来价值                |
|------|---------------------------------------------|----------------------|-----------------------|-------------------------|
| 1    | `compute_pot_odds_and_equity_need`          | ~0.5–1 小时（含测试） | Coach 显示 pot odds    | 后续解释/EV 计算基础     |
| 1    | `compute_pot_math` 暴露 `effective_stack`   | ~0.1 小时            | Coach 可解释筹码深度    | Bot 策略分段（短/深筹码） |
| 1    | `compute_call_ev`                           | ~0.5–1 小时（含测试） | 解释 call 的 EV        | Bot EV 决策原语         |
| 2    | `DecisionContext` + `compose_analysis`      | ~2–3 小时            | 统一特征抽取，减轻重复   | Coach/Bot 共享特征体系   |
| 3    | Range 表示与 `build_default_preflop_range`  | ~1–2 小时            | 准备 V2，UI 不直接使用  | Preflop 策略/Advisor 基础 |
| 3    | `compute_equity_vs_range`                   | ~3–4 小时            | 准备 V2，UI 不直接使用  | V2 Advisor / Bot 核心    |

---

## 9. 后续演进方向（超出 v0 范围，仅做占位）

- 在 `DecisionContext` 中扩展：
  - 更细粒度的 hand strength 信息（如 vs 不同对手人数的 percentile）。
  - 更丰富的 context（action history 摘要、上一次街的投入等）。
- 在 UI 层：
  - 增加 EV/Required Equity 的解释文案与简单可视化（例如：进度条、颜色编码）。
  - 在足够多手数后，将 VPIP/PFR/AFq 映射成 TL×AP 的风格标签。
- 在 Bot 层（未来 V2/V3）：
  - 基于 `DecisionContext` + `Range` + `compute_equity_vs_range` 搭建简单 search-based advisor。
  - 将建议与 Coach 文案打通，实现“可解释的建议”（先解释后给出倾向）。

---

## 10. 当前行动项（v0 具体 TODO）

**Phase 1（P0）— 可并行，完成 1–3 即视为数学基础完成**

1. 核心函数实现（无依赖，可并行）  
   - [ ] `compute_pot_odds_and_equity_need()`  
   - [ ] `compute_pot_math()` 扩展返回 `effective_stack`  
   - [ ] `compute_call_ev()`  
   预估：1.5 小时（含基础验证）

2. 单元测试补充（依赖 1）  
   - 覆盖 pot_odds/required_equity、effective_stack、call_ev 边界与常规场景  
   预估：1 小时

3. 引擎集成（依赖 1）  
   - 在 `TableEngine.advance()` 中计算 `current_street_bets_sum = sum(state.bets)`  
   - 注入 `analysis.pot_extra`（或合入 pot_math）到 Prompt，保持向后兼容  
   预估：0.5 小时

4. UI 展示 pot_odds（依赖 3，可选加分项）  
   - 在 Core Math 区域增加 pot_odds 渲染，字段缺失时优雅降级  
   预估：0.5 小时

**Phase 2（P1）— 架构统一，面向 Coach/Bot 共享特征**

5. `DecisionContext` dataclass 与 `compose_analysis`（依赖 P0 完成）  
   - 统一特征抽取，包含 `current_street_bets_sum`、`effective_stack`、`pot_extra` 等  
   - 可选：在 DC 中汇总 `outs`（int）并保留原始 draw 标志  

6. 引擎改为调用 `compose_analysis` 构建 `Prompt.analysis`（依赖 5）  
   - 保持老字段向后兼容；新增 `pot_extra` 等字段  

7.（可选）测试夹具 `tests/fixtures/scenarios.py`（依赖 5/6 可并行）  
   - 集中维护典型场景（preflop_allin, flop_nut_flush_draw 等）供单元/集成复用  

完成 1–3 可标记 **v0 数学基础完成**；完成 5–6（及可选 7）可标记 **Phase 2 架构统一完成**，然后进入 Range / Advisor 的 Phase 3。

---

## 附录：术语表与调用关系示意

### A. 术语表

- **SPR (Stack-to-Pot Ratio)**：有效筹码 / 底池大小，用于刻画筹码深度。  
- **EV (Expected Value)**：期望值，单位为筹码。  
- **VPIP / PFR / AFq**：人类玩家统计数据，分别表示自愿入池率、翻前加注率、攻击频率。  
- **Effective Stack（有效筹码）**：英雄与最大覆盖对手筹码二者中的较小值。  
- **Pot Decision**：跟注后总底池大小（`pot + sum(state.bets) + to_call`）。  

### B. 调用关系（概念图）

```mermaid
graph TD
    A[TableEngine.advance()] --> B[compose_analysis()]
    B --> C[DecisionContext]
    C --> D[Coach UI]
    C --> E[Bot Strategy (future)]
    B --> F[Prompt.analysis payload]
    F --> D

    subgraph "底层分析函数"
        G[compute_pot_math]
        H[compute_pot_odds_and_equity_need]
        I[compute_outs]
        J[describe_hand]
        K[compute_hand_strength]
        L[build_stats_payload]
    end

    B --> G
    B --> H
    B --> I
    B --> J
    B --> K
    B --> L
```
