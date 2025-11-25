# Frontend Beautification Plan (MVP Enhancement)

**Status:** Ready for Implementation  
**Scope:** Visual enhancement of existing modular frontend (`public/`)  
**Objective:** Professional poker interface with distinctive aesthetics while maintaining MVP simplicity

## 🎯 Design Philosophy

- **Professional Poker Atmosphere**: Authentic casino felt textures with elegant gold accents
- **Distinctive Visual Identity**: Avoid generic "AI slop" aesthetics with unique font and color choices
- **Modern Glassmorphism**: Subtle transparency effects without overwhelming complexity
- **Clear Information Hierarchy**: Color-coded states with intuitive visual feedback
- **Performance-First**: CSS-only enhancements, minimal external dependencies
- **Progressive Enhancement**: Graceful degradation for older browsers
- **Accessibility-First**: Full keyboard navigation and screen reader support

---

## 🌟 Core Visual Upgrades

### 1. Professional Color System

```css
:root {
  /* Professional Poker Palette */
  --felt-green: #1a472a;
  --felt-dark: #0f3018;
  --felt-highlight: #1e5c35;
  --gold-bright: #ffd700;
  --gold-soft: #d4af37;
  --chocolate: #3e2723;
  --cream: #f5f5dc;

  /* Status Colors */
  --winner-glow: #00ff88;
  --loser-dim: #ff4757;
  --action-glow: #ffa502;
  --human-blue: #3742fa;

  /* Card Suit Colors */
  --suit-red: #dc2626;
  --suit-black: #1f2937;

  /* Neutral Grays */
  --gray-900: #0b1520;
  --gray-800: #1c2b3a;
  --gray-700: #2f4863;
  --gray-600: #4a5568;

  /* Semantic Theme Variables (for future theming) */
  --bg-primary: var(--gray-900);
  --bg-secondary: var(--gray-800);
  --bg-elevated: #020617;
  --text-primary: #e6eef5;
  --text-secondary: #9ca3af;
  --text-muted: #6b7280;
  --border-subtle: rgba(255, 255, 255, 0.05);
  --border-accent: rgba(212, 175, 55, 0.3);
}
```

### 2. Distinctive Typography

**设计理念**: 避免 Inter/Roboto 等过度使用的字体，选择更有赌场氛围的独特组合。

```css
/* 独特字体组合 - 高端感 + 清晰数字 */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=JetBrains+Mono:wght@400;500;600&family=DM+Sans:wght@400;500;600&display=swap');

:root {
  --font-display: 'Playfair Display', Georgia, serif;  /* 标题/品牌 */
  --font-body: 'DM Sans', system-ui, sans-serif;       /* 正文 */
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace; /* 数字/筹码 */
}

body {
  font-family: var(--font-body);
  font-weight: 400;
  line-height: 1.5;
  letter-spacing: 0.01em;
}

h1 {
  font-family: var(--font-display);
  font-weight: 700;
  letter-spacing: -0.02em;
}

h2, h3, h4 {
  font-family: var(--font-body);
  font-weight: 600;
  letter-spacing: -0.015em;
}

/* 数字专用样式 - 筹码/底池/下注 */
.pot-amount,
.player-stack,
.player-bet {
  font-family: var(--font-mono);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.pot-amount {
  font-size: 1.6rem;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
}
```

### 3. Textured Poker Table

**MVP 提示**: 首版可以只用简单的径向渐变来区分桌面区域；带噪点纹理和较重的阴影可在 Post‑MVP 再逐步增强。  
**设计理念**: 添加真实毡布纹理感，而非单调渐变。

```css
.poker-table {
  position: relative;
  background: 
    /* SVG 噪点纹理 - 模拟毡布质感 */
    url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E"),
    /* 径向渐变 - 中心亮边缘暗 */
    radial-gradient(ellipse 80% 60% at 50% 50%, var(--felt-highlight) 0%, var(--felt-green) 40%, var(--felt-dark) 100%);
  backdrop-filter: blur(10px);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.6),
    inset 0 1px 0 rgba(255, 255, 255, 0.1),
    inset 0 -2px 8px rgba(0, 0, 0, 0.3);
  border: 3px solid var(--border-accent);
  border-radius: 200px;
}

/* 牌桌内圈装饰线 */
.poker-table::before {
  content: "";
  position: absolute;
  inset: 12px;
  border: 1px solid rgba(212, 175, 55, 0.15);
  border-radius: 188px;
  pointer-events: none;
}
```

