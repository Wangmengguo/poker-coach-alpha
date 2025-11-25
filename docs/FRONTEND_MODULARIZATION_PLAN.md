# Frontend Modularization & Optimization Plan (MVP-first)

**Status:** Draft – aligned with current MVP  
**Scope:** Frontend architecture and UX improvements under `public/`

## Frontend Optimization Plan (MVP-first)

### Goals
- 保持当前静态单页（`public/index.html` + `public/app.js`），不在第一阶段引入打包工具或框架。
- 优先提升可维护性、连接稳定性和基础体验，而不是堆叠复杂 UI 或依赖。
- 以小步迭代方式改造：每次改动后都能完整跑通「加入桌子 → 开局 → 行动 → 摘要」流程。

### Phase 1 — 高优先级（紧贴 MVP）

1. 模块化拆分（原生 ES Modules）
   - 在 `public/` 下引入轻量模块结构，例如：
     - `public/app.js`：应用入口，负责初始化与模块装配。
     - `public/modules/websocket.js`：WebSocket 管理（连接、重连、事件分发）。
     - `public/modules/state.js`：`GameState`（快照、分析数据、连接状态）。
     - `public/modules/renderer.js`：牌桌 & 控件 DOM 渲染。
     - `public/modules/analysis.js`：分析抽屉渲染与交互。
     - `public/utils/dom.js`：常用 DOM 工具（`setText`、`setVisible` 等）。
   - `public/index.html` 使用 `<script type="module" src="/public/app.js">` 加载入口，继续由 FastAPI 作为静态资源提供。

2. DOM 查询与渲染优化
   - 初始化阶段统一缓存高频 DOM 节点：
     - 各座位容器（`[data-seat="1"…"6"]`）、筹码/牌区域。
     - 桌面元素（pot、board、streetInfo）。
     - 动作按钮区域、分析抽屉相关元素。
   - 渲染循环只使用缓存引用，不在每次更新中重复 `querySelector`。
   - 视情况增加简单“差量更新”：保持实现可读的前提下，避免完全重绘整棵 DOM。

3. WebSocket 稳定性与错误处理
   - 实现简化版 `WebSocketManager`：
     - 配置项：`maxRetries`、`retryDelay`。
     - 方法：`connect()`、`send()`、`close()`。
     - 回调：`onOpen`、`onClose`、`onError`、`onMessage`。
   - 支持基础重连：在非正常关闭/错误时按重试策略自动尝试连接，超过上限后标记为 `failed`。
   - 将连接状态写入 `GameState.connection.status`，并在 UI 中以简单状态文本或徽标的方式展示（`Connecting/Connected/Reconnecting/Failed`）。
   - 统一错误出口：向日志区域追加错误信息，必要时展示顶部轻量提示条。

4. 轻量 GameState 抽象
   - 在前端集中维护一个 `GameState`：
     - `snapshot`：最近一次桌面快照（用于渲染）。
     - `analysis`：最近一次教练分析数据。
     - `connection`：`{ status, retryCount }`。
   - 提供少量方法：`updateSnapshot(data)`、`updateAnalysis(data)`、`setConnectionStatus(status)`、`getSnapshot()`。
   - 暂不引入完整的发布/订阅框架；模块之间通过明确函数调用和有限共享状态协作。

5. 可访问性（低侵入增强）
   - 为关键按钮添加 `aria-label`（例如：Fold / Check / Call / Raise）。
   - 为状态展示区域添加 `role="status" aria-live="polite"`，以便读屏器友好。

### Phase 2 — 中优先级（体验与布局）

1. 动画与过渡效果
   - 为手牌、公共牌、当前行动玩家添加基础 `transition`（位置/阴影/边框）。
   - 会话开始、重连成功时，为牌桌容器添加简单淡入效果。
   - 抽屉开合使用平滑过渡，保持在性能尚可的前提下增强视觉反馈。

2. 移动端布局优化
   - 针对 `max-width: 768px` 调整：
     - 牌桌宽高（如 `width: 95vw; height: 60vh`）以适配竖屏。
     - 分析抽屉采用侧边滑入，不遮挡核心行动区域。
   - 确保在小屏幕上，控制按钮和关键信息（pot、street、玩家行动）始终可见。

3. 分析抽屉 UX 完善
   - 用结构化展示代替调试 JSON：
     - Core Math（底池大小、To Call、Pot Odds、SPR）。
     - Hand & Texture（牌力描述、牌面纹理）。
     - Hand Strength（单一百分比，标注基于 PokerKit）。
     - Human Stats（VPIP/PFR/AFq，含样本量提示）。
   - 保留或折叠 debug 区域，仅在开发时使用。

### Phase 3 — 低优先级 / 后续演进

1. 构建与质量工具
   - 在前端结构稳定后，引入：
     - Vite（开发与构建）。
     - ESLint + Prettier（或沿用后端的 ruff/black 风格原则）。
   - 保持与当前 FastAPI 静态资源路径兼容（构建产物继续落在 `public/` 或专用目录）。

