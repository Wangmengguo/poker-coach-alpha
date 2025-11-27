# Frontend Development Plan (Comprehensive)

**Status:** Active Development  
**Scope:** Frontend architecture, visual design, and UX improvements under `public/`  
**Last Updated:** 2024-01

> 本文档整合了原 `FRONTEND_MODULARIZATION_PLAN.md` 和 `FRONTEND_BEAUTIFICATION_PLAN.md`，统一管理前端代码架构与视觉设计。

---

## 🎯 Design Philosophy

- **Professional Poker Atmosphere**: 真实赌场毡布纹理 + 优雅金色点缀
- **Distinctive Visual Identity**: 避免 Inter/Roboto 等通用字体，选择独特组合
- **MVP-First**: 保持静态单页，不引入打包工具或框架
- **Performance-First**: CSS-only 增强，最小化外部依赖
- **Accessibility-First**: 完整键盘导航和屏幕阅读器支持

---

## 📁 Project Structure

```text
public/
├── app.js                 // 入口，负责初始化与模块装配
├── index.html             // 单页 HTML
├── style.css              // 样式文件
├── modules/
│   ├── websocket.js       // WebSocketManager 类
│   ├── state.js           // GameState 类
│   ├── renderer.js        // Renderer 类（牌桌渲染）
│   ├── actions.js         // ActionHandler 类（用户交互）
│   ├── analysis.js        // AnalysisDrawer 类
│   ├── audio.js           // AudioManager 类（音效 + BGM）
│   └── messageQueue.js    // MessageQueue 类（动画节奏）
├── sounds/                // 音效目录（可选）
│   ├── README.md          // 音效下载指南
│   └── bgm-lounge.mp3     // 背景音乐（可选）
└── utils/
    ├── dom.js             // DOM 工具函数
    └── constants.js       // 常量定义
```

---

## 🚀 Implementation Phases

### Phase 1: Code Architecture (代码架构) ✅ 已完成

**目标**：模块化拆分 + WebSocket 稳定性 + 状态管理

| 任务 | 状态 | 说明 |
|------|------|------|
| ES Modules 拆分 | ✅ | websocket/state/renderer/actions/analysis |
| WebSocketManager | ✅ | 重连机制 + 事件分发 (on/emit) |
| GameState 抽象 | ✅ | snapshot/analysis/connection 集中管理 |
| DOM 缓存 | ✅ | 初始化时缓存高频节点 |
| ARIA 可访问性 | ✅ | aria-label + sr-only announcer |

**WebSocketManager 特性**：
- 配置：`maxRetries`、`retryDelay`
- 方法：`connect()`、`send()`、`close()`
- 事件：`on('open'/'close'/'error'/'message', callback)`
- 状态：`Connecting / Connected / Reconnecting / Failed`

**GameState 特性**：
- `snapshot`：最近一次桌面快照
- `analysis`：最近一次教练分析数据
- `connection`：`{ status, retryCount }`
- 方法：`updateSnapshot()` / `updateAnalysis()` / `setConnectionStatus()`

---

### Phase 2: MVP Visual Baseline (视觉基线) ✅ 已完成

**目标**：专业配色 + 独特字体 + 基础可访问性

| 任务 | 状态 | 说明 |
|------|------|------|
| CSS 变量系统 | ✅ | 主题支持的语义变量 |
| 专业配色方案 | ✅ | 赌场绿 + 金色 + 状态色 |
| 字体系统 | ✅ | Playfair Display + DM Sans + JetBrains Mono |
| 卡牌花色区分 | ✅ | 红色 (♥♦) / 黑色 (♠♣) |
| Focus States | ✅ | 金色 outline + box-shadow |
| 颜色对比度 | ✅ | WCAG AA 标准 |
| 基础响应式 | ✅ | 768px / 480px 断点 |
| 触控目标 | ✅ | ≥ 44-48px 最小尺寸 |

**CSS 变量摘要**：