### 4. 3D Card Effects with Suit Colors

**MVP 提示**: MVP 阶段优先保证「牌面清晰 + 红黑花色区分」，3D 悬浮和复杂阴影效果可以延后到视觉深化阶段。

```css
.card {
  background: linear-gradient(135deg, #ffffff 0%, #f8f8f8 100%);
  box-shadow:
    0 4px 8px rgba(0, 0, 0, 0.3),
    0 1px 3px rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  transform-style: preserve-3d;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  font-family: var(--font-mono);
  font-weight: 600;
}

.card:hover {
  transform: translateY(-2px) rotateY(5deg);
  box-shadow:
    0 6px 12px rgba(0, 0, 0, 0.4),
    0 2px 4px rgba(0, 0, 0, 0.3);
}

/* 扑克牌花色区分 */
.card[data-suit="h"],
.card[data-suit="d"],
.card.hearts,
.card.diamonds {
  color: var(--suit-red);
}

.card[data-suit="s"],
.card[data-suit="c"],
.card.spades,
.card.clubs {
  color: var(--suit-black);
}

/* 隐藏牌背面设计 */
.card.hidden {
  background: 
    repeating-linear-gradient(
      45deg,
      #1e3a5f 0px,
      #1e3a5f 10px,
      #2a4a6f 10px,
      #2a4a6f 20px
    );
  color: transparent;
  border: 2px solid #3d5a80;
  position: relative;
}

.card.hidden::after {
  content: "♠";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 1.2em;
  color: rgba(255, 255, 255, 0.15);
}
```

### 5. Glassmorphism Components

```css
/* Player Info Cards */
.player-info {
  background: rgba(28, 43, 58, 0.85);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  padding: 8px;
  text-align: center;
  border: 2px solid transparent;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  transition: all 0.3s ease;
}

/* Pot Info Center */
.pot-info {
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  padding: 16px 24px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

/* Analysis Drawer */
.analysis-drawer {
  background: linear-gradient(180deg, 
    rgba(2, 6, 23, 0.98) 0%, 
    rgba(15, 23, 42, 0.95) 100%);
  backdrop-filter: blur(16px);
  border-left: 1px solid var(--border-accent);
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.5);
}

.drawer-section-body {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  padding: 8px 10px;
  border: 1px solid var(--border-subtle);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}
```

---

## ✨ Dynamic Animations（Post-MVP 增强）

> 说明：本节动画主要用于增强沉浸感和“爽感”，不影响核心训练/分析功能。为符合 MVP + 敏捷迭代原则，建议在基础视觉和可访问性稳定后再逐步引入。

### 1. Orchestrated Entry Animation

**设计理念**: 座位依次出现，创造专业的页面加载体验。

```css
/* 座位依次入场动画 */
.seat {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
  animation: seatReveal 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

@keyframes seatReveal {
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Staggered delays */
.seat-1 { animation-delay: 0ms; }
.seat-2 { animation-delay: 60ms; }
.seat-3 { animation-delay: 120ms; }
.seat-4 { animation-delay: 180ms; }
.seat-5 { animation-delay: 240ms; }
.seat-6 { animation-delay: 300ms; }

/* 牌桌入场 */
.poker-table {
  animation: tableReveal 0.6s ease-out;
}

@keyframes tableReveal {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
```

### 2. Winner Highlight Animation

```css
@keyframes winnerGlow {
  0%, 100% {
    box-shadow: 
      0 0 20px rgba(0, 255, 136, 0.6),
      0 4px 12px rgba(0, 0, 0, 0.3);
    border-color: var(--winner-glow);
  }
  50% {
    box-shadow: 
      0 0 35px rgba(0, 255, 136, 0.9),
      0 4px 12px rgba(0, 0, 0, 0.3);
    border-color: #00ffaa;
  }
}

.player-info.winner {
  animation: winnerGlow 2s ease-in-out infinite;
  border: 3px solid var(--winner-glow);
  will-change: box-shadow;
}
```

