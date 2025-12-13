from __future__ import annotations

import argparse
import asyncio
import csv
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

# Ensure project root (containing the 'poker' package) is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from poker.engine import EngineConfig, TableEngine  # type: ignore  # noqa: E402
from poker.bots import EquityBot  # type: ignore  # noqa: E402
from poker.ai_coach import (  # type: ignore  # noqa: E402
    ALLOWED_MODELS,
    AiProvider,
    DummyProvider,
    get_ai_provider_from_env,
    set_current_model_alias,
)
from poker.llm_bot import LlmBot  # type: ignore  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline LLM vs bot poker simulations."
    )
    parser.add_argument(
        "--model-alias",
        type=str,
        required=True,
        help="Model alias from poker.ai_coach.ALLOWED_MODELS (e.g. gpt-5.1-chat-latest).",
    )
    parser.add_argument(
        "--num-hands",
        type=int,
        default=100,
        help="Number of hands to simulate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--llm-timeout-seconds",
        type=float,
        default=5.0,
        help="Per-decision timeout for LLM calls in seconds.",
    )
    parser.add_argument(
        "--csv-output",
        type=str,
        default="",
        help="Optional path to write per-hand CSV results.",
    )
    return parser.parse_args()


def _build_engine(seed: int) -> TableEngine:
    # Reuse existing 6-max config from EngineConfig defaults; we only
    # customize session_id so that BotManager seeding remains stable.
    session_id = f"llm_sim_{seed}"
    cfg = EngineConfig(session_id=session_id)
    engine = TableEngine(cfg)
    return engine


def _build_llm_bot(provider: AiProvider, model_alias: str, timeout: float) -> LlmBot:
    return LlmBot(provider, model_alias=model_alias, llm_timeout_seconds=timeout)


def _seat_to_state_index(engine: TableEngine, seat: int) -> int:
    idx = engine._seat_to_state_index(seat)  # type: ignore[attr-defined]
    if idx is None:
        raise RuntimeError(f"Seat {seat} has no corresponding state index")
    return idx


async def _run_simulation(
    model_alias: str,
    num_hands: int,
    seed: int,
    llm_timeout_seconds: float,
    csv_output: str,
) -> None:
    if model_alias not in ALLOWED_MODELS:
        raise SystemExit(
            f"model_alias '{model_alias}' not in ALLOWED_MODELS: {sorted(ALLOWED_MODELS.keys())}"
        )

    set_current_model_alias(model_alias)
    provider = get_ai_provider_from_env()
    if isinstance(provider, DummyProvider):
        raise SystemExit(
            "Using DummyProvider (no real gateway). "
            "Please configure AI_PROVIDER / OPENAI_API_KEY / OPENAI_API_BASE (or OPENAI_API_URL)."
        )

    rng = random.Random(seed)
    engine = _build_engine(seed)
    # Start a fresh session so that engine.state is initialized.
    session_id = f"llm_sim_{seed}"
    print(
        f"[SIM] Starting session '{session_id}' with model='{model_alias}', "
        f"num_hands={num_hands}, timeout={llm_timeout_seconds}s",
        flush=True,
    )
    engine.restart_session(new_session_id=session_id)

    llm_bot = _build_llm_bot(provider, model_alias, llm_timeout_seconds)
    equity_bot = EquityBot(seed=seed)

    hero_seat = engine.cfg.human_seat

    results: List[Tuple[int, int, int]] = []  # (hand_index, net_chips, llm_failures)
    llm_failures_total = 0

    initial_stack = 0
    try:
        if engine.state is not None:
            stacks = getattr(engine.state, "stacks", None) or []
            if 0 <= hero_seat - 1 < len(stacks):
                initial_stack = int(stacks[hero_seat - 1] or 0)
    except Exception:
        initial_stack = 0

    # We rely on TableEngine.advance to apply bot actions until a human
    # prompt or hand end. At each human prompt we inject LLM decisions
    # instead of waiting for UI.
    for hand_index in range(num_hands):
        if not engine.session_active or engine.state is None:
            break

        hand_over = False
        llm_failures_this_hand = 0
        hero_delta = 0

        print(f"[SIM] Hand {hand_index + 1}/{num_hands} started", flush=True)

        while not hand_over:
            messages, prompt = engine.advance(hero_seat)

            # Inspect messages for hand_end / session_end and hero delta
            for msg in messages:
                mtype = msg.get("type")
                if mtype == "hand_end":
                    results_payload = msg.get("results") or []
                    for row in results_payload:
                        if int(row.get("seat", -1)) == hero_seat:
                            try:
                                hero_delta = int(row.get("delta", 0))
                            except Exception:
                                hero_delta = 0
                            break
                    hand_over = True
                elif mtype == "session_end":
                    # Session terminated; mark hand as over and stop outer loop later.
                    hand_over = True

            if hand_over:
                break

            if prompt is None:
                # Defensive: avoid infinite loops if advance returns no prompt
                # and no hand_end/session_end; treat as hand over with zero delta.
                hand_over = True
                break

            seat_to_act = int(prompt.get("to_act"))
            legal_actions: List[Dict[str, Any]] = prompt.get("legal_actions") or []

            if seat_to_act == hero_seat:
                hero_idx = _seat_to_state_index(engine, hero_seat)
                decision = await llm_bot.choose_action(engine, hero_idx, hero_seat)
                engine.apply_action(decision.action)
                if decision.llm_failed:
                    llm_failures_this_hand += 1
            else:
                idx = _seat_to_state_index(engine, seat_to_act)
                action = equity_bot.choose(engine.state, idx, seat_to_act, legal_actions)
                engine.apply_action(action)

        llm_failures_total += llm_failures_this_hand
        results.append((hand_index, hero_delta, llm_failures_this_hand))
        print(
            f"[SIM] Hand {hand_index + 1} finished: "
            f"delta={hero_delta}, llm_failures={llm_failures_this_hand}",
            flush=True,
        )

        if not engine.session_active:
            break

        ok, reason = engine.start_next_hand()
        if not ok:
            break

    total_net = sum(r[1] for r in results)
    hands_played = len(results)
    bb_size = 2  # from 1/2 blinds
    bb100 = (total_net / (bb_size * hands_played)) * 100.0 if hands_played > 0 else 0.0

    print(f"Model: {model_alias}")
    print(f"Hands played: {hands_played}")
    print(f"Total net chips: {total_net}")
    print(f"Winrate (BB/100): {bb100:.2f}")
    print(f"Total LLM decision failures: {llm_failures_total}")

    if csv_output:
        path = Path(csv_output)
        if path.is_dir():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = path / f"llm_sim_{model_alias}_{timestamp}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["hand_index", "net_chips", "llm_failures"])
            for hand_index, net_chips, llm_failures in results:
                writer.writerow([hand_index, net_chips, llm_failures])
        print(f"Wrote per-hand results to {path}")


def main() -> None:
    args = _parse_args()
    asyncio.run(
        _run_simulation(
            model_alias=args.model_alias,
            num_hands=args.num_hands,
            seed=args.seed,
            llm_timeout_seconds=args.llm_timeout_seconds,
            csv_output=args.csv_output,
        )
    )


if __name__ == "__main__":
    main()
