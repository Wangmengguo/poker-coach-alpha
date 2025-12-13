from __future__ import annotations

from poker.ai_coach import ALLOWED_MODELS, get_current_model_alias, set_current_model_alias


def test_gpt_52_models_are_allowed() -> None:
    assert "gpt-5.2" in ALLOWED_MODELS
    assert "gpt-5.2-pro" in ALLOWED_MODELS


def test_set_model_alias_roundtrip_gpt_52() -> None:
    previous = get_current_model_alias()
    try:
        assert set_current_model_alias("gpt-5.2-pro") is True
        assert get_current_model_alias() == "gpt-5.2-pro"
    finally:
        set_current_model_alias(previous)
