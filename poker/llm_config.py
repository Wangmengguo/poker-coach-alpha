from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


LEGACY_MODEL_IDS: Dict[str, str] = {
    "claude-4.5-sonnet": "claude-4.5-sonnet",
    "claude-opus-4-5": "claude-opus-4-5",
    "gemini-3-flash-preview": "gemini-3-flash-preview",
    "moonshotai/kimi-k2-instruct": "moonshotai/kimi-k2-instruct",
    "gpt-5.1-chat-latest": "gpt-5.1-chat-latest",
    "gpt-5.2": "gpt-5.2",
    "gpt-5.2-pro": "gpt-5.2-pro",
    "deepseek-chat": "deepseek-chat",
    "grok-4-fast-reasoning": "grok-4-fast-reasoning",
}

DEFAULT_TIER_ORDER = ["smart", "balanced", "fast"]


def _data_dir() -> Path:
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def config_path() -> Path:
    return _data_dir() / "llm_config.json"


def _env_default_tiers() -> Dict[str, Dict[str, Any]]:
    default_model = os.getenv("AI_MODEL_ALIAS", "gpt-5.1-chat-latest").strip()
    if not default_model:
        default_model = "gpt-5.1-chat-latest"
    return {
        "smart": {
            "label": "Top intelligence",
            "model": os.getenv("AI_SMART_MODEL", "gpt-5.2-pro").strip() or "gpt-5.2-pro",
            "enabled": True,
            "timeout_seconds": 30,
            "cost_level": "high",
        },
        "balanced": {
            "label": "Balanced",
            "model": os.getenv("AI_BALANCED_MODEL", default_model).strip() or default_model,
            "enabled": True,
            "timeout_seconds": 20,
            "cost_level": "medium",
        },
        "fast": {
            "label": "Fast response",
            "model": os.getenv("AI_FAST_MODEL", "deepseek-chat").strip() or "deepseek-chat",
            "enabled": True,
            "timeout_seconds": 10,
            "cost_level": "low",
        },
    }


def default_config() -> Dict[str, Any]:
    return {
        "provider": os.getenv("AI_PROVIDER", "dummy").strip().lower() or "dummy",
        "api_base": os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_API_URL") or "",
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "default_tier": os.getenv("AI_MODEL_TIER", "balanced").strip() or "balanced",
        "tiers": _env_default_tiers(),
    }


