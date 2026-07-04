# 部署手册：Poker Coach Alpha 上线到 `explain1thing.top/cards`（Debian 12 / 单实例 MVP）

本文档用于**手把手**指导你把本项目部署到自购服务器，并确保：

- **不影响**你现有个人首页（`https://explain1thing.top/`）与其它站点路径
- 本项目完整隔离在：`https://explain1thing.top/cards/`
- 支持 **WebSocket**（游戏实时通信）
- 单实例（1C1G）以 **systemd** 管理进程，Nginx 反代

## 部署方式选择

本项目支持两种部署方式：

1. **Docker 部署（推荐）**：使用 Docker Compose，更简单、隔离性更好
   - 适合：快速部署、容器化环境、需要隔离的场景
   - 详见：第 15 节「Docker 部署方式（替代方案）」

2. **传统部署（systemd + venv）**：直接在服务器上运行 Python
   - 适合：对 Docker 不熟悉、需要更多控制、资源受限的场景
   - 详见：第 4-14 步（systemd + venv）

> **提示**：两种方式都使用相同的 Nginx 配置，只是后端服务的运行方式不同。

---

## 0. 你的当前信息（已确认）

- **域名**：`explain1thing.top`
- **服务器**：Debian 12 64-bit
- **公网 IP**：`198.23.164.200`
- **资源**：1C1G
- **Nginx 站点配置**：`/etc/nginx/sites-available/explain1thing_ssl.conf`（已在 `sites-enabled/` 生效）
- **后端端口**：规划使用 `127.0.0.1:8010`
- **部署前缀**：`/cards`
- **代码获取**：公开仓库，可直接 `git clone`

---

## 1. 部署架构（最终形态）

- Nginx 继续提供你的个人首页与现有路径
- 仅新增两条规则：
  - `location = /cards { 301 -> /cards/ }`
  - `location ^~ /cards/ { proxy_pass http://127.0.0.1:8010; ... }`
- 后端服务由 systemd 常驻：
  - `uvicorn app.main:app --host 127.0.0.1 --port 8010 --workers 1`
  - 环境变量：`APP_PREFIX=/cards`

---

## 2. 上线前必须理解的限制（1C1G / 单实例）

- **必须 `--workers 1`**：牌局状态在进程内存里，多 worker 会导致状态分裂、WebSocket/REST 命中不同 worker 出错。
- **重启会丢局**：MVP 可接受（你已确认接受）。
- **短暂卡顿可能发生**：主要来自牌力计算的 CPU 突刺（你已确认接受）。

### 2.1 实际体验反馈（1C1G vs 2C2G）

**1C1G 服务器实际表现：**
- ✅ 可以运行和游玩
- ⚠️ **CPU 明显超负荷**：后台需要进行快速计算（牌力计算、AI 建议等），单核 CPU 难以满足实时计算需求
- ⚠️ 可能出现明显卡顿，影响游戏体验

**推荐配置：**
- **2C2G**：如果要真正爽玩，建议升级到 2C2G
  - 双核 CPU 可以更好地处理并发计算
  - 2G 内存提供更多缓冲空间
  - 成本增加有限，但体验提升明显

> **注意**：即使升级到 2C2G，仍然需要保持 `--workers 1`（因为牌局状态在内存中，多 worker 会导致状态分裂）。

---

## 3. 重要说明：关于“用户在前端输入自己的 LLM Key”

你希望不在服务器设置 `OPENAI_API_KEY` 等环境变量，而让用户在前端输入自己的 key。

这里有一个现实约束：

- 如果让浏览器**直接**调用 OpenAI/网关接口：
  - **Key 会暴露给浏览器**（可被用户自己看到/复制；也可能被 XSS/浏览器插件窃取）
  - 还会遇到 **CORS**、不同 provider 的 URL/模型兼容等问题
- 如果让浏览器把 key 传给后端，由后端代为调用：
  - Key 不会写死在服务器，但后端仍然会“看见”用户 key（需要额外代码支持：接收 key、缓存、按连接隔离、限流、审计）

本项目目前的实现是：**后端通过环境变量配置 provider/key**；前端只控制“是否启用 LLM 调用”开关。

因此本手册默认是：先确保服务稳定跑通（可以先不启用 LLM），然后再开启 LLM。

如果你希望**直接启用 LLM**（你当前选择的方案）：