### 3. Action Indicator Pulse

```css
@keyframes actionPulse {
  0%, 100% { 
    transform: scale(1);
    box-shadow: 0 0 15px rgba(255, 165, 2, 0.5);
  }
  50% { 
    transform: scale(1.03);
    box-shadow: 0 0 25px rgba(255, 165, 2, 0.8);
  }
}

.player-info.active {
  border: 3px solid var(--action-glow);
  animation: actionPulse 1.5s ease-in-out infinite;
  will-change: transform, box-shadow;
}
```

### 4. Chip/Bet Animation

```css
@keyframes chipDrop {
  0% {
    transform: translateY(-20px) scale(0.8);
    opacity: 0;
  }
  60% {
    transform: translateY(3px) scale(1.05);
    opacity: 1;
  }
  100% {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}

.player-bet.show {
  animation: chipDrop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* 筹码图标 */
.player-bet::before {
  content: "🪙";
  margin-right: 4px;
  font-size: 0.9em;
}
```

### 5. Card Deal Animation

```css
@keyframes cardDeal {
  0% {
    transform: translateX(100px) translateY(-50px) rotate(15deg);
    opacity: 0;
  }
  100% {
    transform: translateX(0) translateY(0) rotate(0deg);
    opacity: 1;
  }
}

.player-cards .card {
  animation: cardDeal 0.3s ease-out backwards;
}

.player-cards .card:nth-child(1) { animation-delay: 0ms; }
.player-cards .card:nth-child(2) { animation-delay: 100ms; }
```

---

## 🎨 Luxurious Button Design

**MVP 提示**: 首版可以使用简单的纯色/轻渐变按钮，只要层级清晰、可点击区域足够即可；高光、金属质感和复杂渐变属于后续润色。

```css
.controls button {
  background: linear-gradient(135deg, var(--gray-800) 0%, var(--gray-900) 100%);
  border: 1px solid var(--gray-700);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-weight: 500;
  position: relative;
  overflow: hidden;
  border-radius: 8px;
  padding: 12px 20px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.25s ease;
}

.controls button:hover {
  background: linear-gradient(135deg, var(--gray-700) 0%, var(--gray-800) 100%);
  border-color: var(--gold-soft);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

/* Shine effect on hover */
.controls button::before {
  content: "";
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: linear-gradient(
    45deg, 
    transparent 30%, 
    rgba(255, 255, 255, 0.1) 50%, 
    transparent 70%
  );
  transform: rotate(45deg) translateX(-100%);
  transition: transform 0.6s ease;
}

.controls button:hover::before {
  transform: rotate(45deg) translateX(100%);
}

/* Action Buttons - 保持原有语义色彩 */
.actions button.fold-btn {
  background: linear-gradient(135deg, #b91c1c 0%, #991b1b 100%);
  border-color: #dc2626;
}

.actions button.fold-btn:hover {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
}

.actions button.call-btn {
  background: linear-gradient(135deg, #047857 0%, #065f46 100%);
  border-color: #059669;
}

.actions button.call-btn:hover {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
}

.actions button.raise-btn {
  background: linear-gradient(135deg, #b45309 0%, #92400e 100%);
  border-color: #d97706;
}

.actions button.raise-btn:hover {
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
}
```

---

## ♿ Accessibility Enhancements

### Focus States

```css
/* 清晰的 focus 指示器 */
button:focus-visible,
.drawer-toggle:focus-visible {
  outline: 2px solid var(--gold-bright);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px rgba(255, 215, 0, 0.25);
}

/* 鼠标点击时隐藏 focus ring */
button:focus:not(:focus-visible) {
  outline: none;
}

/* 链接和交互元素 */
a:focus-visible,
[tabindex]:focus-visible {
  outline: 2px solid var(--gold-bright);
  outline-offset: 2px;
}
```

### Motion Preferences