```css
:root {
  /* Professional Poker Palette */
  --felt-green: #1a472a;
  --felt-dark: #0f3018;
  --gold-soft: #d4af37;
  
  /* Status Colors */
  --winner-glow: #00ff88;
  --loser-dim: #ff4757;
  --action-glow: #fbbf24;
  --human-blue: #3b82f6;
  
  /* Typography */
  --font-display: 'Playfair Display', Georgia, serif;
  --font-body: 'DM Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}
```

---

### Phase 3: Layout Restructure (布局重构) ✅ 已完成

**目标**：修复核心显示问题 + 操作栏精简 + 抽屉优化

| 任务 | 优先级 | 状态 | 说明 |
|------|--------|------|------|
| 牌面显示格式 | P0 | ✅ | 后端返回短码格式 (如 "4s") |
| 玩家卡片紧凑化 | P1 | ✅ | 68-82px 宽度，紧凑布局 |
| 操作栏精简 | P1 | ✅ | Slider + 快捷按钮 (2x/3x/Pot/All-in) |
| 牌桌 aspect-ratio | P2 | ✅ | 16:10 比例 + 百分比定位 |
| 抽屉不遮挡内容 | P2 | ✅ | body.drawer-open main margin-right |
| Game Log 折叠 | P3 | ✅ | `<details>` 实现 |

**操作栏布局**：

```
┌──────────────────────────────────────────────────────────────┐
│  [Fold]   [Call $12]   │  [2x] [3x] [Pot] [All-in]          │
│                        │  $min [═══○═══════] $max  [Raise]  │
└──────────────────────────────────────────────────────────────┘
```

---

### Phase 4: Immersive Visual Depth (视觉深度) ⏳ 进行中

**目标**：纹理 + 玻璃态 + 3D 效果

| 任务 | 状态 | 说明 |
|------|------|------|
| 牌桌纹理背景 | ⏳ | SVG 噪点 + 径向渐变 |
| 玻璃态组件 | ⏳ | backdrop-filter: blur() |
| 3D 卡牌效果 | ⏳ | transform-style: preserve-3d |
| 隐藏牌背面设计 | ⏳ | 条纹图案 + 花色图标 |
| 按钮渐变高光 | ⏳ | hover shine effect |
| Winner/Loser 样式 | ⏳ | 静态高亮状态 |

**牌桌纹理参考**：

```css
.poker-table {
  background: 
    /* SVG 噪点纹理 */
    url("data:image/svg+xml,..."),
    /* 径向渐变 */
    radial-gradient(ellipse 80% 60% at 50% 50%, 
      var(--felt-highlight) 0%, 
      var(--felt-green) 40%, 
      var(--felt-dark) 100%);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.6),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
```

---

### Phase 5: Advanced Animations (高级动画) ⏳ 待开始

**目标**：入场动画 + 状态动画 + 交互反馈

| 任务 | 状态 | 说明 |
|------|------|------|
| 座位依次入场 | ⏳ | animation-delay staggered |
| Winner 发光动画 | ⏳ | @keyframes winnerGlow |
| Action 脉冲动画 | ⏳ | @keyframes actionPulse |
| 筹码掉落动画 | ⏳ | @keyframes chipDrop |
| 发牌动画 | ⏳ | @keyframes cardDeal |
| 主题切换 | ⏳ | light/dark toggle |

**动画示例**：

```css
@keyframes winnerGlow {
  0%, 100% { box-shadow: 0 0 20px rgba(0, 255, 136, 0.6); }
  50% { box-shadow: 0 0 35px rgba(0, 255, 136, 0.9); }
}

.player-info.winner {
  animation: winnerGlow 2s ease-in-out infinite;
}
```

---

### Phase 3.5: Action Notifications & Audio (行动通知与音效) ✅ 已完成

**目标**：Bot 行动可视化 + 音效反馈

