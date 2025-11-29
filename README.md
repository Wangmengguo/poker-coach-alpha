# Poker Coach Alpha

Simple, understandable scaffold for a Texas Hold’em MVP using FastAPI + WebSocket and pokerkit.

## Quickstart

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

### Enable LiteLLM via environment variables

By default the project uses a dummy provider (no external calls). To enable LiteLLM with an OpenAI-compatible gateway (for example a oneapi-style proxy), set:

```bash
export AI_PROVIDER=openai                # enable LiteLLM-backed provider
export OPENAI_API_KEY="your_gateway_key" # key for your OpenAI-compatible gateway
export OPENAI_API_BASE="https://oneapi.laisky.com/v1"  # or your own /v1 endpoint
export AI_MODEL_ALIAS="gpt-5.1-chat-latest"            # any allowed model alias
```

`AI_PROVIDER=openai` switches the backend to use `LitellmProvider`. The actual models are defined in `poker/ai_coach.py` via `ALLOWED_MODELS` (keys are the human-visible names, values are the model ids passed to LiteLLM). In the current setup these keys are real model names such as:

- `claude-4.5-sonnet`
- `claude-opus-4-5`
- `moonshotai/kimi-k2-instruct`
- `kimi-k2-thinking`
- `gemini-3-pro-preview`
- `gpt-5.1-chat-latest`
- `deepseek-chat`
- `deepseek-reasoner`

The backend will pass the chosen model name to your gateway; the gateway is responsible for routing to the underlying provider (Anthropic/DeepSeek/Kimi/Gemini/etc.).

If `AI_PROVIDER` is unset or misconfigured, or the LLM call fails, the coach will stay in heuristic-only mode and continue to work without external dependencies.

### Switching models at runtime

To inspect and change the current model without restarting the server, use the REST settings endpoint:

- Get current model and allowed list:

```bash
curl http://localhost:8000/settings/ai_model
```

- Change model (must be one of the allowed names from `ALLOWED_MODELS`):

```bash
curl -X POST http://localhost:8000/settings/ai_model \
  -H "Content-Type: application/json" \
  -d '{"model_alias": "deepseek-chat"}'
```

The frontend can call the same endpoint to implement a simple model selector (e.g. a dropdown showing `claude-4.5-sonnet`, `deepseek-chat`, etc.). Only the model name travels over the wire; keys and provider-specific configuration stay on the backend.

## Next

We will implement the TableService around pokerkit, bots, and the WS protocol per PLAN.md.
