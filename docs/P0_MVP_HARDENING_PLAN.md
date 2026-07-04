# P0 计划：MVP 公测前的三项加固（交接执行文档）

> 本文档是决策完成（decision-complete）的执行计划，供接力的 agent/模型直接实施。
> 背景结论来自 2026-07-04 的架构评审：项目代码质量良好、81 个测试全绿，
> 但存在三个阻塞公测的问题。本文按工作流拆分，每个工作流可独立提交。

## 背景与根因（评审结论摘要）

1. **全服务器只有一张 `default` 桌**（`app/main.py` 的 `_engines` 字典在启动时只建一个引擎），
   所有访问者共享同一桌、同一 seat 1，两人同时打开页面会互相看到底牌、互相操作。
2. **WebSocket 没有应用层心跳**，域名经 Cloudflare 代理（空闲 ~100 秒即断开 WS）；
   前端重连策略是固定 1 秒间隔、最多 5 次（`public/modules/websocket.js`），服务抖动超过 5 秒就永久放弃。
   进程重启后内存状态清空，REST 返回 404 `table not found`——这就是用户看到的"牌局突然中断"。
3. **LLM 管理页（/admin/llm）链路有四个缺陷**：
   - 云端未配置 `ADMIN_TOKEN` 时所有 admin 请求 403，页面表现为"输入配置无效"；
   - `poker/llm_config.py` 的 `test_gateway_model` 用 `max_tokens=8`，对 GLM 等推理型模型
     （先输出 reasoning 再输出 content）必然返回空 content，**正确配置也会测试失败**；
   - `save_llm_config` 允许保存 `provider=openai` 但 `api_key` 为空的配置，运行时静默降级为 DummyProvider；
   - 三个 tier 的默认模型名（`gpt-5.2-pro` / `gpt-5.1-chat-latest` / `deepseek-chat`）是历史测试网关的占位值，
     对 GLM 官方端点不存在，不改就全部调用失败并静默降级为启发式建议。

## 约束（必须遵守）

- 不引入 Redis / Postgres / 新的重型依赖。全部在现有 FastAPI + 内存架构内解决。
- 保持 `--workers 1` 单进程模型不变。
- 不改 `poker/engine.py` 的牌局逻辑。
- 遵循仓库规范（AGENTS.md）：类型注解、Conventional Commits、
  提交前 `pytest -q && ruff check . && black --check .` 必须全绿。
- 三个工作流相互独立，建议按 WS-A → WS-B → WS-C 顺序各自成一个 commit（或 PR）。

---

## WS-A：WebSocket 心跳 + 指数退避重连（工作量最小，先做）

### A1. 服务端：响应 ping

文件：`app/main.py`，`ws_table` 的主循环（`while True: data = await websocket.receive_json()` 处）。

在处理 `client_settings` 分支之前加：

```python
if data.get("type") == "ping":
    await websocket.send_json({"type": "pong", "t": data.get("t")})
    continue
```

不需要锁（不触碰引擎状态）。

### A2. 客户端：心跳与活性检测

文件：`public/modules/websocket.js`（`WebSocketManager`）。

- 新增常量：`PING_INTERVAL_MS = 25000`，`PONG_TIMEOUT_MS = 10000`。
- 连接 open 后启动 `setInterval`：每 25s 发送 `{type: 'ping', t: Date.now()}`，
  同时启动一个 10s 的 pong 超时定时器；收到 `pong` 就清除。
- **`pong` 消息在 `onmessage` 里拦截消化，不 emit 给上层**（否则会进入
  `messageQueue` 被节流延迟，破坏活性判断；`public/app.js` 无需感知 pong）。
- pong 超时未到 → 调用 `this.ws.close()` 主动触发既有的 `onclose` → 重连路径。
- close/error 时清除所有定时器，避免泄漏。

### A3. 客户端：重连策略改为指数退避 + 不放弃

同文件 `tryReconnect()`：

- 延迟序列：`min(1000 * 2 ** attempts, 30000)` 加 0~500ms 随机抖动。
- `maxRetries` 改为 `Infinity`（保留 options 覆盖能力，测试用）。
- 重连成功后 `reconnectAttempts` 归零（现有逻辑已做）。
- `reconnect_failed` 事件保留但实际不再触发；`public/app.js` 中对应 UI 不用改。

### A4. 验收标准

- 本地起服务，浏览器打开后在 DevTools 里手动 `wsManager.ws.close()`，观察自动重连并收到 snapshot。
- 断网 2 分钟再恢复，页面无需刷新即恢复（重连计数增长、退避间隔拉长）。
- 新增 pytest：用 `fastapi.testclient.TestClient` 的 `websocket_connect`，
  发送 `{"type": "ping", "t": 123}`，断言收到 `{"type": "pong", "t": 123}`。