```css
/* 尊重用户动画偏好 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  
  .seat {
    opacity: 1;
    transform: none;
  }
}
```

### Color Contrast

```css
/* 确保足够的对比度 - WCAG AA */
.player-name {
  color: var(--text-primary); /* #e6eef5 on #1c2b3a = 9.2:1 */
}

.player-stack {
  color: #4ade80; /* Green on dark = 8.1:1 */
}

/* High contrast mode support */
@media (prefers-contrast: high) {
  .player-info {
    border: 2px solid white;
  }
  
  button {
    border: 2px solid white;
  }
}
```

---

## 📱 Mobile & Touch Optimization

### Responsive Layout

```css
@media (max-width: 768px) {
  .poker-table {
    width: 95vw;
    height: 55vh;
    max-width: 500px;
    border-radius: 100px;
  }

  .seat { width: 65px; }
  
  /* 优化移动端座位位置 */
  .seat-1 { bottom: 2%; left: 50%; transform: translateX(-50%); }
  .seat-2 { bottom: 12%; right: 3%; }
  .seat-3 { top: 45%; right: 0%; transform: translateY(-50%); }
  .seat-4 { top: 5%; right: 12%; }
  .seat-5 { top: 5%; left: 12%; }
  .seat-6 { top: 45%; left: 0%; transform: translateY(-50%); }

  /* 底部抽屉 */
  .analysis-drawer {
    top: auto;
    bottom: 0;
    height: 45vh;
    width: 100%;
    max-width: 100vw;
    border-radius: 20px 20px 0 0;
    border-left: none;
    border-top: 1px solid var(--border-accent);
  }

  .analysis-drawer.collapsed {
    transform: translateY(calc(100% - 52px));
  }
  
  /* 抽屉拖动指示器 */
  .drawer-header::before {
    content: "";
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    width: 40px;
    height: 4px;
    background: var(--gray-600);
    border-radius: 2px;
  }
}

@media (max-width: 480px) {
  .poker-table {
    height: 50vh;
  }
  
  .seat { width: 55px; }
  
  .player-name { font-size: 0.7rem; }
  .player-stack { font-size: 0.8rem; }
}
```

### Touch Optimization

```css
/* 触控设备优化 */
@media (pointer: coarse) {
  button {
    min-height: 48px;
    min-width: 48px;
    padding: 14px 20px;
  }
  
  .player-info {
    padding: 10px;
  }
  
  .drawer-toggle {
    min-width: 44px;
    min-height: 44px;
  }
}

/* 触控反馈 */
button:active {
  transform: scale(0.96);
  transition: transform 0.1s ease;
}

/* 滑动手势支持 */
.analysis-drawer {
  touch-action: pan-y;
  overscroll-behavior: contain;
}
```

---

## ⚡ Performance Optimization

> 说明：这些优化大多是渐进式增强（progressive enhancement）。MVP 阶段不必一次性全部实现，可在功能稳定后按需启用。

### Hardware Acceleration

```css
/* GPU 加速的动画元素 */
.player-info.winner,
.player-info.active,
.card {
  will-change: transform, box-shadow;
  transform: translateZ(0);
}

/* 移除动画后清理 will-change */
.player-info:not(.winner):not(.active) {
  will-change: auto;
}
```

### Containment

```css
/* 布局隔离优化 */
.seat {
  contain: layout style;
}

.player-info {
  contain: layout paint;
}

/* 长列表虚拟化准备 */
.log-section pre {
  content-visibility: auto;
  contain-intrinsic-size: 0 200px;
}
```

### Progressive Enhancement

```css
/* backdrop-filter 不支持时的回退 */
@supports not (backdrop-filter: blur(10px)) {
  .poker-table {
    background: rgba(26, 71, 42, 0.98);
  }
  
  .player-info {
    background: rgba(28, 43, 58, 0.98);
  }
  
  .analysis-drawer {
    background: rgba(2, 6, 23, 0.99);
  }
}
```

---

## 🚀 Implementation Phases（MVP 优先拆分）

> 原则：先做“信息清晰、可操作”的最低可用版本（MVP），再逐步叠加沉浸式视觉和炫酷动画。每一阶段都可以独立上线，尽量保持小步快跑、可回滚。

