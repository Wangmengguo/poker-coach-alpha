# Bot Equity/EV 策略 v0 设计说明

**目标版本**：bot_equity_policy_v0  
**状态**：✅ **已完成**（2025-01-XX）  

本设计在现有 Coach 分析基础设施上（`poker/analysis/*`），实现一个简单但基于“牌力 + 胜率/EV 粗估”的 Bot 策略，用来替代当前只按固定优先级选择动作的 `SimpleBot` 逻辑。目标是：

- 仍然严格尊重 `legal_actions`，不违反 PokerKit 引擎的合法性约束。
- 决策尽量可解释：和 Coach 面板展示的 `hand_strength_pct`、`required_equity_pct`、`SPR` 等指标保持一致。
- 实现成本低、性能可控，作为后续更复杂 bot（搜索/范围/NN）的跳板。

---

## 1. 依赖与输入

Bot 的决策运行环境：

- 底层游戏状态：PokerKit 的 `state`（`poker/engine.TableEngine.state`）。
- 当前位置：
  - `hero_idx`: 当前行动玩家在 PokerKit `state` 中的 index。
  - `hero_seat`: 对应的原始座位号（1-based，TableEngine 通过 `_state_index_to_seat` 提供）。
- 动作空间：
  - `legal_actions: List[Dict]`，由 `TableEngine.legal_actions()` 生成。
  - 典型形态：
    - `{"type": "check"}`
    - `{"type": "call", "amount": 10}`
    - `{"type": "fold"}`
    - `{"type": "raise_to", "amount": 30}`
    - `{"type": "raise_to", "min": 30, "max": 200}`（自定义 raise 区间）

Bot 策略依赖的分析组件（都已存在）：

- `poker.analysis.compose.compose_analysis`
  - 返回 `DecisionContext` + 一个便于 Prompt/前端使用的 `analysis_payload`。
- `poker.analysis.equity.compute_hand_strength`
  - 估算当前 hero 的牌力（类似胜率），返回 `HandStrengthResult`：
    - `hand_strength_pct ∈ [0, 100]` 或 `None`（信息不足或降级）。
    - 概念上近似为：

      ```text
      hand_strength_pct
      ≈ 100 * average_equity_vs_random_hands(
            hero_hole,
            board_cards,
            num_players = live_players,  # _live_player_count(state)
        )
      ```

      其中：
      - `live_players` 通过 `state.statuses` 或 `state.stacks>0` 估算当前仍在局内的玩家数；
      - board 已作为已知公共牌参与计算；
      - preflop 场景优先使用预计算表 `PREFLOP_EQUITIES_BY_PLAYERS`，否则回退到 Monte Carlo 近似。
- `poker.analysis.core.compute_pot_math` / `compute_pot_odds_and_equity_need`
  - 提供 `to_call`, `pot`, `effective_stack`, `spr`, `required_equity_pct` 等信息。

Bot 不直接操纵 PokerKit `state`，只根据这些派生特征和 `legal_actions` 做选择，实际动作由 `TableEngine.apply_action` 执行。

---

## 2. 决策核心思想

核心思想：基于当前牌力估计与底池赔率近似评估“跟注/弃牌/加注”的期望价值，然后用一组简单的阈值规则做决策。

概念对应：

- 牌力 / 胜率近似：`hs = hand_strength_pct`  
  - 如果是多玩家局，视为“对随机对手/范围的平均胜率”，用于粗粒度判断。
- 所需胜率（break-even equity）：`req = required_equity_pct`  
  - 从 `pot_odds` 推导而来：如果 hero 的真实胜率等于 `req`，长期跟注 EV ≈ 0。
- 边际胜率：`edge = hs - req`  
  - `edge > 0`：从赔率上看 call 倾向赚钱；  
  - `edge < 0`：从赔率上看 call 倾向亏钱。  
  - 实现中会对 `hs`、`req` 进行 `[0, 100]` clamp，避免极端输入。

在此基础上按 **街道（street）** 划分三类手牌，阈值依街道不同而不同（可后续调参）：