提交：`fix: add ws heartbeat and exponential backoff reconnect`

---

## WS-B：每访客一张桌（多人隔离，核心工作流）

### B1. 后端：按会话建桌 + get_or_create

文件：`app/main.py`。

1. `POST /tables` 改为接受可选 JSON body `{"session_id": "<hex>"}`：
   - `table_id = "t_" + hashlib.sha256(session_id.encode()).hexdigest()[:12]`；
     body 缺失或为空时退回 `DEFAULT_TABLE_ID`（兼容旧客户端与本地 curl 调试）。
   - 新增辅助函数 `_get_or_create_engine(table_id: str) -> TableEngine`：
     不存在则 `TableEngine(EngineConfig(session_id=table_id))` 并放入 `_engines`。
   - **容量上限**：新建前检查 `len(_engines) >= TABLE_LIMIT`（env `TABLE_LIMIT`，默认 50），
     超限返回 503 `{"error": "table_limit"}`。已存在的 table_id 不受限。
2. 所有按 `table_id` 查引擎的入口（`join` / `start` / `next` / `restart` / `state` /
   `ai_advice/llm` / `ws_table`）改用 `_get_or_create_engine`，**删除 404 `table not found` 分支**：
   - 服务器重启后旧 table_id 会拿到一个 `state is None` 的新引擎；
   - `GET /state` 在 `engine.state is None` 时返回 200 `{"type": "snapshot", "seq": 0, "table": null}`；
   - WS 连接时 `state is None` 则不发 snapshot（现有行为已如此）。
3. **活跃度跟踪与 TTL 回收**：
   - 新增 `_table_last_activity: Dict[str, float]`，在 WS connect/收到消息、
     以及每个状态变更 REST 端点里用 `time.monotonic()` 刷新。
   - FastAPI startup 事件里启动后台任务：每 60s 扫描，满足
     「无活跃 WS 连接（`manager.active_connections.get(tid)` 为空）
     且空闲超过 `TABLE_TTL_SECONDS`（env，默认 1800）」的桌子，
     从 `_engines`、`_table_locks`、`_table_last_activity` 中删除，
     并清理 `_hand_strength_cache` 中以该 table_id 开头的 key。
   - `DEFAULT_TABLE_ID` 不回收（本地开发方便）。

### B2. 前端：先取 table_id，再连 WS

文件：`public/app.js`、`public/modules/websocket.js`、`public/modules/actions.js`、
`public/modules/state.js`、`public/utils/constants.js`。

1. `constants.js` 或 `app.js` 中新增 `getTableSessionId()`：
   复用 `_getInviteSessionId()` 的实现模式（`crypto.getRandomValues` 生成 32 位 hex，
   存 `localStorage`，key 用 `pokerCoach.tableSessionId`）。注意与 invite session id 是两个独立的 key。
2. 启动流程重构（`app.js` 底部的初始化段）：
   - 先 `POST withBase('/tables')`，body `{session_id: getTableSessionId()}` → 得到 `table_id`；
     失败（如服务器重启中）则 1s/2s/4s…退避重试，页面状态显示 connecting。
   - 用返回的 `table_id` 构造 WS URL：
     `wsAbsoluteUrl(\`/ws/tables/${tableId}?player_id=human\`)`，再 `wsManager.connect()`。
     （`WebSocketManager` 构造函数已支持传入 url，把当前"构造时写死 default"的逻辑
     改成由 `app.js` 显式传入。）
   - `gameState` 新增 `setTableId(id)` / 让 `getTableId()` 优先返回显式设置的值，
     snapshot 里的 `table_id` 作为兜底。
3. `actions.js`：`start()` / `nextHand()` 里的 `DEFAULT_TABLE_ID` 全部替换为
   `this.gameState.getTableId()`；`join()` 不再自己 POST /tables（bootstrap 已建桌），
   直接 `POST /tables/${gameState.getTableId()}/join`。
4. snapshot 为 `null` 的处理（对应服务器重启后的空引擎）：
   `app.js` 的 `processMessage` snapshot 分支和初始加载路径中，
   `msg.table` 为 null 时重置 UI 到初始"Start Session"状态并 log
   `Session was reset (server restarted)`，不报错。

### B3. 验收标准

