# 部署前检查清单（公测 MVP）

> **用途**：供执行部署的 agent / 运维人员按顺序完成上线前配置与验收。  
> **适用版本**：包含 P0 加固（WS 心跳、每访客独立桌、LLM Admin 修复）之后的代码。  
> **关联文档**：`docs/DEPLOY_EXPLAIN1THING_TOP_CARDS.md`（完整部署手册）、`docs/P0_MVP_HARDENING_PLAN.md`（P0 技术说明）。

---

## 0. 部署目标（完成定义）

全部勾选后，才可对外发放测试链接：

- [ ] 页面 `https://<域名>/cards/` 可打开，静态资源正常
- [ ] WebSocket 可连接，断线后能自动重连（无需手动刷新）
- [ ] 两个浏览器同时打开，各自独立对局、互不干扰
- [ ] 服务器重启后刷新页面，不再出现 `table not found`，可重新 Start Session
- [ ] LLM Admin 页可保存配置，Test all tiers 通过（若启用 LLM）
- [ ] 游戏内邀请码 + Ask once 返回 AI 建议（`reason` 为 `llm_actions`）
- [ ] `python -m tools.e2e_check` 在容器内全部 `[OK]`（或按策略 `[SKIP]` LLM）

---

## 1. 服务器与环境前提

| 项目 | 要求 | 说明 |
|------|------|------|
| 系统 | Debian 12 或同等 Linux | 已有 Nginx + TLS |
| 内存/CPU | **推荐 2C2G** | 1C1G 可跑但牌力计算易卡顿、OOM 重启 |
| 后端进程 | **`--workers 1` 固定** | 多 worker 会导致牌局状态分裂 |
| 端口 | `127.0.0.1:8010` | 仅本机监听，公网经 Nginx `/cards/` 反代 |
| 数据持久化 | `./data` 挂载到容器 | 邀请码库 `invites.db`、LLM 配置 `llm_config.json` |

Nginx `/cards/` 反代必须包含 WebSocket 头（已有则跳过）：

```nginx
proxy_set_header Upgrade           $http_upgrade;
proxy_set_header Connection        $connection_upgrade;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

---

## 2. 代码拉取与构建（部署机上执行）

```bash
cd /opt/poker-coach-alpha   # 或你的部署目录
git pull
cp -n .env.example .env     # 首次部署；已有 .env 则跳过
chmod 600 .env
docker compose up -d --build
docker compose logs -f poker --tail 50
```

确认容器健康：

```bash
curl -I http://127.0.0.1:8010/cards/ | head -3
# 期望 HTTP/1.1 200
```

---

## 3. `.env` 必填项（部署前必须写好）

在服务器编辑 `/opt/poker-coach-alpha/.env`。**改完后必须重启容器**：

```bash
docker compose restart poker
```

### 3.1 安全（生产必做）

```bash
# 随机 32+ 字符；用于 /admin/llm 页面 Unlock
ADMIN_TOKEN=<生成一个随机长字符串>

# 生产必须为 0
LOCAL_ADMIN_BYPASS=0
LOCAL_INVITE_BYPASS=0

# Nginx 反代 + POKER_BIND_ADDR=127.0.0.1 时保持默认即可
FORWARDED_ALLOW_IPS=*
POKER_BIND_ADDR=127.0.0.1
```

生成 `ADMIN_TOKEN` 示例：

```bash
openssl rand -hex 32
```

> **未设置 `ADMIN_TOKEN` 时**：Admin 页所有保存/测试请求返回 403，表现为「配置输不进去」——这是最常见上线故障之一。

### 3.2 LLM（若要对测试者开放 AI 教练）

```bash
AI_PROVIDER=openai          # 或 gateway；dummy 则仅启发式建议
OPENAI_API_KEY=<你的 Key>

# GLM 官方示例（模型名以控制台为准，不要照抄占位符）
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4

