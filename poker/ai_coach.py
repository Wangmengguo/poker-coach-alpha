from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from .analysis.models import DecisionContext


class AiProvider(Protocol):
    async def generate(self, prompt: str) -> str:
        ...


@dataclass
class AiAdvice:
    recommended_action: Optional[Dict[str, Any]]
    secondary_action: Optional[Dict[str, Any]]
    confidence: Optional[float]
    explanation: Optional[str]
    reason: Optional[str] = None


class DummyProvider:
    async def generate(self, prompt: str) -> str:
        return ""


# Whitelisted model aliases for LiteLLM-backed providers.
# Keys are the human-visible names; values are the underlying model ids
# passed to LiteLLM. For the current OpenAI-compatible gateway setup,
# we keep them identical so the UI always shows the real model name.
ALLOWED_MODELS: Dict[str, str] = {
    "claude-4.5-sonnet": "claude-4.5-sonnet",
    "claude-opus-4-5": "claude-opus-4-5",
    "moonshotai/kimi-k2-instruct": "moonshotai/kimi-k2-instruct",
    "kimi-k2-thinking": "kimi-k2-thinking",
    "gemini-3-pro-preview": "gemini-3-pro-preview",
    "gpt-5.1-chat-latest": "gpt-5.1-chat-latest",
    "deepseek-chat": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
}

_DEFAULT_ALIAS = "gpt-5.1-chat-latest"
_current_model_alias: str = os.getenv("AI_MODEL_ALIAS", _DEFAULT_ALIAS)


def get_allowed_model_aliases() -> List[str]:
    return sorted(ALLOWED_MODELS.keys())


def get_current_model_alias() -> str:
    alias = _current_model_alias or _DEFAULT_ALIAS
    if alias in ALLOWED_MODELS:
        return alias
    # Fallback: pick a stable first key if default is invalid
    if ALLOWED_MODELS:
        return sorted(ALLOWED_MODELS.keys())[0]
    return _DEFAULT_ALIAS


def set_current_model_alias(alias: str) -> bool:
    global _current_model_alias
    if alias not in ALLOWED_MODELS:
        return False
    _current_model_alias = alias
    return True


class LitellmProvider:
    async def generate(self, prompt: str) -> str:
        """Call LiteLLM with the current model alias.

        Any errors are swallowed and result in an empty string so that
        the caller can safely fall back to heuristic-only advice.
        """
        try:
            import litellm  # type: ignore
        except Exception:
            return ""

        alias = get_current_model_alias()
        model = ALLOWED_MODELS.get(alias, alias)
        try:
            resp = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.2,
            )
        except Exception:
            return ""

        try:
            choice = resp.choices[0]
            message = getattr(choice, "message", None) or getattr(choice, "delta", None)
            if isinstance(message, dict):
                content = message.get("content")
            else:
                content = getattr(message, "content", None)
            if isinstance(content, list):
                text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            else:
                text = content
            return str(text or "").strip()
        except Exception:
            return ""