| 任务 | 状态 | 说明 |
|------|------|------|
| ActionNotification 协议 | ✅ | ws/protocol.py 新增消息类型 |
| 后端发送行动通知 | ✅ | Bot 和 Human 行动均发送通知 |
| 前端音效模块 | ✅ | Web Audio API 生成简单音效 |
| 行动通知显示 | ✅ | 玩家座位旁显示 toast 通知 |
| 音效开关按钮 | ✅ | 🔊/🔇 切换 |

**音效类型**：
- `check` / `call` / `raise` / `fold` - 不同行动对应不同音调
- `turn` - 轮到玩家行动时提示
- `win` - 胜利时播放琶音

**通知样式**：

```css
.action-notification {
  position: absolute;
  bottom: 100%;
  background: rgba(0, 0, 0, 0.85);
  color: var(--gold-bright);
  animation: notificationSlideIn 0.3s ease-out;
}
```

---

### Phase 3.6: Message Queue & Animation Pacing (消息队列与动画节奏) ✅ 已完成

**目标**：解决 Bot 行动"快进"问题，让动画有节奏地播放

**问题背景**：
- 后端 `engine.advance()` 会同步执行所有 Bot 行动，直到轮到 human
- 所有消息一次性通过 WebSocket 发送
- 前端几乎同时收到并处理，导致动画被"跳过"

**解决方案**：前端消息队列 + 延迟渲染

| 任务 | 状态 | 说明 |
|------|------|------|
| MessageQueue 类 | ✅ | 消息入队、定时处理、可跳过 |
| 集成到 app.js | ✅ | WebSocket 消息走队列 |
| 分类型延迟 | ✅ | action_taken 800ms, showdown 1500ms 等 |
| 速度控制 UI | ✅ | 🎯/🐇/⏩/🐢 切换按钮 |
| 用户行动跳过 | ✅ | 轮到用户时自动 flush 队列 |

**MessageQueue 设计**：

```javascript
class MessageQueue {
  constructor(processCallback, options = {}) {
    this.queue = [];
    this.processing = false;
    this.processCallback = processCallback;
    this.speedMultiplier = 1.0; // 1.0 = normal, 0.5 = fast, 2.0 = slow
    this.paused = false;
  }
  
  enqueue(msg) { /* 入队并启动处理 */ }
  processNext() { /* 递归处理队列 */ }
  getDelay(msg) { /* 根据消息类型返回延迟 */ }
  flush() { /* 立即处理所有消息（跳过动画） */ }
  setSpeed(multiplier) { /* 设置速度倍率 */ }
}
```

**延迟配置**：

| 消息类型 | 基础延迟 | 说明 |
|----------|----------|------|
| `action_taken` | 800ms | Bot 行动后停留 |
| `snapshot` | 100ms | 快照快速处理 |
| `showdown` | 1500ms | 摊牌停留观看 |
| `hand_end` | 500ms | 手牌结束过渡 |
| `prompt` | 0ms | 立即提示用户行动 |

---

### Phase 3.7: Audio Enhancement (音效增强) ✅ 已完成

**目标**：简约现代风格音效 + 背景音乐支持

| 任务 | 状态 | 说明 |
|------|------|------|
| 音效风格重设计 | ✅ | 简约现代风格（iOS/macOS 系统音风格） |
| ADSR 包络 | ✅ | 柔和的攻击/衰减曲线 |
| 低通滤波器 | ✅ | 消除刺耳高频 |
| 外部音效支持 | ✅ | 可选加载 public/sounds/ 下的 MP3 |
| 背景音乐 | ✅ | 循环播放、淡入淡出 |
| BGM 控制 UI | ✅ | 🎵/🎶 切换按钮 |
| 音效下载指南 | ✅ | public/sounds/README.md |

**合成音效特点**：
- 低频为主（120-350Hz）
- 短促（50-200ms）
- ADSR 包络 + 低通滤波
- 音量适中（不刺耳）

**音效对应**：

| 行动 | 风格 |
|------|------|
| Check | 轻柔敲击（180Hz sine） |
| Call | 温和音调（320Hz triangle） |
| Raise | 上滑音（280→350Hz） |
| Fold | 低沉放下声（120Hz） |
| Turn | 柔和双音提示 |
| Win | 三音琶音（温暖成功感） |