# 可选：首次部署前在 .env 预填；也可部署后通过 Admin 页填写并保存到 data/llm_config.json
AI_MODEL_TIER=balanced
AI_SMART_MODEL=<网关上真实模型 ID>
AI_BALANCED_MODEL=<网关上真实模型 ID>
AI_FAST_MODEL=<网关上真实模型 ID>

# 上线初期建议 1，确认 LLM 被调用；稳定后改 0
AI_COACH_DEBUG=1
```

### 3.3 可选调优

```bash
# 同时在线桌数上限（默认 50）
TABLE_LIMIT=50

# 无 WS 连接的空闲桌回收时间，秒（默认 1800 = 30 分钟）
TABLE_TTL_SECONDS=1800
```

---

## 4. 部署后必做：LLM Admin 配置（启用 LLM 时）

**前提**：`.env` 中已设置 `ADMIN_TOKEN` 且容器已重启。

1. 浏览器打开：`https://<域名>/cards/admin/llm`
2. 在 **Admin Token** 输入框填入 `ADMIN_TOKEN`，点 **Unlock**
   - 不要把 token 写在 URL 里（会进 access log）
3. 填写：
   - **Provider**：`openai` 或 `gateway`
   - **API Base**：如 `https://open.bigmodel.cn/api/paas/v4`
   - **API Key**：你的 Key（留空则沿用已保存的 key）
4. 三个 Tier（smart / balanced / fast）的 **Model** 全部改为网关上**真实存在**的模型 ID
5. 点 **Save config** → 状态栏应显示 `Saved.`
6. 点 **Fetch model list** → 应列出可用模型
7. 点 **Test all tiers** → 三档应显示 `ok`（若失败，看 `empty_response` 或具体错误）

服务器本机快速确认 LLM 已识别：

```bash
curl -s http://127.0.0.1:8010/cards/settings/ai_model | python3 -m json.tool
# 期望 "llm_available": true
```

配置持久化路径：`./data/llm_config.json`（随 `./data` 卷保留）。

---

## 5. 部署后必做：邀请码

LLM 功能对用户 gated 在邀请码之后（生产环境 `LOCAL_INVITE_BYPASS=0`）。

```bash
# 创建邀请码（建议加配额）
docker compose exec poker python -m tools.manage_invites create \
  --note "beta-tester-1" \
  --max-uses 500 \
  --daily-quota 50

# 查看列表
docker compose exec poker python -m tools.manage_invites list
```

将邀请码发给测试者；对方在游戏页 **Invite Code** 输入框填入 → 打开 **LLM** 开关 → 点 **Ask once**。

---

## 6. 自动化验收（容器内执行）

```bash
docker compose exec poker python -m tools.e2e_check --verbose
```

全部步骤应为 `[OK]`。若暂未配置 LLM：

```bash
docker compose exec poker python -m tools.e2e_check --skip-llm --verbose
```

额外手动验证 P0 项（脚本可能未覆盖）：

```bash
# 1) 按 session 建桌：两个 session 得到不同 table_id
curl -s -X POST http://127.0.0.1:8010/cards/tables \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"deploy-check-a"}' | python3 -m json.tool

curl -s -X POST http://127.0.0.1:8010/cards/tables \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"deploy-check-b"}' | python3 -m json.tool
# 两个 table_id 应不同，且以 t_ 开头

# 2) WS ping/pong（需 websocat 或浏览器 DevTools）
# 连上 wss://<域名>/cards/ws/tables/<table_id>?player_id=human
# 发送 {"type":"ping","t":123} 应收到 {"type":"pong","t":123}

# 3) 空引擎 state 不 404
curl -s http://127.0.0.1:8010/cards/tables/t_nonexistent123/state | python3 -m json.tool
# 期望 HTTP 200，"table": null
```

---

## 7. 浏览器手动验收清单

按顺序勾选：

### 7.1 基础连通

- [ ] 打开 `https://<域名>/cards/`，页面与样式正常
- [ ] DevTools → Network → WS：连接 `.../cards/ws/tables/t_...?player_id=human`，状态 101
- [ ] 点 **Start Session**，能发牌、操作、打完一手