- 预设阈值表（初始建议值）：

  ```text
  Preflop: EDGE_WEAK = -15, EDGE_STRONG = +15, EDGE_VERY_STRONG = +25
  Flop   : EDGE_WEAK = -12, EDGE_STRONG = +12, EDGE_VERY_STRONG = +22
  Turn   : EDGE_WEAK = -10, EDGE_STRONG = +10, EDGE_VERY_STRONG = +20
  River  : EDGE_WEAK =  -8, EDGE_STRONG =  +8, EDGE_VERY_STRONG = +18
  ```

- 分类规则（给定当前 `street` 对应的阈值）：

  - `edge >= EDGE_STRONG(street)` → 强牌  
  - `EDGE_WEAK(street) < edge < EDGE_STRONG(street)` → 边缘牌  
  - `edge <= EDGE_WEAK(street)` → 弱牌

额外定义一个“超强牌”阈值：

- `very_strong = (edge >= EDGE_VERY_STRONG(street))`。

同时考虑：

- 当前是否被下注（`to_call > 0`）。
- SPR（`spr`）是否较低（例如 ≤ 3），作为 all-in/大额加注的一个粗略触发条件。

---

## 3. 行为策略规则（v0）

### 3.1 获取决策上下文

在 bot 回合时，先构造决策上下文：

1. 从 `TableEngine` 拿到：
   - 当前 `state`
   - `hero_idx`（状态中的 index）
   - `hero_seat`（原始座位号）
2. 调用：
   - `dc, _ = compose_analysis(state, hero_idx, hero_seat, include_hand_strength=True, hand_strength_samples=100, ...)`
3. 从 `DecisionContext` 中取出：
   - `hs = dc.hand_strength_pct`（可能为 `None`）
   - `to_call = dc.to_call`
   - `pot = dc.pot`
   - `required_equity_pct = dc.required_equity_pct`
   - `spr = dc.spr`
   - 其他字段（如 `street`, `players_count`, `hero_position`）暂留作将来细化规则使用。

降级策略：

- 若 `hs is None` 或 `required_equity_pct` 无法计算：
  - 回退到当前 `SimpleBot` 风格的规则：`check > call > min raise_to > fold > random`。
- sample_count 选用较小值（如 50~100），确保 bot 决策在合理时间内完成。

### 3.2 预处理：edge 与基础分类

```text
hs = clamp(dc.hand_strength_pct or 50.0, 0, 100)
req = clamp(dc.required_equity_pct or 50.0, 0, 100)
edge = hs - req
```

阈值通过一个按街道划分的映射函数获得，例如：

```text
weak, strong, very_strong = edge_thresholds(dc.street)
```

其中 `edge_thresholds` 可按第 2 节给出的预设表实现；这样 strong / very_strong 的逻辑在实现中只出现一处，便于统一调整。

分类：

- `edge >= strong` → 强牌
- `weak < edge < strong` → 边缘牌
- `edge <= weak` → 弱牌

同时设定一个“超强牌”标记：

- `very_strong = (edge >= very_strong)`。

### 3.3 动作选择逻辑

记：

- `LA = legal_actions`。
- `raises_fixed = [a for a in LA if a.get("type") == "raise_to" and "amount" in a]`
- `raises_range = [a for a in LA if a.get("type") == "raise_to" and "min" in a and "max" in a]`

并定义若干工具函数：

- `has(type)`: 判断是否存在该类型动作。
- `get_first(type)`: 返回首个该类型动作。
- `sorted_fixed_raises`: 按 `amount` 从小到大排序。
- `pick_small_raise`: 取最小 `amount` 的 raise（`sorted_fixed_raises[0]`）。
- `pick_medium_raise`: 在 `sorted_fixed_raises` 中取中位数（`sorted_fixed_raises[len//2]`）。
- `pick_large_raise`: 取最大 `amount` 的 raise（`sorted_fixed_raises[-1]`）。

#### 场景 A：无人下注（to_call == 0）

1. 若可 `check`：
   - 强牌（`edge >= strong` 且 `hs >= 65`）：
     - 若有 `raise_to`：
       - 优先选择一个 **中等 size** 的 `raise_to`（`pick_medium_raise`）；
       - 若只有一个候选，就用该候选；
       - 在某些强牌但非超强牌场景下，可加入少量随机化，例如：

         ```text
         if 0 < edge - strong < 5:
             70% 选择 check，30% 选择 pick_small_raise
         ```

         以避免完全确定性，同时控制整体风险。
     - 若无 `raise_to`：选择 `check`。
   - 边缘牌（`weak < edge < strong` 且大致 `45 <= hs < 65`）：
     - 主要选择 `check`，避免频繁 bloating pot；
     - 可以在少数情况下随机选择 `pick_small_raise` 作为轻度混合策略，例如：

       ```text
       if abs(edge) <= 5 and has('raise_to') and random() < 0.2:
           选择 pick_small_raise
       else:
           选择 check
       ```
   - 弱牌（`edge <= weak` 或 `hs < 45`）：
     - 始终选择 `check`。