### Phase 1: MVP Visual Baseline (Week 1) ✅
- [x] Define CSS variable system with theme support
- [x] Apply professional poker color palette to layout (without heavy textures)
- [x] Implement base typography (body + mono for numbers) with safe fallbacks
- [x] Implement card suit color differentiation
- [x] Add focus states and color contrast tweaks for accessibility
- [x] Add minimal responsive layout for table / seats / controls
- [x] Ensure core controls meet touch target size (≥ 44–48px)

---

### Phase 1.5: 页面布局重构 (Layout Restructure)

**状态**: ✅ 已完成  
**优先级**: 高 - 影响核心用户体验  
**MVP 范围说明**:  
- MVP 必做：P0（牌面显示修复）+ P1（玩家卡片紧凑化、操作栏精简的基础版）  
- 可推迟到 Post‑MVP：部分 P2+ 任务（如高阶抽屉联动、复杂交互方案）

#### 🔍 问题诊断（基于实际运行截图）

| 问题 | 描述 | 影响 |
|------|------|------|
| **牌面显示异常** | 公共牌和手牌显示完整文本（如 "FOUR OF SPADES (4s)"）而非简短格式 "4s" | 严重 - 牌面无法辨认 |
| **玩家卡片过大** | Human 玩家卡片占据过多空间，座位布局不协调 | 中等 - 视觉不平衡 |
| **操作按钮过多** | Raise 预设选项（$24, $28, $36, $60, $398）+ Custom 输入框，布局杂乱 | 中等 - 认知负担重 |
| **空间利用低效** | 牌桌上方/下方空白不均，整体重心偏下 | 轻微 - 美观问题 |

---

#### 1.5.1 整体布局架构

**目标布局**：单栏 + 右侧抽屉，牌桌区域居中，操作栏精简。

```
┌─────────────────────────────────────────────────────────────────────┐
│  Header: Logo + Session Info                                        │
├─────────────────────────────────────────────────────────────────────┤
│  Controls Bar: [Join] [Start] [Next Hand] [Restart]                 │
├───────────────────────────────────────────────┬─────────────────────┤
│                                               │                     │
│              POKER TABLE AREA                 │   Coach Drawer      │
│         (centered, max-width: 680px)          │   (280px, fixed)    │
│                                               │                     │
│   ┌─────────────────────────────────┐         │                     │
│   │     Seat 5       Seat 4         │         │                     │
│   │ Seat 6   [POT + BOARD]   Seat 3 │         │                     │
│   │     Seat 1 (Human)  Seat 2      │         │                     │
│   └─────────────────────────────────┘         │                     │
│                                               │                     │
├───────────────────────────────────────────────┴─────────────────────┤
│  Action Bar: Street + [Fold] [Call $X] [Raise ▼ dropdown/slider]    │
├─────────────────────────────────────────────────────────────────────┤
│  Game Log (collapsible)                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

#### 1.5.2 牌面显示修复

**根本原因**：后端返回的卡牌格式可能是完整描述而非短码。

**修复方案**：
1. 检查后端 `poker/table.py` 返回的卡牌格式
2. 若后端返回长格式，在前端 `renderer.js` 中提取短码
3. 添加卡牌格式化函数：

```javascript
// 提取卡牌短码，如 "FOUR OF SPADES (4s)" -> "4s"
function formatCard(card) {
  if (!card) return '';
  // 如果已经是短格式 (如 "4s", "Kh")
  if (card.length <= 3) return card;
  // 从括号中提取短码
  const match = card.match(/\(([^)]+)\)/);
  return match ? match[1] : card;
}
```

---

#### 1.5.3 玩家卡片紧凑化

**当前问题**：卡片内容纵向堆叠，高度过大，human 卡片尤其突出。

**改进方案**：

```css
.player-info {
  min-width: 70px;
  max-width: 88px;
  padding: 6px;
}

.player-name {
  font-size: 0.72rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
}

.player-stack {
  font-size: 0.8rem;
}