def _match_action_spec(
    spec: Dict[str, Any],
    legal_actions: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Map a JSON-specified action to a concrete legal action.

    We keep the mapping simple and defensive:
    - type-only actions (check/fold) are matched by type.
    - call: amount must match a legal call amount (if provided); if omitted, use the first legal call.
    - raise_to: if a legal action has an explicit amount, match exactly; if there is a range (min/max),
      accept any amount within the range and normalize to {'type': 'raise_to', 'amount': amount}.
    """
    if not spec:
        return None
    a_type = str(spec.get("type", "") or "").strip()
    if not a_type:
        return None
    amount_val = spec.get("amount")
    try:
        amt = int(amount_val) if amount_val is not None else None
    except Exception:
        amt = None

    for la in legal_actions:
        l_type = str(la.get("type", "") or "").strip()
        if l_type != a_type:
            continue
        if a_type in ("check", "fold"):
            return {"type": a_type}
        if a_type == "call":
            legal_amt = la.get("amount")
            if legal_amt is None:
                if amt is None:
                    return {"type": "call"}
                continue
            if amt is None or int(legal_amt) == amt:
                return {"type": "call", "amount": int(legal_amt)}
        if a_type == "raise_to":
            legal_amt = la.get("amount")
            if legal_amt is not None:
                if amt is None:
                    continue
                if int(legal_amt) == amt:
                    return {"type": "raise_to", "amount": int(legal_amt)}
            l_min = la.get("min")
            l_max = la.get("max")
            if amt is not None and (l_min is not None or l_max is not None):
                if (l_min is None or amt >= int(l_min)) and (l_max is None or amt <= int(l_max)):
                    return {"type": "raise_to", "amount": amt}
    return None


def _parse_llm_json(
    text: str,
    legal_actions: List[Dict[str, Any]],
) -> Optional[AiAdvice]:
    """Best-effort parse of LLM JSON output into AiAdvice.

    The model is instructed to return a single JSON object, but we defensively:
    - extract the first {...} block,
    - attempt json.loads,
    - map recommended/secondary via _match_action_spec.
    """
    import json
    if not text:
        return None
    s = text.strip()
    # Try to locate a JSON object within the text
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = s[start : end + 1]
    try:
        data = json.loads(candidate)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    rec_spec = data.get("recommended")
    sec_spec = data.get("secondary") or data.get("secondary_action")
    rec_action = _match_action_spec(rec_spec or {}, legal_actions)
    sec_action = _match_action_spec(sec_spec or {}, legal_actions) if sec_spec else None

    # Confidence
    conf_val = data.get("confidence")
    conf: Optional[float]
    try:
        conf = float(conf_val)
        if conf < 0.0:
            conf = 0.0
        if conf > 1.0:
            conf = 1.0
    except Exception:
        conf = None

    explanation = data.get("explanation")
    if explanation is not None:
        explanation = str(explanation)

    if rec_action is None and sec_action is None and explanation is None:
        return None

    return AiAdvice(
        recommended_action=rec_action,
        secondary_action=sec_action,
        confidence=conf,
        explanation=explanation,
        reason="llm_actions",
    )


def _format_core_metrics(dc: DecisionContext) -> str:
    parts: List[str] = []
    parts.append(f"Street: {dc.street}")
    parts.append(f"Hero position: {dc.hero_position or '-'}")
    parts.append(f"Pot: {dc.pot}, To call: {dc.to_call}")
    parts.append(f"SPR: {dc.spr}")
    if dc.players_count:
        parts.append(f"Players: {dc.players_count}")
    if dc.pot_odds_pct is not None:
        parts.append(f"Pot odds: {dc.pot_odds_pct}%")
    if dc.required_equity_pct is not None:
        parts.append(f"Required equity: {dc.required_equity_pct}%")
    if dc.hand_label:
        parts.append(f"Hand: {dc.hand_label}")
    if dc.hand_strength_pct is not None:
        parts.append(f"Hand strength: ~{round(dc.hand_strength_pct)}%")
    if dc.outs:
        parts.append(f"Outs: {dc.outs}")
    # Cards (hero + board); we only include hero's own hole cards and public board,
    # never opponents' hidden cards.
    try:
        if dc.hero_cards:
            parts.append(f"Hero cards: {' '.join(dc.hero_cards)}")
    except Exception:
        pass
    try:
        if dc.board_cards:
            parts.append(f"Board: {' '.join(dc.board_cards)}")
    except Exception:
        pass
    return " | ".join(parts)


def _summarize_action_history(history: Optional[List[Dict[str, Any]]], limit: int = 10) -> str:
    if not history:
        return "[]"
    # Take the last N actions for brevity
    tail = history[-limit:]
    lines: List[str] = []
    for h in tail:
        street = h.get("street", "?")
        pos = h.get("position") or f"Seat {h.get('seat', '?')}"
        a_type = h.get("action_type", "?")
        amt = h.get("amount") or 0
        if a_type in ("call", "raise_to") and amt:
            lines.append(f"{street}: {pos} {a_type} ${amt}")
        else:
            lines.append(f"{street}: {pos} {a_type}")
    return "[ " + " | ".join(lines) + " ]"


def build_prompt(
    dc: DecisionContext,
    legal_actions: List[Dict[str, Any]],
    action_history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    metrics = _format_core_metrics(dc)
    actions_desc = []
    for a in legal_actions:
        t = a.get("type")
        amt = a.get("amount")
        if t in ("call", "raise_to") and amt is not None:
            actions_desc.append(f"{t} ${amt}")
        else:
            actions_desc.append(str(t))
    actions_text = ", ".join(actions_desc)
    history_text = _summarize_action_history(action_history)
    return (
        "You are a poker coach for No-Limit Hold'em.\n"
        "You will be given the current situation for the HERO seat and a list of legal actions.\n"
        "Choose ONE recommended action and, optionally, ONE secondary action from the legal list only.\n"
        "Respond STRICTLY as a single JSON object with the following shape and no extra text:\n"
        "{\n"
        '  \"recommended\": {\"type\": \"call\" | \"fold\" | \"check\" | \"raise_to\", \"amount\": <int optional for call/raise>},\n'
        '  \"secondary\": {\"type\": \"call\" | \"fold\" | \"check\" | \"raise_to\", \"amount\": <int optional>},\n'
        '  \"confidence\": <float between 0 and 1>,\n'
        '  \"explanation\": \"short natural-language explanation\"\n'
        "}\n"
        "Rules:\n"
        "- Only use actions that appear in the legal list below.\n"
        "- For raise_to and call, the amount must match one of the legal options or lie within a legal min/max range.\n"
        "- If you are unsure, you may set secondary to null.\n"
        "- Do NOT include any commentary outside the JSON.\n\n"
        f"Context: {metrics}\n"
        f"Legal actions: {actions_text}\n"
        f"Recent action history: {history_text}\n"
    )


def select_actions_heuristic(
    dc: DecisionContext, legal_actions: List[Dict[str, Any]]
) -> AiAdvice:
    recommended = None
    secondary = None
    explanation = None
    confidence = None
    reason = "heuristic"

    call_action = None
    fold_action = None
    raise_actions: List[Dict[str, Any]] = []
    for a in legal_actions:
        t = a.get("type")
        if t == "call":
            call_action = a
        elif t == "fold":
            fold_action = a
        elif t == "raise_to":
            raise_actions.append(a)

    strength = dc.hand_strength_pct or 0.0
    required = dc.required_equity_pct or 0.0

    if strength >= required + 20.0 and raise_actions:
        recommended = max(
            raise_actions, key=lambda x: int(x.get("amount") or 0)
        )
        secondary = call_action
        confidence = 0.8
        explanation = (
            "Hand strength appears well above the break-even equity, so playing aggressively "
            "with a raise is reasonable. Calling is a safer alternative."
        )
    elif strength >= required and call_action is not None:
        recommended = call_action
        secondary = raise_actions[0] if raise_actions else fold_action
        confidence = 0.7
        explanation = (
            "Hand strength is near or slightly above the required equity. Calling keeps the pot "
            "manageable while realizing your equity."
        )
    else:
        if fold_action is not None:
            recommended = fold_action
            secondary = call_action
        else:
            recommended = call_action or (raise_actions[0] if raise_actions else None)
            secondary = None
        confidence = 0.6
        explanation = (
            "Hand strength looks weak relative to the required equity, so folding is often best. "
            "If you continue, prefer the smallest-investment option."
        )

    return AiAdvice(
        recommended_action=recommended,
        secondary_action=secondary,
        confidence=confidence,
        explanation=explanation,
        reason=reason,
    )


def get_ai_provider_from_env() -> Optional[AiProvider]:
    provider_name = os.getenv("AI_PROVIDER", "").strip().lower()
    if not provider_name or provider_name == "dummy":
        return DummyProvider()
    if provider_name == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return DummyProvider()
        return LitellmProvider()
    return DummyProvider()


async def generate_ai_advice(
    dc: DecisionContext,
    legal_actions: List[Dict[str, Any]],
    provider: Optional[AiProvider],
    action_history: Optional[List[Dict[str, Any]]] = None,
) -> AiAdvice:
    if not legal_actions:
        return AiAdvice(
            recommended_action=None,
            secondary_action=None,
            confidence=None,
            explanation=None,
            reason="no_legal_actions",
        )

    if provider is None:
        return select_actions_heuristic(dc, legal_actions)

    try:
        prompt = build_prompt(dc, legal_actions, action_history=action_history)
        raw_text = await provider.generate(prompt)
        parsed = _parse_llm_json(raw_text, legal_actions)
        # If we got a usable mapping from the LLM, prefer it.
        if parsed and parsed.recommended_action:
            # Ensure explanation is not excessively long
            if parsed.explanation:
                parsed.explanation = parsed.explanation[:500]
            if parsed.confidence is None:
                parsed.confidence = 0.7
            return parsed

        # Fallback: if the JSON was unusable, fall back to heuristic actions
        # but still try to reuse any explanation text as a plain explanation.
        heuristic = select_actions_heuristic(dc, legal_actions)
        if parsed and parsed.explanation:
            heuristic.explanation = parsed.explanation[:500]
            heuristic.reason = "llm_explanation_heuristic_actions"
        return heuristic
    except Exception:
        return select_actions_heuristic(dc, legal_actions)
