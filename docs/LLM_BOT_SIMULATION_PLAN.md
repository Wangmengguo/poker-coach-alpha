# LLM Bot Simulation Plan

## Goal

Allow a single configured LLM model to fully control one seat in the table, play a large number of hands (e.g. 100+), and measure its performance vs existing bots (EquityBot) in a repeatable, offline simulation.

## High-Level Approach

- Add a dedicated `LlmBot` wrapper that uses the existing analysis pipeline (`compose_analysis`, `DecisionContext`, `generate_ai_advice`) to choose actions for one seat.
- Create an offline simulation script that:
  - Initializes a `TableEngine` with 1 LLM seat + N bot seats.
  - Plays a fixed number of hands with deterministic randomness.
  - Records per-hand and aggregate results (e.g. net chips, BB/100, LLM failure rate).
- Keep everything server-side (no WebSocket / frontend) to reduce complexity and cost.

## Components

### 1. LlmBot wrapper

New module: `poker/llm_bot.py`

- Responsibilities:
  - Given `engine.state`, `hero_idx`, `hero_seat`, and `legal_actions`, build the same `DecisionContext` and `analysis` payload used by the coach.
  - Call a **LLM-only** path (no heuristic fallback for recommended_action) so we can truly measure the model.
  - Handle malformed / unusable LLM outputs with a simple, explicit fallback (e.g. fold or check) and log the failure.

- Suggested API:

  ```python
  class LlmBot:
      def __init__(self, provider: AiProvider, *, model_alias: str) -> None: ...

      async def choose_action(
          self,
          engine: TableEngine,
          hero_idx: int,
          hero_seat: int,
      ) -> Dict[str, Any]:
          """Return a single legal action dict for this decision."""
  ```

- Implementation notes:
  - Reuse `compose_analysis(...)` to build `DecisionContext`.
  - Reuse `build_prompt(...)` + `_parse_llm_json(...)` from `poker.ai_coach`, but:
    - If `_parse_llm_json` returns a usable `AiAdvice` with `recommended_action`, use it directly.
    - If parsing fails or the action is invalid, treat this **decision** as an LLM failure and fall back to a safe policy:
      - Prefer `check` when `to_call == 0` 且合法；
      - 否则如果有 `fold`，直接 `fold`；
      - 否则选择 `call`，再不行就选第一个合法动作。
    - 不会直接中止整手牌或整场实验，只是这一决策由 fallback 接管，并将失败计入统计。

### 2. Pure LLM advice helper

To keep `generate_ai_advice` untouched for the coach UI, add a small helper in `poker/ai_coach.py`:

```python
async def generate_llm_actions_only(
    dc: DecisionContext,
    legal_actions: List[Dict[str, Any]],
    provider: AiProvider,
    action_history: Optional[List[Dict[str, Any]]] = None,
) -> AiAdvice:
    """
    Like generate_ai_advice but:
    - Always tries to use LLM-recommended actions.
    - On failure, returns AiAdvice with recommended_action=None and a reason
      like 'llm_error' or 'llm_parse_failed' (no heuristic override).
    """
```

The `LlmBot` will use this function so we can distinguish:

- LLM succeeded: `reason == "llm_actions"` and `recommended_action` is not None.
- LLM failed: `recommended_action is None`, `reason` describes the failure.

Additionally, `generate_llm_actions_only` should:

- Wrap the provider call with a per-decision timeout (e.g. using `asyncio.wait_for`), with a configurable `llm_timeout_seconds` defaulting to a small number (e.g. 3–5 seconds).
- On timeout or network / API errors, return an `AiAdvice` with `recommended_action=None` and a `reason` such as `"llm_timeout"` or `"llm_error"`, leaving the concrete fallback behavior to `LlmBot`.

### 3. Offline simulation script

New script: `tools/run_llm_simulation.py` (or `poker/experiments/run_llm_simulation.py`)

CLI usage (example):

```bash
python tools/run_llm_simulation.py \
  --model-alias gpt-5.1-chat-latest \
  --num-hands 100 \
  --seed 42
```

Responsibilities:

- Read env vars and model alias:
  - Use `set_current_model_alias(model_alias)` and `get_ai_provider_from_env()`.
  - If the provider is `DummyProvider`, exit with a clear message.
- Build a `TableEngine` configured for simulation:
  - Use existing `EngineConfig` with e.g. 6-max table, fixed blinds and stacks.
  - Choose one seat (e.g. seat 1) for LLM; other seats use existing `EquityBot`.
- Main loop:
  - For each hand in `range(num_hands)`:
    - Reset or start a new hand using existing `TableEngine` APIs.
    - While the hand is not finished:
      - Determine current seat to act and `legal_actions`.
      - If it is LLM seat:
        - Call `await llm_bot.choose_action(engine, hero_idx, hero_seat)`.
      - Else:
        - Call `EquityBot.choose(...)` as today.
      - Apply the chosen action to the engine.
    - At hand end, record LLM seat net chip change for this hand.
- Metrics:
  - Per-hand record: `hand_index`, `net_chips`, `llm_failures_this_hand`.
  - Aggregate:
    - Total hands played.
    - Total net chips, BB/100.
    - Total LLM failures (parse errors, API errors).
  - Optional: write CSV to `logs/llm_sim_{model_alias}_{timestamp}.csv`.

### 4. Experiment configuration

Initial defaults:

- Table:
  - 6-max, blinds 1/2, stacks 400 chips (~200bb) as in current `poker/table.py`.
- Seats:
  - Seat 1: human-equivalent seat, controlled by `LlmBot`.
  - Seats 2–6: existing `EquityBot` logic (reuse `EquityBot` directly, not `BotManager`'s asynchronous wrappers).
- Number of hands:
  - Start with `num_hands=100` for smoke tests.
  - For more meaningful stats, later run `num_hands=1000+`.
- Randomness:
  - Use a top-level `seed` to seed both the engine and any internal RNG in bots, so runs are reproducible.

### 5. Safety and cost controls

- Token cost:
  - Keep the prompt identical (or very close) to the current coach prompt.
  - Avoid extra natural-language commentary in simulation.
- Failure handling:
  - Treat repeated LLM failures as a signal; print a summary warning if failure rate is high.
  - A **failure** 指单次决策（一次 LLM 调用）因超时、网络错误或解析失败而无法给出可用动作，本次决策交由安全 fallback 完成。
- Rate limiting:
  - Allow a `--max-concurrent-calls` or a simple sequential mode; by default keep calls sequential to simplify.

## Next Steps

1. Implement `generate_llm_actions_only` in `poker/ai_coach.py`.
2. Implement `LlmBot` in `poker/llm_bot.py` using that helper.
3. Implement the first version of `tools/run_llm_simulation.py`:
   - Hard-code a simple 6-max setup.
   - Support `--model-alias`, `--num-hands`, and `--seed`.
4. Run small local experiments (e.g. 50–100 hands) for one model to validate:
   - No crashes.
   - Reasonable LLM success rate.
   - Metrics output looks sane.
5. Iterate on experiment design (more hands, different baselines, multiple models).
