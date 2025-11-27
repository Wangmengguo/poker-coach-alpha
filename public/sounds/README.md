# 🎵 Poker Coach 音效指南

本目录用于存放自定义音效和背景音乐。

## 默认行为

系统已内置**简约现代风格的合成音效**，无需下载任何文件即可使用。如果你想要更真实的音效体验，可以按照下面的指南下载音效文件。

---

## 🎰 音效文件（可选）

将以下音效文件放入此目录，系统会自动加载并使用：

| 文件名 | 用途 | 建议时长 | 风格建议 |
|--------|------|----------|----------|
| `check.mp3` | Check（过牌） | 50-100ms | 轻柔敲击/点击声 |
| `call.mp3` | Call（跟注） | 80-150ms | 单个筹码落下声 |
| `raise.mp3` | Raise（加注） | 100-200ms | 多个筹码堆叠声 |
| `fold.mp3` | Fold（弃牌） | 80-150ms | 卡牌放下声 |
| `bet.mp3` | Bet（下注） | 80-150ms | 筹码投入声 |
| `turn.mp3` | 轮到你行动 | 150-300ms | 柔和提示音 |
| `win.mp3` | 赢得底池 | 200-400ms | 轻快成功音 |
| `deal.mp3` | 发牌 | 30-80ms | 卡牌滑动声 |

### 推荐音效来源（免费）

1. **Pixabay Sound Effects** - https://pixabay.com/sound-effects/
   - 搜索: "poker chips", "card", "notification", "click"
   - ✅ 免费商用，无需署名

2. **Freesound** - https://freesound.org/
   - 搜索: "casino chip", "card deal", "ui click"
   - ⚠️ 注意检查许可证（选择 CC0 或 CC-BY）

3. **Zapsplat** - https://www.zapsplat.com/
   - 搜索: "poker", "casino", "ui"
   - ⚠️ 需要免费注册

### 音效处理建议

使用 **Audacity**（免费）处理下载的音效：
1. 裁剪到合适长度
2. 标准化音量（-3dB）
3. 添加淡入/淡出（10-20ms）
4. 导出为 MP3（128kbps 足够）
5. 控制文件大小 < 30KB

---

## 🎶 背景音乐

将背景音乐文件命名为 `bgm-lounge.mp3` 放入此目录。

### 推荐风格
- Lofi / Chill Beats
- Jazz Lounge
- Ambient Electronic
- 时长：2-5分钟（会循环播放）

### 推荐来源

1. **Pixabay Music** - https://pixabay.com/music/
   - 搜索: "lofi", "lounge", "ambient", "chill"
   - ✅ 免费商用

2. **Free Music Archive** - https://freemusicarchive.org/
   - 搜索: "lounge", "jazz", "ambient"
   - ⚠️ 检查许可证

3. **YouTube Audio Library** - https://studio.youtube.com/channel/audio
   - 需要 YouTube 账号
   - ✅ 免费使用

### 推荐曲目（示例搜索词）
- "lofi poker night"
- "jazz lounge background"
- "chill ambient loop"
- "casino lounge music"

---

## 📁 目录结构

```
public/sounds/
├── README.md          # 本文件
├── check.mp3          # (可选)
├── call.mp3           # (可选)
├── raise.mp3          # (可选)
├── fold.mp3           # (可选)
├── bet.mp3            # (可选)
├── turn.mp3           # (可选)
├── win.mp3            # (可选)
├── deal.mp3           # (可选)
└── bgm-lounge.mp3     # (可选) 背景音乐
```

---

## 🔧 技术说明

- **格式**: MP3（推荐）或 OGG
- **采样率**: 44.1kHz 或 48kHz
- **比特率**: 128-192kbps
- **声道**: 单声道或立体声均可
- **文件大小**: 音效 < 30KB，BGM < 3MB

系统会在加载时尝试预加载这些文件。如果文件不存在，会自动使用内置的合成音效。

---

## 🎮 使用方式

1. **音效开关**: 点击 🔊/🔇 按钮切换音效
2. **背景音乐**: 点击 🎵/🎶 按钮切换背景音乐
3. **音量**: 目前使用默认音量（后续版本会添加音量滑块）

---

*Last updated: 2025-01*