### 7.2 P0：多桌隔离

- [ ] 浏览器 A 与 B（或普通 + 隐身）同时打开，各自 Start Session
- [ ] A 的操作/底牌不出现在 B 的界面

### 7.3 P0：断线恢复

- [ ] 开局后等待 2 分钟不操作，连接应通过心跳保持（或短暂重连后恢复）
- [ ] DevTools 里执行 `wsManager.ws.close()`（若可访问）或短暂断网，页面应自动 Reconnecting 并恢复

### 7.4 P0：服务重启

```bash
docker compose restart poker
```

- [ ] 刷新游戏页，**不出现** `table not found`
- [ ] 日志显示 `Session was reset (server restarted)`，可重新 Start Session

### 7.5 LLM 端到端（若已配置）

- [ ] 输入有效邀请码，Invite 状态变绿
- [ ] 打开 LLM 开关，选一档模型
- [ ] **Ask once** 返回自然语言建议（非仅启发式）
- [ ] 容器日志无大量 `dummy_provider` / `invite_code_required`（在已填码情况下）

---

## 8. 故障排查速查

| 现象 | 最可能原因 | 处理 |
|------|-----------|------|
| Admin 页无法保存 / Unlock 失败 | 未设 `ADMIN_TOKEN` 或未重启 | 设 token → `docker compose restart poker` |
| Test all tiers 全失败 | API Base / Key 错，或模型名不存在 | Admin 页 Fetch model list；改真实模型 ID |
| Test 显示 `empty_response` | 推理型模型 token 不足或网关异常 | 换模型或查网关日志；Admin 测试端点已用 max_tokens=256 |
| 游戏内 LLM 无建议，`dummy_provider` | `AI_PROVIDER=dummy` 或 key 未配置 | 检查 `llm_available`；重做 Admin Save |
| `invite_code_required` | 未填码或码无效/超额 | `manage_invites list` / `check <code>` |
| 502 on `/cards/` | 容器未起或 Nginx 反代错 | `docker compose ps`；`journalctl` / `docker compose logs` |
| WS 频繁断开 | Cloudflare/Nginx 超时 | 确认 Nginx WS 头；客户端已有 25s 心跳 |
| 多人同桌互相干扰 | 旧版前端未按 session 建桌 | 确认已部署 P0 代码；硬刷新清缓存 |
| OOM / 频繁重启 | 1C1G 内存不足 | 升 2C2G；调低 `docker-compose` memory limit |

LLM 详细排查顺序见 `docs/DEPLOY_EXPLAIN1THING_TOP_CARDS.md` 第 15.2.2 节「LLM 配置不生效排查顺序」。

---

## 9. 回滚

```bash
cd /opt/poker-coach-alpha
git log -1 --oneline          # 记下当前 commit
git reset --hard <上一已知可用 commit>
docker compose up -d --build
```

仅回滚 Nginx：删除 `/cards` 两个 `location` 块后 `nginx -t && systemctl reload nginx`。

---

## 10. 已知限制（公测阶段接受）

- 牌局状态在**内存**中：进程重启 = 当前局丢失（刷新后可重新 Start，不再 404）
- 单进程 `--workers 1`：无法水平扩展多实例
- LLM Key 在服务端配置（非用户自带 Key）；邀请码控制调用配额
- 1C1G 服务器：可玩但 CPU/内存压力大，建议 2C2G

---

## 11. 执行记录模板（给其他 agent 填）

```
部署日期：
部署人/agent：
Git commit：
域名：

[ ] 第 2 节 构建完成
[ ] 第 3 节 .env 已配置并 restart
[ ] 第 4 节 LLM Admin（或标记 N/A）
[ ] 第 5 节 邀请码已创建：__________
[ ] 第 6 节 e2e_check 通过
[ ] 第 7 节 浏览器验收通过

备注：
```