- Docker 部署：见第 15.2.1（编辑 `.env`，设置 `AI_PROVIDER=openai` + `OPENAI_API_KEY`）
- 传统部署：在 systemd service 里加 `Environment=AI_PROVIDER=openai` / `Environment=OPENAI_API_KEY=...`

> 如果你确实要做“用户输入 key 并生效”，需要一个小功能迭代（我可以在后续给你一份设计/实现计划）。

---

## 4. 第一步：服务器准备（一次性）

### 4.1 更新系统并安装依赖（推荐包含构建工具，避免部分包需要编译时失败）

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nginx build-essential python3-dev
```

### 4.2（可选）确认域名解析是否生效

在你本机或任意能联网的机器上执行：

```bash
dig +short explain1thing.top A
```

**情况 1：如果返回 `198.23.164.200`**
- 说明域名直接解析到你的服务器，部署流程正常进行。

**情况 2：如果返回 Cloudflare IP（如 `104.21.x.x` 或 `172.67.x.x`）**
- 说明域名通过 Cloudflare 代理/CDN，这是**正常且推荐**的配置。
- Cloudflare 会自动转发请求到你的源服务器 `198.23.164.200`。
- **不影响部署**：Nginx 配置和后端服务都不需要调整。
- **WebSocket 支持**：Cloudflare 完全支持 WebSocket 代理，`/cards/ws/...` 路径可以正常工作。
- 你可以直接跳过此验证步骤，继续后续部署。

> 提示：如果你想确认源服务器 IP，可以在 Cloudflare 控制台查看 DNS 记录的 A 记录目标，或在服务器上直接访问 `http://198.23.164.200`（如果 Nginx 允许直接 IP 访问）。

---

## 5. 第二步：创建专用用户与目录（推荐）

创建一个最小权限用户（不允许登录 shell 可选，这里先保留 shell 方便排错）：

```bash
sudo adduser --disabled-password --gecos "" poker
```

创建部署目录并授权：

```bash
sudo mkdir -p /opt/poker-coach-alpha
sudo chown -R poker:poker /opt/poker-coach-alpha
```

之后我们都用该用户运行服务。

---

## 6. 第三步：拉代码并安装依赖（在服务器上执行）

### 6.1 切换到部署用户

```bash
sudo -iu poker
```

### 6.2 git clone（在已有目录内克隆，避免 /opt 权限与目录已存在问题）

```bash
cd /opt/poker-coach-alpha
git clone https://github.com/Wangmengguo/poker-coach-alpha.git .
```

### 6.3 创建 venv 并安装 requirements

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### 6.4（推荐）确保运行期目录存在

```bash
mkdir -p /opt/poker-coach-alpha/logs
```

> 说明：如果看到 `File exists` 错误，说明目录已存在，这是正常的，可以继续下一步。

> 说明：你服务器 1G 内存，安装依赖时如果遇到内存紧张/卡死，可考虑临时开 swap（见文末排错）。

退出 poker 用户（回到 root）：

```bash
exit
```

---

## 7. 第四步：创建 systemd 服务（后端）

我们让后端监听 `127.0.0.1:8010`（仅本机可访问），由 Nginx 反代出公网。

### 7.0 手把手创建服务文件

**步骤 1：退出 poker 用户，回到 root（如果当前在 poker 用户下）**

```bash
exit
```

你现在应该在 root 用户下（提示符显示 `root@...`）。

**步骤 2：创建服务文件（推荐方法：使用 cat 命令，避免格式问题）**

**方法 A：使用 cat 命令（推荐，避免粘贴格式丢失）**

直接执行以下命令，一次性创建正确格式的文件：