/* 手牌紧凑 */
.player-cards .card {
  width: 22px;
  height: 30px;
  font-size: 0.68rem;
  padding: 2px 3px;
}
```

---

#### 1.5.4 操作栏精简

**当前问题**：
- Custom raise 输入框与按钮混杂
- Raise 预设按钮过多（5-6 个）

**改进方案 A - Dropdown 模式**：

```
┌──────────────────────────────────────────────────────────────┐
│  Street: flop                                                │
├──────────────────────────────────────────────────────────────┤
│  [Fold]   [Call $12]   [Raise ▼]                             │
│                         ├─ 2x ($24)                          │
│                         ├─ 3x ($36)                          │
│                         ├─ Pot ($48)                         │
│                         ├─ All-in ($398)                     │
│                         └─ Custom: [___] [Go]                │
└──────────────────────────────────────────────────────────────┘
```

**改进方案 B - Slider + 快捷按钮**（推荐）：

```
┌──────────────────────────────────────────────────────────────┐
│  Street: flop                                                │
├──────────────────────────────────────────────────────────────┤
│  [Fold]   [Call $12]   │  [2x] [3x] [Pot] [All-in]          │
│                        │  [═══○═══════════] $36  [Raise]    │
│                        │   $24            $398               │
└──────────────────────────────────────────────────────────────┘
```

> MVP 实施建议：  
> - 短期内先实现「简化版」——保留 Custom raise 输入框 + 2–3 个核心预设按钮（如 2x / Pot / All-in），即可显著降低认知负担。  
> - Slider + 更复杂的交互逻辑视为 Phase 2+ 的进阶优化，不纳入当前 MVP 必做范围。

---

#### 1.5.5 牌桌响应式优化

**改进**：使用 `aspect-ratio` 保持比例，座位使用百分比定位。

```css
.poker-table {
  aspect-ratio: 16 / 10;
  max-width: 680px;
  width: 100%;
}

/* 座位百分比定位 */
.seat-1 { bottom: 0; left: 50%; transform: translateX(-50%); }
.seat-2 { bottom: 12%; right: 5%; }
.seat-3 { top: 50%; right: 0; transform: translateY(-50%); }
.seat-4 { top: 5%; right: 12%; }
.seat-5 { top: 5%; left: 12%; }
.seat-6 { top: 50%; left: 0; transform: translateY(-50%); }
```

---

#### 1.5.6 Coach 抽屉优化

**改进**：抽屉展开时，主内容区自动收缩避免遮挡。

```css
/* 抽屉展开时给主内容留空间 */
body.drawer-open main {
  margin-right: 290px;
  transition: margin-right 0.25s ease;
}