2. 可视化与历史趋势
   - 评估是否有明确用户价值后，再考虑接入轻量图表库或基于 Canvas 的定制图表：
     - 手牌胜率变化（按街道）。
     - VPIP/PFR 等长期趋势。
   - 严格控制依赖体积，避免对首屏加载产生过大影响。

3. PWA / 离线增强（仅在需要时）
   - 如未来需要更强的移动端/弱网支持，可规划：
     - Service Worker（缓存静态资源与有限数据）。
     - 简单离线提示与重连体验优化。
   - 该项视实际使用反馈再决策，不作为当前 MVP 必要目标。

### 非目标（前端，MVP 阶段）
- 不在 MVP 阶段引入大型前端框架或虚拟 DOM 实现，仅在确实遇到性能瓶颈并通过数据验证后再评估。
- 不优先实现复杂的多主题切换、动画编排或重度图表，仅做轻量的体验加强。


本文档记录前端模块化拆分、WebSocket 管理、状态管理、渲染优化、移动端适配与可访问性增强等建议中，哪些在当前 MVP 阶段采纳、部分采纳或暂缓，并给出理由，确保改动既能提升质量，又不会破坏现有的 MVP 敏捷节奏。

---

## 1. 模块化拆分（目录与类划分）

**建议结构**

```text
public/
  app.js                 // 入口，负责初始化
  modules/
    websocket.js         // WebSocketManager 类
    state.js             // GameState 类
    renderer.js          // Renderer 类（牌桌渲染）
    actions.js           // ActionHandler 类（用户交互）
    analysis.js          // AnalysisDrawer 类
  utils/
    dom.js               // DOM 工具函数
    constants.js         // 常量定义
    validators.js        // 输入验证
```

**采纳决策**

- 采纳（略微简化）：  
  - 保留上述整体结构和主要模块：  
    - `websocket.js / state.js / renderer.js / actions.js / analysis.js`。  
    - `utils/dom.js`、`utils/constants.js`。  
  - `validators.js` 暂不单独拆出，等出现多个输入验证场景后再抽离为公用模块。
- `public/index.html` 继续通过 FastAPI 作为静态资源提供，但入口脚本调整为：
  - 使用 `<script type="module" src="/public/app.js">` 加载 ES Module 入口。

**理由（MVP 兼容性）**

- 拆分大文件是“结构升级”，不是重型新功能，风险低且收益明显：  
  - 每个模块职责更清晰，有利于后续小步重构。  
  - 不引入打包器或前端框架，保持当前“静态资源 + 原生浏览器能力”的简单栈。
- 使用类（`WebSocketManager / GameState / Renderer` 等）只是组织方式，不强制复杂模式，符合 MVP 阶段“简单可读”的要求。

---

## 2. WebSocketManager 增强

**原始建议要点**

- 配置项：`maxRetries`、`retryDelay`、`exponentialBackoff`。  
- 重连次数：`reconnectAttempts`。  
- 离线消息队列：`messageQueue`，在未连接时缓存消息。  
- 事件订阅/发布：`on(event, callback)` 与 `emit(event, data)`。

**采纳决策**

- 部分采纳：  
  - 采纳：
    - `maxRetries`、`retryDelay`、`reconnectAttempts` 等基础重连能力。  
    - 事件订阅/发布机制：`on/emit`，用于向上层模块广播连接状态、消息等。  
  - 暂缓：
    - `exponentialBackoff`（指数退避）逻辑。  
    - 通用 `messageQueue` 离线消息队列。

**理由（MVP 兼容性）**

- 事件机制非常适合把连接层从 UI / 渲染细节中解耦，能明显改善代码结构，同时实现复杂度可控。  
- 对于当前“单桌 + 单人”桌面应用场景，离线消息队列并非刚需：  
  - 重连后自动补发旧动作存在语义风险（例如发送已经过期的 `action`），对牌局而言有安全性问题。  
  - MVP 阶段更希望“失败显式暴露并提示重试”，而不是静默重试导致状态混乱。  
- 固定间隔重连 + 清晰的连接状态展示（`Connecting / Connected / Reconnecting / Failed`）已经能显著提升稳定性，与 MVP 要求的“可用 + 可调试”目标匹配。

---

## 3. GameState 设计

**原始建议要点**

- `GameState` 属性：
  - `snapshot`：当前桌面快照。  
  - `analysis`：当前分析数据。  
  - `connection`：`{ status: 'disconnected', retryCount: 0 }`。  
  - `history`：历史记录（调试/回放）。  
  - `subscribers`：订阅者集合。
- 更新模式：
  - `updateSnapshot(newSnapshot)`：不可变更新（拷贝新对象）。  
  - 记录历史：在 `history` 中推入时间戳 + 类型。  
  - `notifyChanges(oldData, newData)`：计算差异并仅在有变化时通知订阅者。

**采纳决策**

- 部分采纳：  
  - 采纳：
    - 集中管理 `snapshot / analysis / connection` 的 `GameState`，避免状态散落在各处。  
    - 提供明确方法：`updateSnapshot(data)`、`updateAnalysis(data)`、`setConnectionStatus(status)`、`getSnapshot()` 等。  
  - 暂缓：
    - 完整的不可变 diff 与按字段触发（`detectChanges` + `notifyChanges`）。  
    - 无限制增长的 `history` 与完整回放机制。

