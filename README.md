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

### Enable AI Coach via an OpenAI-compatible gateway

By default the project uses a dummy provider (no external calls). To enable the AI coach with an OpenAI-compatible gateway (for example a oneapi-style proxy), set:

```bash
export AI_PROVIDER=openai                # or 'gateway'; enables OpenAICompatibleProvider
export OPENAI_API_KEY="your_gateway_key" # key for your OpenAI-compatible gateway
export OPENAI_API_BASE="https://oneapi.laisky.com/v1"  # or your own /v1 endpoint
export AI_MODEL_ALIAS="gpt-5.1-chat-latest"            # any allowed model alias
```

`AI_PROVIDER=openai` (or `gateway`) switches the backend to use `OpenAICompatibleProvider`, which talks directly to your OpenAI-compatible `/chat/completions` endpoint. The actual models are defined in `poker/ai_coach.py` via `ALLOWED_MODELS` (keys are the human-visible names, values are the model ids passed to the gateway). In the current setup these keys are real model names such as:

- `claude-4.5-sonnet`
- `claude-opus-4-5`
- `moonshotai/kimi-k2-instruct`
- `gpt-5.1-chat-latest`
- `deepseek-chat`
- `grok-4-fast-reasoning`

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

We will implement the TableService around pokerkit, bots, and the WS protocol per PLAN.md.
