from __future__ import annotations

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