2. 若不能 `check`（理论上不应该在 `to_call == 0` 出现，但防御性处理）：
   - 若有 `call`：当作 `check` 处理，直接 `call`。
   - 否则：回退到简单策略：`fold` 或任意合法动作。

#### 场景 B：面对下注（to_call > 0）

1. 若有 `fold` 和 `call`：

   - 弱牌（`edge <= weak`）：
     - 直接 `fold`。

   - 边缘牌（`weak < edge < strong`）：
     - 优先 `call`；
     - 对非常接近 0 的 `edge`（例如 `abs(edge) <= 5`），可以加入少量随机化，以避免策略完全可预测：

       ```text
       if edge < 0 and abs(edge) <= 5:
           80% fold, 20% call
       elif edge > 0 and abs(edge) <= 5 and has('raise_to') and random() < 0.25:
           25% 选择较小或中等 raise（pick_small_raise / pick_medium_raise）
           其余选择 call
       else:
           始终 call
       ```

     - 若无 `call` 但存在 `raise_to`，并且最小的 `raise_to.amount` 不远高于 `to_call`：
       - 可以将该 `raise_to` 作为“勉强跟注”使用（v0 中可以简化为：若没有 `call` 就选最小 `raise_to`）。

   - 强牌（`edge >= strong`）：
     - 若存在多个固定 `raise_to` 候选：
       - 默认选择 **中等偏大** 的一个，例如：

         ```text
         idx = max(len(raises_fixed)//2, len(raises_fixed)-2)
         action = raises_fixed[idx]
         ```

     - 若只有单个 `raise_to`：
       - 直接选择该 `raise_to`。
     - 若不存在固定 `raise_to`，但存在 `raise_to` 区间（`min/max`）：
       - 选择 `amount = min + 0.5 * (max - min)` 作为中等 size；  
       - 在需要更激进时可用 `amount = min + 0.8 * (max - min)`。
     - 若既没有 `raise_to` 又有 `call`：
       - 选择 `call`。

2. 考虑 SPR 与超强牌：

   - 若 `very_strong` 且 `spr <= 3`：
     - 在强牌分支中，倾向于选择更大的加注：
       - 若存在固定 `raise_to` 候选：选靠近最大值的那个。
       - 若存在 `min/max` 区间：选接近 `max` 的值。
     - 目标是在浅 SPR 场景中快速把筹码打光，以符合常见 cash game 策略。

3. 若 `fold` 或 `call` 不存在（防御性逻辑）：

   - 若只有一种动作类型：
     - 直接返回该动作（保持不会阻塞游戏）。
   - 若有多种：
     - 尝试按 `check > raise_to > call > fold` 的顺序找一个动作（回退到简单优先级）。

---

## 4. 与现有 Bot 框架的集成方式

### 4.1 策略对象形态

在当前项目中已有：

- `poker.bots.SimpleBot`：同步、仅看 `legal_actions` 的简单策略。
- `poker.bot_manager.AsyncBotPolicy`：异步策略基类，提供 `choose_async(self, legal_actions, seat, game_state)`。
- `poker.bot_manager.SimpleAsyncBot` / `TightBot`：对简单策略做了异步封装或加了 fold 倾向。

本策略 v0 计划：

- 先实现一个纯同步策略函数或类，例如：

  ```python
  class EquityBot:
      def choose(self, state, hero_idx, hero_seat, legal_actions) -> Dict:
          # 按第 3 节的规则实现
          ...
  ```

- 后续可以包装为异步策略：

  ```python
  class EquityAsyncBot(AsyncBotPolicy):
      async def choose_async(self, legal_actions, seat, game_state):
          # 根据 game_state 还原 state / hero_idx / hero_seat
          # 加一点 asyncio.sleep 模拟思考时间
          return EquityBot().choose(state, hero_idx, seat, legal_actions)
  ```