**背景音乐**：
- 文件：`public/sounds/bgm-lounge.mp3`
- 风格：Lofi / Jazz Lounge / Ambient
- 特性：自动循环、淡入淡出

---

### Phase 6: Mobile & Touch Optimization (移动端优化) ⏳ 待开始

**目标**：响应式完善 + 触控优化 + 底部抽屉

| 任务 | 状态 | 说明 |
|------|------|------|
| 断点细化 | ⏳ | 768px / 480px / 320px |
| 触控按钮尺寸 | ⏳ | min-height: 52px |
| 底部抽屉 | ⏳ | 移动端改为底部弹出 |
| 拖动 handle | ⏳ | 抽屉顶部拖动条 |
| 触控反馈 | ⏳ | button:active scale |
| 横屏支持 | ⏳ | landscape orientation |

**移动端抽屉**：

```css
@media (max-width: 768px) {
  .analysis-drawer {
    top: auto;
    bottom: 0;
    height: 45vh;
    width: 100%;
    border-radius: 20px 20px 0 0;
  }
  
  .analysis-drawer.collapsed {
    transform: translateY(calc(100% - 52px));
  }
}
```

---

## ♿ Accessibility Standards

### 已实现

- ✅ `aria-label` 为所有交互按钮
- ✅ `aria-live="polite"` 状态播报区域
- ✅ `.sr-only` 屏幕阅读器专用类
- ✅ `:focus-visible` 金色焦点指示器
- ✅ `prefers-reduced-motion` 动画偏好
- ✅ `prefers-contrast: high` 高对比度支持
- ✅ WCAG AA 颜色对比度

### 待实现

- ⏳ 键盘快捷键 (f/c/r)（暂缓，按需实现）

---

## 📊 Performance Targets

| 指标 | 目标 | 当前状态 |
|------|------|----------|
| CSS Size | < 20KB gzipped | ✅ ~15KB |
| First Paint | < 200ms | ✅ |
| Animation FPS | 60fps | ✅ |
| CLS | < 0.1 | ✅ |

---

## 🔧 Development Guidelines

### CSS Organization

```
style.css
├── 1. Imports & Variables
├── 2. Base & Reset
├── 3. Layout Components
├── 4. UI Components
├── 5. Analysis Drawer
├── 6. States & Modifiers
├── 7. Accessibility
└── 8. Responsive Design
```

### 非目标 (MVP 阶段)

- ❌ 大型前端框架 (React/Vue)
- ❌ 打包工具 (Vite/Webpack) - 后续可引入
- ❌ 复杂图表库
- ❌ PWA / Service Worker
- ❌ 无限制历史回放

---

## 📈 Progress Summary

| Phase | 名称 | 状态 | 完成度 |
|-------|------|------|--------|
| 1 | Code Architecture | ✅ 已完成 | 100% |
| 2 | MVP Visual Baseline | ✅ 已完成 | 100% |
| 3 | Layout Restructure | ✅ 已完成 | 100% |
| 3.5 | Action Notifications & Audio | ✅ 已完成 | 100% |
| 3.6 | Message Queue & Animation Pacing | ✅ 已完成 | 100% |
| 3.7 | Audio Enhancement | ✅ 已完成 | 100% |
| 4 | Immersive Visual Depth | ⏳ 待开始 | 0% |
| 5 | Advanced Animations | ⏳ 待开始 | 0% |
| 6 | Mobile Optimization | ⏳ 待开始 | 0% |

**总体进度：约 67%（核心功能完成，音效系统已增强）**

---

## 📝 Change Log

- **2025-01**: 新增 Phase 3.7 音效增强（简约现代风格 + BGM）
- **2025-01**: 新增 Phase 3.6 消息队列与动画节奏
- **2024-01**: 合并 MODULARIZATION + BEAUTIFICATION 文档
- **2024-01**: Phase 1-3 完成，调整移动端优化到 Phase 6

