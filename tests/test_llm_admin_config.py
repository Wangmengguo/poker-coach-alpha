from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app, _public_invite_failure_reason
from poker.ai_coach import set_current_model_alias


def test_public_ai_settings_expose_tiers(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    set_current_model_alias("balanced")
    client = TestClient(app)
    res = client.get("/settings/ai_model")
    assert res.status_code == 200
    data = res.json()
    assert data["model_alias"] in {"smart", "balanced", "fast"}
    assert data["allowed"] == ["smart", "balanced", "fast"]
    assert [tier["id"] for tier in data["tiers"]] == ["smart", "balanced", "fast"]


def test_admin_config_requires_admin_access(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("LOCAL_ADMIN_BYPASS", "0")
    client = TestClient(app)
    assert client.get("/admin/llm/config").status_code == 403


def test_admin_page_is_public_html() -> None:
    client = TestClient(app)
    res = client.get("/admin/llm")
    assert res.status_code == 200
    html = res.text
    assert "Admin Token" in html
    assert "sessionStorage" in html
    assert "admin_token" not in html


def test_admin_config_rejects_query_token(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "dev-token")
    monkeypatch.setenv("LOCAL_ADMIN_BYPASS", "0")
    client = TestClient(app)
    assert client.get("/admin/llm/config?admin_token=dev-token").status_code == 403


def test_admin_config_accepts_header_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_TOKEN", "dev-token")
    monkeypatch.setenv("LOCAL_ADMIN_BYPASS", "0")
    client = TestClient(app)
    res = client.get("/admin/llm/config", headers={"x-admin-token": "dev-token"})
    assert res.status_code == 200


def test_settings_ai_model_post_requires_admin(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "dev-token")
    monkeypatch.setenv("LOCAL_ADMIN_BYPASS", "0")
    set_current_model_alias("balanced")
    client = TestClient(app)
    assert (
        client.post(
            "/settings/ai_model",
            json={"model_alias": "fast"},
        ).status_code
        == 403
    )
    res = client.post(
        "/settings/ai_model",
        headers={"x-admin-token": "dev-token"},
        json={"model_alias": "fast"},
    )
    assert res.status_code == 200
    assert res.json()["model_alias"] == "fast"


def test_admin_config_save_masks_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_TOKEN", "dev-token")
    set_current_model_alias("balanced")
    client = TestClient(app)

    payload = {
        "provider": "openai",
        "api_base": "https://gateway.example.test/v1",
        "api_key": "sk-test-secret",
        "default_tier": "fast",
        "tiers": {
            "smart": {"label": "Top", "model": "model-smart", "enabled": True},
            "balanced": {"label": "Balanced", "model": "model-balanced", "enabled": True},
            "fast": {"label": "Fast", "model": "model-fast", "enabled": True},
        },
    }
    res = client.post(
        "/admin/llm/config",
        headers={"x-admin-token": "dev-token"},
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert "api_key" not in data
    assert data["api_key_set"] is True
    assert data["api_key_preview"] == "sk-t...cret"
    assert data["default_tier"] == "fast"

    settings = client.get("/settings/ai_model").json()
    assert settings["model_alias"] == "fast"


def test_public_invite_failure_reason_masks_enumeration() -> None:
    assert _public_invite_failure_reason("not_found") == "invalid_invite"
    assert _public_invite_failure_reason("expired") == "invalid_invite"
    assert _public_invite_failure_reason("revoked") == "invalid_invite"
    assert _public_invite_failure_reason("session_mismatch") == "session_mismatch"
    assert _public_invite_failure_reason("daily_quota_exhausted") == "daily_quota_exhausted"


def test_save_llm_config_requires_api_key_for_openai(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from poker.llm_config import save_llm_config

    payload = {
        "provider": "openai",
        "api_base": "https://gateway.example.test/v1",
        "api_key": "",
        "default_tier": "balanced",
        "tiers": {
            "smart": {"label": "Top", "model": "model-smart", "enabled": True},
            "balanced": {"label": "Balanced", "model": "model-balanced", "enabled": True},
            "fast": {"label": "Fast", "model": "model-fast", "enabled": True},
        },
    }
    try:
        save_llm_config(payload)
        assert False, "expected missing_api_key"
    except ValueError as exc:
        assert str(exc) == "missing_api_key"


def test_save_llm_config_keeps_existing_api_key_when_omitted(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from poker.llm_config import load_llm_config, save_llm_config

    base_payload = {
        "provider": "openai",
        "api_base": "https://gateway.example.test/v1",
        "api_key": "sk-existing-secret",
        "default_tier": "balanced",
        "tiers": {
            "smart": {"label": "Top", "model": "model-smart", "enabled": True},
            "balanced": {"label": "Balanced", "model": "model-balanced", "enabled": True},
            "fast": {"label": "Fast", "model": "model-fast", "enabled": True},
        },
    }
    save_llm_config(base_payload)
    save_llm_config(
        {
            "provider": "openai",
            "api_base": "https://gateway.example.test/v1",
            "default_tier": "fast",
            "tiers": base_payload["tiers"],
        }
    )
    cfg = load_llm_config()
    assert cfg["api_key"] == "sk-existing-secret"
    assert cfg["default_tier"] == "fast"


def test_test_gateway_model_empty_response(monkeypatch) -> None:
    import openai
    from poker import llm_config as mod

    class _Msg:
        content = ""

    class _Choice:
        message = _Msg()
        finish_reason = "length"

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        async def create(self, **kwargs):
            return _Resp()

    class _Client:
        chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(mod, "get_provider_credentials", lambda: {"api_key": "sk-test", "api_base": ""})
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: _Client())
    result = asyncio.run(mod.test_gateway_model("glm-test"))
    assert result["ok"] is False
    assert result["error"] == "empty_response"
    assert result["finish_reason"] == "length"


def test_test_gateway_model_structured_sdk_error(monkeypatch) -> None:
    import openai
    from poker import llm_config as mod

    class _Completions:
        async def create(self, **kwargs):
            raise RuntimeError("gateway down")

    class _Client:
        chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(mod, "get_provider_credentials", lambda: {"api_key": "sk-test", "api_base": ""})
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: _Client())
    result = asyncio.run(mod.test_gateway_model("glm-test"))
    assert result["ok"] is False
    assert "RuntimeError: gateway down" in result["error"]