```bash
sudo tee /etc/systemd/system/poker-coach.service > /dev/null << 'EOF'
[Unit]
Description=Poker Coach Alpha (FastAPI/Uvicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=poker
Group=poker
WorkingDirectory=/opt/poker-coach-alpha

# 关键：部署前缀（与 /cards 反代一致）
Environment=APP_PREFIX=/cards

# 关键：单实例内存状态，必须 1 worker
ExecStart=/opt/poker-coach-alpha/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --workers 1

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

**方法 B：使用 nano 编辑器（如果方法 A 不工作）**

如果上面的命令不工作，使用 nano：

```bash
sudo nano /etc/systemd/system/poker-coach.service
```

在 nano 中：
1. **先删除所有现有内容**（如果文件已存在）：按 `Ctrl + K` 多次删除所有行
2. **然后一行一行地输入**以下内容（**不要一次性粘贴，避免格式丢失**）：

```ini
[Unit]
Description=Poker Coach Alpha (FastAPI/Uvicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=poker
Group=poker
WorkingDirectory=/opt/poker-coach-alpha

# 关键：部署前缀（与 /cards 反代一致）
Environment=APP_PREFIX=/cards

# 关键：单实例内存状态，必须 1 worker
ExecStart=/opt/poker-coach-alpha/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --workers 1

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

3. **保存并退出**：
   - 按 `Ctrl + O`（保存）
   - 按 `Enter`（确认文件名）
   - 按 `Ctrl + X`（退出编辑器）

**步骤 5：验证文件内容（可选但推荐）**

确认文件创建成功：

```bash
cat /etc/systemd/system/poker-coach.service
```

应该能看到刚才粘贴的内容。

**步骤 6：启用并启动服务**

依次执行以下命令：

```bash
# 重新加载 systemd 配置（让 systemd 识别新服务）
sudo systemctl daemon-reload

# 启用服务（开机自启）并立即启动
sudo systemctl enable --now poker-coach

# 查看服务状态（确认是否运行成功）
sudo systemctl status poker-coach --no-pager
```

**步骤 7：检查启动结果**

执行 `status` 命令后，你应该看到：

- ✅ **成功情况**：显示 `Active: active (running)` 和绿色的状态
- ❌ **失败情况**：显示 `Active: failed` 或 `Active: activating`，需要查看错误日志

如果失败，查看详细日志：

```bash
sudo journalctl -u poker-coach -n 50 --no-pager
```

这会显示最近 50 行日志，帮助你定位问题。

### 7.1 验证后端是否监听成功

```bash
sudo ss -ltnp | grep 8010 || true
```

应看到类似 `127.0.0.1:8010` 的监听。

### 7.2 本机 curl 验证（不经过 Nginx）

```bash
curl -I http://127.0.0.1:8010/cards/ | head
```

应返回 `200`（或至少不是 `404/502`）。

查看服务日志：

```bash
sudo journalctl -u poker-coach -n 200 --no-pager
```

---

## 8. 第五步：修改 Nginx 配置（只新增 /cards，不动首页）

你当前生效的配置文件是：

- `/etc/nginx/sites-enabled/explain1thing_ssl.conf`

它通常是从：

- `/etc/nginx/sites-available/explain1thing_ssl.conf`

软链过来的。你可以用下面命令确认：

```bash
ls -l /etc/nginx/sites-enabled/ | grep explain1thing
```

### 8.1 在 `server { listen 443 ... }` 内添加 /cards 规则

编辑文件：

```bash
sudo nano /etc/nginx/sites-available/explain1thing_ssl.conf
```

在该 `server` block 里（建议放在 `location / { ... }` 之前，便于阅读）加入：

```nginx
# Poker Coach Alpha（完全隔离在 /cards/ 下）
location = /cards {
  return 301 /cards/;
}

location ^~ /cards/ {
  proxy_pass http://127.0.0.1:8010;
  proxy_http_version 1.1;

  proxy_set_header Host              $host;
  proxy_set_header X-Real-IP         $remote_addr;
  proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;

  # WebSocket
  proxy_set_header Upgrade           $http_upgrade;
  proxy_set_header Connection        $connection_upgrade;

  proxy_read_timeout 3600s;
  proxy_send_timeout 3600s;
}
```

> 为什么需要 `location = /cards`？
> - 访问 `/cards`（无斜杠）时，如果不做跳转，会落入你已有的 `location /` 静态站点规则，最终 **404**。
> - 跳转到 `/cards/` 后，浏览器相对路径解析也更稳定。

### 8.2 检查并 reload Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 9. 第六步：线上验证（浏览器与命令行）

### 9.1 验证你的个人首页仍然可用

打开：

- `https://explain1thing.top/`

应保持不变。

### 9.2 验证 Poker 项目可用

打开：

- `https://explain1thing.top/cards/`

应能加载页面（CSS/JS 正常）。

### 9.3 命令行快速检查 HTTP 状态码

```bash
curl -I https://explain1thing.top/cards/ | head
curl -I https://explain1thing.top/cards/public/style.css | head
```

### 9.4 WebSocket 如何验证？

最简单方式：打开浏览器控制台 Network → WS，看到 `.../cards/ws/tables/default?...` 成功升级（101）。

命令行方式（可选安装 `websocat`）：

```bash
sudo apt install -y websocat
websocat -v wss://explain1thing.top/cards/ws/tables/default?player_id=human
```

连上后应收到 `snapshot` JSON（如果已有 session/状态）。

---

## 10. WebSocket upgrade 变量：你要怎么确认它真的“正确存在并生效”？

你提供的 `nginx -T` 输出里已经包含：

- 在 `http {}` 作用域内的 `map $http_upgrade $connection_upgrade ...`

因此 **变量是存在的**，并且你的 `/golden-eyes` 反代也在用它，说明生产环境已经依赖这条 map 规则。

### 10.1 最直接的确认方法（推荐）

运行：

```bash
sudo nginx -T | sed -n '1,220p' | grep -n "map \\$http_upgrade \\$connection_upgrade" -n || true
sudo nginx -T | grep -n "connection_upgrade" | head -n 20
```

如果 `nginx -T` 显示语法 OK 并能找到 map，说明它已被 Nginx 解析且变量可用。

### 10.2 这条 map 写法是否“标准”？

你当前是：

```nginx
map $http_upgrade $connection_upgrade { default close; websocket upgrade; }
```

它的含义是：

- 当浏览器发 `Upgrade: websocket` 时，`$connection_upgrade` 取值为 `upgrade`
- 否则取值 `close`

这对于 WebSocket 升级是可用的（你已有应用在用）。

更常见/更通用的写法是：

```nginx
map $http_upgrade $connection_upgrade {
  default upgrade;
  ''      close;
}
```

但你现在的写法并不阻止 WebSocket 正常工作；本次 `/cards` 反代可以沿用你的现有 map。

---

## 11. 回滚方案（如果你希望“一键恢复”）

### 11.1 回滚 Nginx（移除 /cards 规则）

把你新增的两个 `location` 删除或注释，然后：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 11.2 停止后端服务

```bash
sudo systemctl stop poker-coach
sudo systemctl disable poker-coach
```

---

## 12. 常见问题排查（高频）

### 12.1 访问 `/cards/` 出现 502

- 看后端是否在跑：

```bash
sudo systemctl status poker-coach --no-pager
sudo journalctl -u poker-coach -n 200 --no-pager
sudo ss -ltnp | grep 8010 || true
```

- 看 Nginx 是否正确 reload：

```bash
sudo nginx -t
sudo tail -n 200 /var/log/nginx/error.log
```

### 12.2 页面能打开但按钮不工作/WS 断开

- 浏览器 DevTools → Console / Network → WS 看是否连到了：
  - `wss://explain1thing.top/cards/ws/tables/default?...`
- Nginx 里 `/cards/` location 是否包含：
  - `proxy_set_header Upgrade $http_upgrade;`
  - `proxy_set_header Connection $connection_upgrade;`

### 12.3 安装依赖时内存不足（1G）

可以临时开 2G swap（可选）：

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
free -h
```

安装完后也可以保留 swap 以提高稳定性（权衡：swap 会慢，但能避免 OOM）。

### 12.4 游戏卡顿、CPU 超负荷（1C1G 服务器）

**症状：**
- 游戏响应慢，操作有明显延迟
- 服务器 CPU 使用率持续 100%
- 牌力计算、AI 建议生成时卡顿明显

**原因：**
- 1C1G 配置对于实时计算（牌力计算、AI 分析）来说资源不足
- 单核 CPU 难以同时处理 WebSocket 通信和后台计算任务

**解决方案：**
1. **推荐：升级到 2C2G**
   - 双核 CPU 可以更好地处理并发计算
   - 2G 内存提供更多缓冲空间
   - 体验提升明显

2. **临时优化（效果有限）：**
   - 减少 AI 建议的复杂度（如果可配置）
   - 降低并发玩家数量
   - 但 1C1G 的硬件限制无法完全通过软件优化解决

> **实际体验反馈**：1C1G 可以运行和游玩，但 CPU 明显超负荷。如果要真正爽玩，建议升级到 2C2G。

---

## 13. 你现在要做的唯一替换项

本手册已替你填好仓库地址，无需再替换。

---

## 14. 后续如何更新版本（上线后常用）

当你在本地/CI 更新代码推到 GitHub 后，在服务器上执行：

```bash
sudo -iu poker
cd /opt/poker-coach-alpha
PREV_COMMIT="$(git rev-parse --short HEAD)"
echo "Previous commit: $PREV_COMMIT"
git pull
. .venv/bin/activate
pip install -r requirements.txt
exit
sudo systemctl restart poker-coach
sudo systemctl status poker-coach --no-pager
```

如果你只改了前端静态文件（`public/`），通常只需要 `git pull` + `systemctl restart poker-coach`。

### 14.1（推荐）更新失败时如何快速回滚

如果你在更新后发现：
- `/cards/` 打不开 / 报 502
- 前端能打开但功能异常
- `journalctl -u poker-coach` 出现明显报错

可以用下面方式回滚到更新前版本（使用你在上一步打印的 `PREV_COMMIT`）：

```bash
sudo -iu poker
cd /opt/poker-coach-alpha
git reset --hard "$PREV_COMMIT"
exit
sudo systemctl restart poker-coach
sudo systemctl status poker-coach --no-pager
```

> 说明：
> - 这是最快的“回到上一个已知可用版本”的方法。
> - 如果你更新过程中改动了依赖（requirements），回滚后一般不需要重新 pip；若仍报依赖相关错误，再运行一次 `pip install -r requirements.txt` 即可。

---

## 15. Docker 部署方式（替代方案）

如果你更喜欢使用 Docker 部署，可以按照以下步骤：

### 15.1 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose（如果未包含）
sudo apt install -y docker-compose-plugin

# Debian 12 安装的是 Compose plugin，命令是：docker compose ...
# 如果你机器上是旧版 docker-compose 二进制，把下文的 "docker compose" 换成 "docker-compose" 即可。
```

### 15.2 拉取代码并配置

```bash
# 创建部署目录
sudo mkdir -p /opt/poker-coach-alpha
sudo chown -R $USER:$USER /opt/poker-coach-alpha
cd /opt/poker-coach-alpha

# 克隆代码
git clone https://github.com/Wangmengguo/poker-coach-alpha.git .

# 复制环境变量模板
cp .env.example .env

# 编辑 .env（可选：如果要用 LLM 功能）
nano .env
```

### 15.2.1 直接启用 LLM（OpenAI 兼容网关 / OpenAI）

在服务器上编辑 `/opt/poker-coach-alpha/.env`，至少配置这些变量：

```bash
# 启用 LLM
AI_PROVIDER=openai

# 必填：你的 Key（不要提交到 git）
OPENAI_API_KEY=YOUR_REAL_KEY

# 可选：OpenAI 兼容网关（例如 oneapi / openrouter / 自建网关）
# 如果你直连 OpenAI 官方，一般可以留空
OPENAI_API_BASE=

# 可选：默认模型别名（前端也可以切换）
AI_MODEL_ALIAS=gpt-5.1-chat-latest

# 可选：开启调试日志（上线初期建议开 1，确认 LLM 真在被调用；稳定后可改回 0）
AI_COACH_DEBUG=1
```

建议把 `.env` 权限收紧，避免其他系统用户读取：

```bash
cd /opt/poker-coach-alpha
chmod 600 .env
```

### 15.2.2 生产环境 Token 滥用防护（必做）

上线前请确认 `.env` 至少满足：

```bash
# 必填：Admin 页面与受保护 API 使用（随机 32+ 字符）
ADMIN_TOKEN=YOUR_RANDOM_ADMIN_TOKEN

# 必须为 0（生产环境禁止绕过）
LOCAL_ADMIN_BYPASS=0
LOCAL_INVITE_BYPASS=0

# Nginx 反代 + POKER_BIND_ADDR=127.0.0.1 时可保持默认
FORWARDED_ALLOW_IPS=*
```

说明：

- Docker 镜像已启用 `uvicorn --proxy-headers`，配合 Nginx 的 `X-Real-IP` / `X-Forwarded-For`，按 IP 的 LLM 限流才会生效。
- Admin 配置页：`https://explain1thing.top/cards/admin/llm`，在页面内输入 `ADMIN_TOKEN`（存于 `sessionStorage`，仅通过 `x-admin-token` Header 发送）。**不要把 token 写在 URL 里**（会进 access log）。
- `POST /settings/ai_model` 已改为 Admin 专用；普通用户通过前端模型下拉切换（WebSocket），不会改全局默认档。
- 创建邀请码时建议加配额：`--max-uses` + `--daily-quota`。

### 15.3 启动 Docker 服务

```bash
# 构建并启动（后台运行）
docker compose up -d --build

# 查看日志
docker compose logs -f poker
```

> 安全提示：`docker-compose.yml` 默认把后端端口仅绑定到 `127.0.0.1:8010`，让公网只能通过 Nginx 访问 `/cards/`。
> 如果你确实需要直接对外暴露 8010 端口（不推荐），可在 `.env` 里设置：`POKER_BIND_ADDR=0.0.0.0`。

### 15.3.1 验证 LLM 已经被后端识别（不等于“用户可用”）

后端是否识别到 LLM provider/key，可以在服务器本机跑：

```bash
curl -s http://127.0.0.1:8010/cards/settings/ai_model
```

你应该看到 `"llm_available": true`。

注意：**即使 `llm_available=true`，没有邀请码也依然不会调用 LLM**（见第 16 节）。

### 15.4 配置 Nginx

Docker 部署使用相同的 Nginx 配置（见第 8 步），后端服务运行在 `127.0.0.1:8010`。

### 15.5 Docker 管理命令

```bash
# 查看日志
docker compose logs -f poker

# 重启服务
docker compose restart poker

# 停止服务
docker compose down

# 更新代码后重启
git pull
docker compose up -d --build
```

---

## 16. 邀请码管理

本项目使用邀请码系统来控制 LLM AI Coach 功能的访问。部署后，你需要创建邀请码并分发给用户。

### 16.1 创建邀请码

**使用 Docker 部署：**
```bash
docker compose exec poker python -m tools.manage_invites create --note "For friend A"
```

**使用传统部署（systemd）：**
```bash
sudo -iu poker
cd /opt/poker-coach-alpha
source .venv/bin/activate
python -m tools.manage_invites create --note "For friend A"
exit
```

### 16.2 查看邀请码列表

**使用 Docker：**
```bash
docker compose exec poker python -m tools.manage_invites list
```

**使用传统部署：**
```bash
sudo -iu poker
cd /opt/poker-coach-alpha
source .venv/bin/activate
python -m tools.manage_invites list
exit
```

### 16.3 撤销邀请码

```bash
# Docker
docker compose exec poker python -m tools.manage_invites revoke POKER-ABC123

# 传统部署
sudo -iu poker
cd /opt/poker-coach-alpha
source .venv/bin/activate
python -m tools.manage_invites revoke POKER-ABC123
exit
```

### 16.4 检查邀请码有效性

```bash
# Docker
docker compose exec poker python -m tools.manage_invites check POKER-ABC123

# 传统部署
sudo -iu poker
cd /opt/poker-coach-alpha
source .venv/bin/activate
python -m tools.manage_invites check POKER-ABC123
exit
```

### 16.5 邀请码数据库位置

- **Docker 部署**：`./data/invites.db`（挂载在容器外）
- **传统部署**：`/opt/poker-coach-alpha/data/invites.db`（或 `DATA_DIR` 环境变量指定的路径）

### 16.6 用户如何使用邀请码

1. 用户访问 `https://explain1thing.top/cards/`
2. 在页面上的"Invite Code"输入框中输入邀请码
3. 启用"LLM"开关
4. 点击"Ask once"获取 AI 建议

没有有效邀请码时，AI Coach 将使用启发式模式（不调用 LLM）。

### 16.7（推荐）上线后做一次“LLM + 邀请码”端到端验证

1) 在服务器上创建邀请码：

```bash
docker compose exec poker python -m tools.manage_invites create --note "self-check"
```

2) 浏览器打开 `https://explain1thing.top/cards/`：

- 输入邀请码
- 打开 LLM 开关
- 点击 `Ask once`

3) 同时在服务器上观察日志（确认确实发起了外部调用/没有报错）：

```bash
docker compose logs -f poker
```

如果看到 `invite_code_required` / `dummy_provider` 之类原因，说明仍在走非 LLM 路径：

- `invite_code_required`：邀请码不对/未输入/已撤销
- `dummy_provider`：`AI_PROVIDER` 仍是 dummy 或 key/base 配置不生效
