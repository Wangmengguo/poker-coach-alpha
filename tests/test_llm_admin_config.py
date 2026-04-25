from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
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


def test_admin_page_forwards_query_token_to_fetch_calls(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "dev-token")
    monkeypatch.setenv("LOCAL_ADMIN_BYPASS", "0")
    client = TestClient(app)

    res = client.get("/admin/llm?admin_token=dev-token")
    assert res.status_code == 200
    html = res.text
    assert 'new URLSearchParams(window.location.search).get("admin_token")' in html
    assert 'headers["x-admin-token"] = adminToken' in html


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
    res = client.post("/admin/llm/config", headers={"x-admin-token": "dev-token"}, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "api_key" not in data
    assert data["api_key_set"] is True
    assert data["api_key_preview"] == "sk-t...cret"
    assert data["default_tier"] == "fast"

    settings = client.get("/settings/ai_model").json()
    assert settings["model_alias"] == "fast"