- 两个不同浏览器（或普通+隐身窗口）同时打开，各自独立发牌、互不可见对方状态。
- 同一浏览器刷新页面回到同一张桌（localStorage session id 稳定）。
- 重启服务器后刷新页面：不再出现 `table not found`，UI 回到可 Start 状态。
- 新增 pytest（放 `tests/test_multi_table.py`）：
  - 两个不同 session_id POST /tables 得到不同 table_id；同一 session_id 幂等。
  - 对两桌分别 start，各自 state 互不影响。
  - TTL 回收：把 `_table_last_activity` 直接改成过期值后手动调用回收函数一次，
    断言引擎被清除且 default 桌保留（把扫描逻辑抽成可直接调用的
    `_evict_idle_tables(now: float) -> list[str]` 以便测试，后台任务只是循环调它）。
  - 超过 TABLE_LIMIT 时返回 503。

提交：`feat: per-visitor tables with TTL eviction`

---

## WS-C：LLM 管理链路修复（GLM 可用性）

### C1. 修 test 端点对推理型模型的假失败

文件：`poker/llm_config.py` 的 `test_gateway_model`。

- `max_tokens` 从 8 提到 **256**，提示词保持 "Reply with exactly: ok"。
- content 为空时不要直接判失败：返回
  `{"ok": False, "error": "empty_response", "model": model, "finish_reason": <finish_reason>}`，
  让管理页能区分"网络/鉴权错误"和"模型没吐 content"。
- 把对 provider SDK 的异常转成结构化错误：捕获 `Exception as exc`，返回
  `{"ok": False, "error": f"{type(exc).__name__}: {exc}", "model": model}`
  （当前异常直接抛给端点，只剩一个笼统的 400）。

### C2. 保存校验：openai/gateway 必须有 key

文件：`poker/llm_config.py` 的 `save_llm_config`。

- 合并 payload 与现有配置之后（保留"留空表示沿用旧 key"的语义），若
  `provider in {"openai", "gateway"}` 且最终 `api_key` 为空 → `raise ValueError("missing_api_key")`。
- 管理页已把 `data.error` 显示在状态栏，无需改前端；但在
  `app/main.py` 的 `set_llm_admin_config` 保持 400 透传（现有逻辑已满足）。

### C3. 默认档位与文档对齐 GLM

- `.env.example`：把 `AI_SMART_MODEL` / `AI_BALANCED_MODEL` / `AI_FAST_MODEL` 的示例值与注释
  改为说明"必须填你的网关上真实存在的模型 ID"，并给出 GLM 官方端点示例
  （`OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4`，模型名以 bigmodel 控制台为准，
  形如 `glm-4.x`；**不要臆造具体版本号**，写成占位提示即可）。
- `docs/DEPLOY_EXPLAIN1THING_TOP_CARDS.md` 第 15.2.2 节后追加一小节
  「LLM 配置不生效排查顺序」：
  1. 服务器 `.env` 已设置 `ADMIN_TOKEN` 且容器/服务重启过
     （未设置时 admin 页任何输入都是 403，表现为"配置输不进去"）；
  2. 管理页 Unlock → 三个 tier 的 model 全部改为网关上真实存在的模型 ID → Save；
  3. 点 "Fetch model list" 验证 base/key 连通；
  4. 点 "Test all tiers"；
  5. `curl http://127.0.0.1:8010/cards/settings/ai_model` 确认 `llm_available: true`。

### C4. 验收标准

- 新增/更新 pytest（`tests/test_llm_admin_config.py` 已有基础）：
  - `save_llm_config({"provider": "openai", "api_key": ""})` 在无既有 key 时抛 `missing_api_key`；
    有既有 key 且 payload 省略 `api_key` 时保存成功并沿用旧 key。
  - `test_gateway_model` 用 monkeypatch 假 client：content 为空时返回
    `ok=False, error="empty_response"`；SDK 抛异常时返回结构化 error 字符串。
- 手动验收（需要真实 GLM key，由项目 owner 在云端执行）：管理页配置 GLM base + key +
  真实模型名后，"Test all tiers" 三档 ok，游戏内 Ask once 返回 LLM 建议
  （`reason` 为 `llm_actions` 而非 `dummy_provider` / `llm_error_heuristic_actions`）。

提交：`fix: harden LLM admin config validation and gateway test endpoint`

---

## 不在本次范围（明确排除，避免执行者发散）

- 引擎状态落盘/重启恢复（P1）；结构化日志（P1）；多人同桌对战（V3）。
- 不改 `poker/ai_coach.py` 的建议生成逻辑，不动邀请码系统。
- 不调整 Nginx / Cloudflare 配置（心跳方案不依赖基础设施变更）。

## 完成定义（DoD）

1. `pytest -q && ruff check . && black --check .` 全绿（含新增测试）。
2. 本地双浏览器隔离验证通过（B3 第一条）。
3. 三个 commit 遵循 Conventional Commits，逐工作流独立提交。
4. 云端部署后由 owner 执行 C4 的手动验收与 `.env` 的 `ADMIN_TOKEN` 配置。
