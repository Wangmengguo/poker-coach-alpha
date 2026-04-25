from __future__ import annotations

from poker.ai_coach import (
    ALLOWED_MODELS,
    get_allowed_model_aliases,
    get_current_model_alias,
    set_current_model_alias,
)
from poker.llm_config import resolve_model_id


def test_gpt_52_models_are_allowed() -> None:
    assert "gpt-5.2" in ALLOWED_MODELS
    assert "gpt-5.2-pro" in ALLOWED_MODELS
    assert "gemini-3-flash-preview" in ALLOWED_MODELS


def test_model_tiers_are_allowed() -> None:
    allowed = get_allowed_model_aliases()
    assert "smart" in allowed
    assert "balanced" in allowed
    assert "fast" in allowed


def test_set_model_alias_roundtrip_balanced_tier() -> None:
    previous = get_current_model_alias()
    try:
        assert set_current_model_alias("balanced") is True
        assert get_current_model_alias() == "balanced"
        assert resolve_model_id("balanced")
    finally:
        set_current_model_alias(previous)