def _normalize_tier(tier_id: str, raw: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    model = str(data.get("model") or fallback.get("model") or "").strip()
    return {
        "label": str(data.get("label") or fallback.get("label") or tier_id),
        "model": model,
        "enabled": bool(data.get("enabled", fallback.get("enabled", True))),
        "timeout_seconds": float(
            data.get("timeout_seconds", fallback.get("timeout_seconds", 20))
        ),
        "cost_level": str(data.get("cost_level") or fallback.get("cost_level") or "medium"),
    }


def load_llm_config() -> Dict[str, Any]:
    cfg = default_config()
    path = config_path()
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for key in ("provider", "api_base", "api_key", "default_tier"):
                    if key in saved:
                        cfg[key] = saved.get(key) or ""
                saved_tiers = saved.get("tiers")
                if isinstance(saved_tiers, dict):
                    tiers = {}
                    for tier_id in DEFAULT_TIER_ORDER:
                        tiers[tier_id] = _normalize_tier(
                            tier_id,
                            saved_tiers.get(tier_id),
                            cfg["tiers"][tier_id],
                        )
                    cfg["tiers"] = tiers
        except Exception:
            pass

    if cfg.get("default_tier") not in cfg.get("tiers", {}):
        cfg["default_tier"] = "balanced"
    return cfg


def save_llm_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = load_llm_config()

    def _value(key: str, fallback: Any) -> Any:
        val = payload.get(key, fallback)
        return fallback if val is None else val

    provider = str(_value("provider", current.get("provider", "dummy"))).strip().lower()
    if provider not in {"dummy", "openai", "gateway"}:
        raise ValueError("invalid_provider")

    next_cfg = {
        "provider": provider,
        "api_base": str(_value("api_base", current.get("api_base", ""))).strip(),
        "api_key": "",
        "default_tier": str(
            _value("default_tier", current.get("default_tier", "balanced"))
        ).strip()
        or "balanced",
        "tiers": {},
    }

    if "api_key" in payload and payload.get("api_key") is not None:
        next_cfg["api_key"] = str(payload.get("api_key") or "").strip()
    else:
        next_cfg["api_key"] = str(current.get("api_key") or "").strip()

    raw_tiers = payload.get("tiers", current.get("tiers", {}))
    if not isinstance(raw_tiers, dict):
        raise ValueError("invalid_tiers")

    defaults = _env_default_tiers()
    for tier_id in DEFAULT_TIER_ORDER:
        tier = _normalize_tier(tier_id, raw_tiers.get(tier_id), defaults[tier_id])
        if not tier["model"]:
            raise ValueError(f"missing_model:{tier_id}")
        next_cfg["tiers"][tier_id] = tier

    if next_cfg["default_tier"] not in next_cfg["tiers"]:
        raise ValueError("invalid_default_tier")

    if next_cfg["provider"] in {"openai", "gateway"} and not next_cfg["api_key"]:
        raise ValueError("missing_api_key")

    path = config_path()
    path.write_text(json.dumps(next_cfg, indent=2, sort_keys=True), encoding="utf-8")
    try:
        path.chmod(0o600)
    except Exception:
        pass
    return next_cfg


def public_config() -> Dict[str, Any]:
    cfg = load_llm_config()
    out = dict(cfg)
    key = str(out.get("api_key") or "")
    out["api_key_set"] = bool(key)
    out["api_key_preview"] = mask_secret(key)
    out.pop("api_key", None)
    return out


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def get_provider_credentials() -> Dict[str, str]:
    cfg = load_llm_config()
    return {
        "provider": str(cfg.get("provider") or "dummy").strip().lower(),
        "api_key": str(cfg.get("api_key") or "").strip(),
        "api_base": str(cfg.get("api_base") or "").strip(),
    }


def is_llm_configured() -> bool:
    creds = get_provider_credentials()
    return creds["provider"] in {"openai", "gateway"} and bool(creds["api_key"])


def get_model_tiers() -> List[Dict[str, Any]]:
    cfg = load_llm_config()
    tiers = cfg.get("tiers", {})
    result: List[Dict[str, Any]] = []
    for tier_id in DEFAULT_TIER_ORDER:
        tier = tiers.get(tier_id, {})
        result.append(
            {
                "id": tier_id,
                "label": tier.get("label") or tier_id,
                "enabled": bool(tier.get("enabled", True)),
                "cost_level": tier.get("cost_level") or "medium",
            }
        )
    return result


def get_enabled_tier_ids() -> List[str]:
    return [t["id"] for t in get_model_tiers() if t.get("enabled")]


def get_default_tier() -> str:
    cfg = load_llm_config()
    tier = str(cfg.get("default_tier") or "balanced")
    enabled = get_enabled_tier_ids()
    if tier in enabled:
        return tier
    return enabled[0] if enabled else "balanced"


def resolve_model_id(alias_or_tier: Optional[str]) -> str:
    cfg = load_llm_config()
    alias = str(alias_or_tier or cfg.get("default_tier") or "balanced").strip()
    tiers = cfg.get("tiers", {})
    if alias in tiers and tiers[alias].get("enabled", True):
        return str(tiers[alias].get("model") or "").strip()
    if alias in LEGACY_MODEL_IDS:
        return LEGACY_MODEL_IDS[alias]
    default_tier = get_default_tier()
    return str(tiers.get(default_tier, {}).get("model") or "gpt-5.1-chat-latest").strip()


async def list_gateway_models(config_override: Optional[Dict[str, Any]] = None) -> List[str]:
    from openai import AsyncOpenAI  # type: ignore

    creds = get_provider_credentials()
    if config_override:
        creds.update(
            {
                "api_key": str(config_override.get("api_key") or creds["api_key"]).strip(),
                "api_base": str(config_override.get("api_base") or creds["api_base"]).strip(),
            }
        )
    client = AsyncOpenAI(
        api_key=creds["api_key"] or None,
        base_url=creds["api_base"] or None,
    )
    models = await client.models.list()
    ids: List[str] = []
    for item in getattr(models, "data", []) or []:
        model_id = getattr(item, "id", None)
        if isinstance(model_id, str) and model_id:
            ids.append(model_id)
    return sorted(set(ids))


async def test_gateway_model(
    model: str,
    config_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from openai import AsyncOpenAI  # type: ignore

    creds = get_provider_credentials()
    if config_override:
        creds.update(
            {
                "api_key": str(config_override.get("api_key") or creds["api_key"]).strip(),
                "api_base": str(config_override.get("api_base") or creds["api_base"]).strip(),
            }
        )
    if not creds["api_key"]:
        return {"ok": False, "error": "missing_api_key", "model": model}

    client = AsyncOpenAI(
        api_key=creds["api_key"] or None,
        base_url=creds["api_base"] or None,
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=256,
            temperature=0,
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "model": model}

    text = ""
    finish_reason = None
    try:
        choice = resp.choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        text = str(choice.message.content or "").strip()
    except Exception:
        text = ""

    if not text:
        return {
            "ok": False,
            "error": "empty_response",
            "model": model,
            "finish_reason": finish_reason,
        }
    return {"ok": True, "model": model, "response": text[:80]}