/* 移动端：底部弹出 */
@media (max-width: 768px) {
  body.drawer-open main {
    margin-right: 0;
    margin-bottom: 45vh;
  }
}
```

---

#### 1.5.7 实施清单

| 任务 | 优先级 | 文件 | 状态 |
|------|--------|------|------|
| ✅ 修复牌面显示格式 | P0 | `engine.py` | 完成 |
| ✅ 玩家卡片紧凑化 | P1 | `style.css` | 完成 |
| ✅ 操作栏精简（Slider + 快捷按钮方案 B） | P1 | `actions.js`, `style.css` | 完成 |
| ✅ 牌桌 aspect-ratio + 座位百分比 | P2 | `style.css` | 完成 |
| ✅ 抽屉不遮挡主内容 | P2 | `style.css`, `renderer.js` | 完成 |
| ✅ Game Log 折叠 | P3 | `index.html`, `style.css` | 完成 |

**MVP 完成定义（Frontend DoD）**  
- 当前阶段：完成 Phase 1（上文已全部 ✅）并落地本表中的 **P0 + 所有 P1 任务**，即可满足 MVP 版本的前端要求。  
- P2 及以后任务作为渐进增强，在不阻塞训练/分析主流程的前提下按优先级逐步推进。

---

### Phase 2: Usability & Mobile Polish (Week 2)
- [ ] Responsive breakpoints refinement for tablet and mobile
- [ ] Touch-optimized button sizes and spacing
- [ ] Mobile analysis drawer layout（含拖动 handle，若当期有需求）
- [ ] Touch feedback animations（按钮按下缩放等轻量效果）
- [ ] Landscape orientation support

### Phase 3: Immersive Visual Depth (Post-MVP)
- [ ] Apply textured poker table background（噪点 + 阴影）
- [ ] Add glassmorphism to player cards and pot info
- [ ] Implement 3D card effects and hidden card back design
- [ ] Luxurious button gradients and hover shine effects
- [ ] Winner/loser highlighting styles（先实现静态状态样式）

### Phase 4: Advanced Animations & Effects (Future)
- [ ] Orchestrated seat reveal animation
- [ ] Winner/loser highlighting with glow effects
- [ ] Action indicator pulse animation
- [ ] Chip/bet drop animation
- [ ] Card deal animation
- [ ] Theme switching (light/dark)
- [ ] Sound effect coordination hooks
- [ ] Particle effects for big wins
- [ ] Advanced micro-interactions
- [ ] Custom scrollbar styling

---

## 📊 Implementation Metrics

### Performance Targets
| Metric | Target | Notes |
|--------|--------|-------|
| CSS Size | < 20KB gzipped | Including fonts |
| First Paint | < 200ms | Critical CSS inline |
| Animation FPS | 60fps | On mid-range devices |
| CLS | < 0.1 | No layout shifts |

### Browser Support
| Browser | Support Level |
|---------|---------------|
| Chrome/Edge 88+ | Full |
| Firefox 78+ | Full |
| Safari 14+ | Full |
| iOS Safari 14+ | Full |
| Samsung Internet | Full |
| IE11 | Graceful degradation |

### Accessibility Compliance
- **WCAG 2.1 AA**: Color contrast, focus indicators
- **Keyboard Navigation**: Full support
- **Screen Readers**: ARIA labels, live regions
- **Motion**: `prefers-reduced-motion` support

---

## 🔄 CSS Organization Structure

```
public/style.css
├── 1. Imports & Variables
│   ├── Google Fonts import
│   ├── :root CSS custom properties
│   └── Theme variables
├── 2. Base & Reset
│   ├── Box-sizing, margin reset
│   ├── Typography defaults
│   └── Accessibility utilities (.sr-only)
├── 3. Layout Components
│   ├── Header & Session Info
│   ├── Controls Bar
│   ├── Poker Table
│   ├── Seats Container
│   └── Game Controls
├── 4. UI Components
│   ├── Player Info Cards
│   ├── Playing Cards
│   ├── Buttons (all variants)
│   ├── Pot & Board Display
│   └── Analysis Drawer
├── 5. States & Modifiers
│   ├── .active, .winner, .loser
│   ├── .human, .folded
│   └── .collapsed, .show
├── 6. Animations & Keyframes
│   ├── Entry animations
│   ├── State animations
│   └── Interaction feedback
├── 7. Responsive Design
│   ├── Tablet (max-width: 768px)
│   ├── Mobile (max-width: 480px)
│   └── Touch device overrides
└── 8. Accessibility & Preferences
    ├── Focus states
    ├── High contrast mode
    └── Reduced motion
```

---

## 🎯 Visual Identity Summary

### Design Tokens
| Token | Value | Usage |
|-------|-------|-------|
| Primary Font | Playfair Display | Headers, branding |
| Body Font | DM Sans | UI text, labels |
| Mono Font | JetBrains Mono | Numbers, chips, bets |
| Accent Color | #d4af37 (Gold) | Borders, highlights |
| Success | #00ff88 | Winner states |
| Warning | #ffa502 | Action required |
| Error | #ff4757 | Fold, loss |

### Key Visual Differentiators
1. **Textured felt table** - Not flat gradients
2. **Distinctive typography** - Casino-elegant fonts
3. **Orchestrated animations** - Coordinated reveals
4. **Glassmorphism depth** - Modern premium feel
5. **Rich card styling** - Suit colors, 3D effects

---

**Conclusion**: This enhanced plan delivers a distinctive, professional poker interface that avoids generic AI aesthetics while maintaining excellent performance and accessibility. The phased approach allows incremental improvements without disrupting the MVP functionality.