注意：本设计文档先聚焦决策逻辑本身，不约束具体集成细节（例如 `game_state` 的结构），但建议：

- `game_state` 至少包含：
  - `state`（或可用于重建 state 的信息）
  - `hero_idx` or `turn_index`
  - `hero_seat`

### 4.2 TableEngine 中的接入点

当前 `TableEngine.advance` 中 bot 分支逻辑大致为：

```python
if seat == human_seat:
    # 构建 prompt
else:
    # Bot seat - 目前直接在这里写死 check > call > raise > fold 的策略
```

集成本策略的建议步骤：

1. 将 bot 决策逻辑抽取到单独的 helper（或策略对象）中。
2. 在 bot 分支中调用：
   - `la = self.legal_actions()`
   - `action = equity_bot.choose(self.state, idx, seat, la)`
   - `self.apply_action(action)`
3. 保留原有逻辑作为降级备用选项：
   - 当 `equity_bot.choose` 抛异常或给出 `None` 时，回退到 simple 策略。

---

## 5. 限制与未来扩展

### 5.1 已知限制

- `hand_strength_pct` 目前是“对随机牌/玩家”的平均胜率，不区分对手范围，也不严格区分多方/单挑；因此决策只是“粗略合理”，不代表高水平策略。
- 未区分不同街道/位置的策略码本，例如：
  - preflop 没有单独使用 preflop table 或 open/fold chart。
  - turn/river 没有针对 bluff/call down 的精细规则。
- 未使用行动序列/历史，只基于当前一帧状态。

### 5.2 自然的演进方向

后续可以在该基础上逐步增强：

- 使用 `compute_equity_vs_range` + `build_default_preflop_range`：
  - 按位置/stack 深度构建默认对手范围，估算更接近真实的胜率。
- 引入更细的规则：
  - preflop 根据表格决定 open/3-bet/ flat/fold。
  - postflop 根据 board texture + hand category（made hand / draw / air）调整阈值。
- 将多个策略封装为不同 bot personality：
  - `NitBot`：EDGE_STRONG 更高、EDGE_WEAK 更大绝对值，基本不轻率加注。
  - `LagBot`：EDGE_STRONG 较低、在一些边缘牌上更频繁地选择加注。
- 引入简单对手建模：
  - 基于已有 `HumanStats` 或扩展统计，粗略估计对手松紧/激进度；
  - 按对手风格动态微调阈值和随机化权重（例如对超激进对手收紧边缘牌的跟注）。

---

## 6. 性能与样本数选择（MVP）

- `compose_analysis(..., include_hand_strength=True)` 会调用 `compute_hand_strength` 做 Monte Carlo 采样：
  - MVP 建议默认 `hand_strength_samples ≈ 50`，在本地压测确认 P50 / P95 延迟；
  - 若性能充裕，可提升到 80 或 100，以换取更稳定的估计。
- Bot 调用时的性能约束：
  - 每个 bot 决策 ideally 控制在 10–50ms 内；
  - 6-max 桌上多个 bot 连续行动时，总体开销也应保持在可接受范围。
- 边界与降级策略：
  - 若 hand strength 计算异常或超时时（`degraded=True`），bot 回退到 `SimpleBot` 优先级策略；
  - 未来若发现性能瓶颈，可考虑：
    - 对相同 street / board / hero_hole 做简单缓存；
    - 对 turn/river 使用更低 sample_count 或稍微放宽阈值以减少对精度的依赖。

---

## 7. 验收标准（v0）

在完成本策略的实现与接入后，bot 应满足：

- 每一个决策回合：
  - 都只从 `legal_actions` 中选择动作，不会构造非法 action。
  - 能在几十毫秒内完成一次决策（包括 hand strength 计算）。
- 行为上：
  - 面对明显不利的赔率（小胜率大底池）的跟注，应倾向于弃牌。
  - 有明显优势时（胜率显著高于赔率所需）能主动加注，而不是总是 flat call。
  - 在没人下注时，能合理地区分“强牌想构建底池”与“中/弱牌免费看下一张”。

本设计文档作为后续具体代码实现（策略类/函数 + TableEngine 集成）的规范基线。实现细节如参数阈值、raise 选择具体规则可在实践中微调，但不应违背上述总体思路。 