**理由（MVP 兼容性）**

- 集中状态管理提升代码可读性与可测试性，是一个非常符合 MVP 需求的重构方向，且改动范围可控（由入口与模块逐步迁移）。  
- 当前牌桌规模有限，前端渲染成本不高，使用“全量重绘 + 少量优化（DOM 缓存）”已经足够，不必一开始就为 diff 通知付出额外复杂度。  
- 若保留 `history`，建议以“调试工具”视角实现：  
  - 限制长度（例如只保留最近 N 条），防止长期会话内存占用过大。  
  - 不依赖 history 做核心功能，只用于开发时查看与问题排查。

---

## 4. 渲染性能优化（Renderer）

**原始建议要点**

- `Renderer` 内维护：
  - `cachedElements`：缓存所有需要频繁访问的 DOM 节点。  
  - `renderQueue`：渲染任务队列。  
  - `isRendering`：当前是否正在渲染。
- 初始化缓存：
  - 在 `initializeElements()` 中，对 6 个座位及桌面元素进行一次性 `querySelector` 并存入缓存。  
- 批量渲染：
  - `scheduleRender(updateFn)`：推入队列并通过 `requestAnimationFrame` 批量执行。  
  - `processRenderQueue()`：逐个执行更新函数，然后重置状态。

**采纳决策**

- 部分采纳（仅做缓存）：  
  - 初始化阶段缓存所有关键 DOM 节点（座位、pot/board/street、控制条、分析抽屉）。  
  - 渲染时直接操作缓存引用，不再重复 `querySelector`。  
  - 当前阶段**不实现** `renderQueue` / `requestAnimationFrame` 批处理或更复杂的差量更新逻辑，如后续出现性能瓶颈再单独评估。

**理由（MVP 兼容性）**

- DOM 缓存属于“低风险、高收益”的优化：  
  - 实现简单，仅影响初始化逻辑。  
  - 后续所有渲染函数只操作缓存引用，无需重复 `querySelector`。  
- 就当前玩家数量和 UI 复杂度而言，直接渲染已经足够，不需要提前引入渲染队列或虚拟 DOM；更进阶的渲染优化明确留到 MVP 稳定、真有性能数据后再做。

---

## 5. 移动端优化

**原始建议要点**

- 使用 `vw/vh` 单位调整 `.poker-table` 尺寸，并增大圆角。  
- 通过 `absolute` 布局和不同 `seat-X` 位置，重新排布 6 个座位以适配竖屏。  
- 将分析抽屉在小屏上改为底部弹出，使用 `transform: translateY(...)` 控制。

**采纳决策**

- 部分采纳：  
  - 先做：
    - 将 `.poker-table` 改为使用 `vw/vh`，在 `max-width: 768px` 下保证竖屏可用。  
    - 在小屏上，将分析抽屉改为底部弹出（height ~40vh，圆角顶部），避免遮挡核心牌桌区域。  
  - 暂缓：
    - 全部座位使用绝对定位重新布阵（`seat-1..6` 大幅改动位置/大小）。

**理由（MVP 兼容性）**

- 目前主要使用场景仍然是桌面浏览器，移动端属于“加分项”，不宜一次性做过重布局变更而影响桌面样式或点击区域。  
- 优先使用简单媒体查询和尺寸调整，使牌桌在竖屏下“看得清、点得到”；更复杂的座位布局和视觉优化可以在 MVP 稳定后逐步打磨，并结合真机测试。

---

## 6. 可访问性增强（不含快捷键）

**当前决策**

- 采纳：
  - 创建一个屏幕阅读器专用的 `aria-live` 区域（`sr-only`），用于播报关键状态变化。  
  - 通过日志 + SR 公告提升易用性。  
- 不采纳：
  - 不在当前 MVP 计划中实现键盘快捷键（如 `f/c/r`）；后续若有明确需求，将单独设计。

**理由（MVP 兼容性）**

- ARIA 标签和状态播报已经能在不改变交互方式的前提下提升可访问性。  
- 键盘快捷键会改变当前操作习惯、也增加一层行为复杂度，而你明确不希望这部分功能，因此在本阶段不再规划快捷键相关实现。

---

## 总结：MVP 阶段的整体取舍

- 第一优先级：  
  - 完成模块化拆分（入口 + modules + utils），清晰划分职责。  
  - 引入简化版 `WebSocketManager` 与 `GameState`，让连接与状态管理更稳、更易调试。  
  - 做 DOM 缓存，解决最直接的性能隐患；渲染队列等进阶优化不在当前范围内。  
- 第二优先级：  
  - 基础移动端适配（牌桌尺寸 + 抽屉位置）。  
  - 分析抽屉的结构化展示与可访问性增强（以 ARIA 为主，不含快捷键）。  
- 后续阶段：  
  - 更复杂的 diff/回放、离线消息队列、完整布局重排和 a11y 框架，放在 MVP 稳定之后再逐步引入，基于真实使用反馈做决策。
