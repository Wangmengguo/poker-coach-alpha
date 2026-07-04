# Poker Coach Alpha

Simple, understandable scaffold for a Texas Hold’em MVP using FastAPI + WebSocket and pokerkit.

## Quickstart

### Option 1: Docker (Recommended for Production)

```bash
# 1. Copy environment variables template
cp .env.example .env
# For heuristic-only mode (no external calls): keep `AI_PROVIDER=dummy` and `OPENAI_API_KEY=`
# To enable LLM: set `AI_PROVIDER=openai` and fill `OPENAI_API_KEY`

# 2. Start with Docker Compose
docker compose up -d --build

# 3. Access the app
# Open http://localhost:8010/cards/
```

Note: `docker-compose.yml` binds the backend to `127.0.0.1:8010` by default (recommended). To expose it publicly, set `POKER_BIND_ADDR=0.0.0.0`.

See [Docker Deployment](#docker-deployment) for more details.

### Option 2: Local Development

- Python 3.10+

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 to load the minimal client.

## Layout

- app/ — FastAPI app (REST + WebSocket)
- poker/ — pokerkit wrapper and bots
- ws/ — protocol schemas (messages, validation)
- public/ — static client (index.html, app.js, style.css)
- tests/ — basic tests
- PLAN.md — roadmap and technical plan

## AI Coach (LLM) configuration

The AI coach has three modes:
- Heuristic-only (no LLM): default when no provider/key is configured; actions and explanations are based on deterministic rules.
- LLM explanation + heuristic actions: when a provider is available, the LLM only generates natural-language explanations; action selection remains heuristic and safe.
- Fallback: on LLM errors, the coach automatically falls back to heuristic-only mode.

### Enable AI Coach via an OpenAI-compatible gateway

By default the project uses a dummy provider (no external calls). To enable the AI coach with an OpenAI-compatible gateway (for example a oneapi-style proxy), set:

```bash
export AI_PROVIDER=openai                # or 'gateway'; enables OpenAICompatibleProvider
export OPENAI_API_KEY="your_gateway_key" # key for your OpenAI-compatible gateway
export OPENAI_API_BASE="https://oneapi.laisky.com/v1"  # or set OPENAI_API_URL to your /v1 endpoint
export AI_MODEL_ALIAS="gpt-5.1-chat-latest"            # any allowed model alias
export AI_COACH_DEBUG=1                  # optional; prints LLM debug info (token truncation, fallback path)
```

`AI_PROVIDER=openai` (or `gateway`) switches the backend to use `OpenAICompatibleProvider`, which talks directly to your OpenAI-compatible `/chat/completions` endpoint. The actual models are defined in `poker/ai_coach.py` via `ALLOWED_MODELS` (keys are the human-visible names, values are the model ids passed to the gateway). In the current setup these keys are real model names such as:

- `claude-4.5-sonnet`
- `claude-opus-4-5`
- `gemini-3-flash-preview`
- `moonshotai/kimi-k2-instruct`
- `gpt-5.1-chat-latest`
- `gpt-5.2`
- `gpt-5.2-pro`
- `deepseek-chat`
- `grok-4-fast-reasoning`

The backend will pass the chosen model name to your gateway; the gateway is responsible for routing to the underlying provider (Anthropic/DeepSeek/Kimi/Gemini/etc.).

If `AI_PROVIDER` is unset or misconfigured, or the LLM call fails, the coach will stay in heuristic-only mode and continue to work without external dependencies.

### Switching models at runtime

To inspect the current model tier list:

```bash
curl http://localhost:8000/settings/ai_model
```

Changing the **global default** model requires admin access (header only; do not pass token in URL):

```bash
curl -X POST http://localhost:8000/settings/ai_model \
  -H "Content-Type: application/json" \
  -H "x-admin-token: YOUR_ADMIN_TOKEN" \
  -d '{"model_alias": "fast"}'
```

End users switch models per browser via the frontend model selector (WebSocket `client_settings`); that path does not require admin access.

### LLM Admin page

Open `/cards/admin/llm` (or `/admin/llm` in local dev). Enter `ADMIN_TOKEN` in the page unlock form; the token is stored in `sessionStorage` and sent only via the `x-admin-token` header.

## Invite Code System

The AI Coach LLM features are protected by an invite code system. Users must enter a valid invite code in the frontend to access LLM-powered advice.

### Managing Invite Codes

**Using Docker Compose:**
```bash
# Create a new invite code
docker compose exec poker python -m tools.manage_invites create --note "For friend A"

# Create a limited invite code
docker compose exec poker python -m tools.manage_invites create \
  --note "For friend A" \
  --expires-at "2026-05-01T00:00:00+00:00" \
  --max-uses 100 \
  --daily-quota 20 \
  --models fast,balanced

# List all invite codes
docker compose exec poker python -m tools.manage_invites list

# Revoke an invite code
docker compose exec poker python -m tools.manage_invites revoke POKER-ABCD1234

# Check if a code is valid
docker compose exec poker python -m tools.manage_invites check POKER-ABCD1234
```

**Using Local Python:**
```bash
# Activate your virtual environment first
source .venv/bin/activate

# Create a new invite code
python -m tools.manage_invites create --note "For friend A"

# Create a limited invite code
python -m tools.manage_invites create \
  --note "For friend A" \
  --expires-at "2026-05-01T00:00:00+00:00" \
  --max-uses 100 \
  --daily-quota 20 \
  --models fast,balanced

# List all invite codes
python -m tools.manage_invites list

# Revoke an invite code
python -m tools.manage_invites revoke POKER-ABCD1234

# Check if a code is valid
python -m tools.manage_invites check POKER-ABCD1234
```

Invite codes are stored in a SQLite database (`data/invites.db` by default). The database is automatically created on first use. Codes can optionally enforce an expiry time, total LLM call limit, daily LLM call quota, and allowed model tiers. A code is bound to the first anonymous browser session that validates it.

### Using Invite Codes

1. Start a game session
2. Enter your invite code in the "Invite Code" input field in the frontend
3. Enable the "LLM" toggle
4. Click "Ask once" to get AI-powered advice

Without a valid invite code, the AI Coach will use heuristic-only mode (no LLM calls).

## Docker Deployment

### Prerequisites

- Docker and Docker Compose installed
- (Optional) API keys for LLM features in `.env` file

### Quick Start

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env`** and configure:
   - Heuristic-only: `AI_PROVIDER=dummy` and `OPENAI_API_KEY=`
   - Enable LLM: `AI_PROVIDER=openai` and `OPENAI_API_KEY=your-key`
   - `OPENAI_API_BASE=https://your-gateway.com/v1` (optional)
   - `AI_MODEL_ALIAS=gpt-5.1-chat-latest` (optional)

3. **Start the service:**
   ```bash
   docker compose up -d --build
   ```

4. **Access the app:**
   - Web UI: http://localhost:8010/cards/
   - Health check: http://localhost:8010/cards/

### Managing the Service

```bash
# View logs
docker compose logs -f poker

# Stop the service
docker compose down

# Restart the service
docker compose restart poker

# Update and rebuild
git pull
docker compose up -d --build
```

### Data Persistence

- Invite codes database: `./data/invites.db` (mounted as volume)
- Logs: Inside container (use `docker compose logs` to view)

### Production Considerations

- The Dockerfile uses `--workers 1` because game state is stored in memory
- Resource limits are set in `docker-compose.yml` (adjust based on your server)
- **Token abuse protection (production checklist):**
  - Set a strong `ADMIN_TOKEN` (32+ random characters)
  - Keep `LOCAL_ADMIN_BYPASS=0` and `LOCAL_INVITE_BYPASS=0`
  - Use Nginx in front; keep `POKER_BIND_ADDR=127.0.0.1` so `FORWARDED_ALLOW_IPS=*` is safe
  - If exposing port 8010 publicly, set `FORWARDED_ALLOW_IPS` to your proxy IP only
  - Open `/cards/admin/llm` and enter the admin token in the page (never in URL query strings)
  - Create invite codes with `--max-uses` and `--daily-quota` limits
- For production, also consider:
  - Using a reverse proxy (Nginx) for SSL/TLS
  - Setting up proper backup for `./data` directory
  - Configuring log rotation (already configured in docker-compose.yml)

See `docs/DEPLOY_EXPLAIN1THING_TOP_CARDS.md` for a detailed production deployment guide with Nginx.

## Offline LLM vs bot simulation (testing)

When `AI_PROVIDER` is configured to use an OpenAI-compatible gateway and a valid model alias (see above), you can benchmark the coach by running offline simulations with `tools/run_llm_simulation.py`. For example, to run 10 independent 100-hand sessions with different seeds and write per-hand CSVs into `logs/`:

```bash
for s in 1 2 3 4 5 6 7 8 9 10; do
  echo "=== Session $s ==="
  python tools/run_llm_simulation.py \
    --model-alias gpt-5.1-chat-latest \
    --num-hands 100 \
    --seed $s \
    --llm-timeout-seconds 30 \
    --csv-output logs
done
```

Each run plays `--num-hands` hands with one LLM-controlled seat (via `LlmBot`) against existing bots, prints aggregate stats (hands, net chips, BB/100, LLM failures), and writes a CSV file under `logs/` that you can analyze later.

## Next

Infrastructure is in place. Current focus is deepening the AI coaching strategy:

- Enhance hand-strength and decision-math metrics per `COACH_IMPLEMENTATION_PLAN.md`
- Integrate GTO-informed heuristics and bot algorithms (see research docs in repo root)
- Extend real-time coach UI (drawer, pot odds, SPR, board texture)
