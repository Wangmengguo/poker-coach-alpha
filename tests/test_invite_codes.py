from __future__ import annotations

from datetime import datetime, timedelta, timezone

from poker.invite_codes import InviteCodeStore


def _store(tmp_path) -> InviteCodeStore:
    return InviteCodeStore(str(tmp_path / "invites.db"))


def test_invite_code_binds_to_first_session(tmp_path) -> None:
    store = _store(tmp_path)
    code = store.create_code()

    assert store.check_code(code, session_id="session-a", require_session=True).ok is True
    assert store.check_code(code, session_id="session-a", require_session=True).ok is True

    result = store.check_code(code, session_id="session-b", require_session=True)
    assert result.ok is False
    assert result.reason == "session_mismatch"
    assert store.validate_code(code) is True


def test_invite_code_requires_session_when_requested(tmp_path) -> None:
    store = _store(tmp_path)
    code = store.create_code()

    result = store.check_code(code, require_session=True)
    assert result.ok is False
    assert result.reason == "session_required"


def test_invite_code_expiry_is_enforced(tmp_path) -> None:
    store = _store(tmp_path)
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    code = store.create_code(expires_at=expired)

    result = store.check_code(code, session_id="s", require_session=True)
    assert result.ok is False
    assert result.reason == "expired"


def test_invite_code_total_use_limit_is_consumed_only_on_llm_call(tmp_path) -> None:
    store = _store(tmp_path)
    code = store.create_code(max_uses=1)

    assert store.check_code(code, session_id="s", require_session=True).ok is True
    assert store.check_code(code, session_id="s", require_session=True).ok is True
    assert store.consume_llm_call(code, session_id="s", require_session=True).ok is True

    result = store.consume_llm_call(code, session_id="s", require_session=True)
    assert result.ok is False
    assert result.reason == "usage_exhausted"


def test_invite_code_daily_quota_is_enforced(tmp_path) -> None:
    store = _store(tmp_path)
    code = store.create_code(daily_quota=1)

    assert store.consume_llm_call(code, session_id="s", require_session=True).ok is True

    result = store.consume_llm_call(code, session_id="s", require_session=True)
    assert result.ok is False
    assert result.reason == "daily_quota_exhausted"


def test_invite_code_model_allowlist_is_enforced(tmp_path) -> None:
    store = _store(tmp_path)
    code = store.create_code(allowed_model_aliases=["fast"])

    assert (
        store.consume_llm_call(
            code,
            session_id="s",
            model_alias="fast",
            require_session=True,
        ).ok
        is True
    )

    result = store.consume_llm_call(
        code,
        session_id="s",
        model_alias="balanced",
        require_session=True,
    )
    assert result.ok is False
    assert result.reason == "model_not_allowed"


def test_new_invite_codes_use_eight_char_suffix(tmp_path) -> None:
    store = _store(tmp_path)
    code = store.create_code()
    assert code.startswith("POKER-")
    assert len(code) == len("POKER-") + 8
