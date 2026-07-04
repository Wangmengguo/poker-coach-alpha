"""Invite code management for API access control.

This module provides SQLite-backed storage and validation for invite codes.
Invite codes are used to gate access to LLM-powered AI Coach features.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import string
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _generate_code() -> str:
    """Generate a random invite code in format POKER-XXXXXXXX."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(8))
    return f"POKER-{suffix}"


@dataclass(frozen=True)
class InviteValidationResult:
    ok: bool
    reason: str = ""
    code: str = ""


class InviteCodeStore:
    """SQLite-backed store for invite codes.

    Thread-safe for typical web server usage (SQLite handles locking).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the store.

        Args:
            db_path: Path to SQLite database file. If None, uses
                     DATA_DIR/invites.db where DATA_DIR defaults to ./data.
        """
        if db_path is None:
            data_dir = os.getenv("DATA_DIR", "data")
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            db_path = os.path.join(data_dir, "invites.db")

        self.db_path = db_path
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new database connection."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        """Create the invite_codes table if it doesn't exist."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS invite_codes (
                    code TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    note TEXT,
                    last_used_at TEXT
                )
            """)
            existing = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(invite_codes)").fetchall()
            }
            migrations = {
                "expires_at": "ALTER TABLE invite_codes ADD COLUMN expires_at TEXT",
                "max_uses": "ALTER TABLE invite_codes ADD COLUMN max_uses INTEGER",
                "use_count": (
                    "ALTER TABLE invite_codes ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0"
                ),
                "daily_quota": "ALTER TABLE invite_codes ADD COLUMN daily_quota INTEGER",
                "daily_used_on": "ALTER TABLE invite_codes ADD COLUMN daily_used_on TEXT",
                "daily_use_count": (
                    "ALTER TABLE invite_codes ADD COLUMN daily_use_count INTEGER NOT NULL DEFAULT 0"
                ),
                "allowed_model_aliases": (
                    "ALTER TABLE invite_codes ADD COLUMN allowed_model_aliases TEXT"
                ),
                "session_id": "ALTER TABLE invite_codes ADD COLUMN session_id TEXT",
                "bound_at": "ALTER TABLE invite_codes ADD COLUMN bound_at TEXT",
            }
            for column, sql in migrations.items():
                if column not in existing:
                    conn.execute(sql)
            conn.commit()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    @staticmethod
    def _normalize_session_id(session_id: Optional[str]) -> str:
        return str(session_id or "").strip()[:128]

    @staticmethod
    def _allowed_models(raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [part.strip() for part in str(raw).split(",") if part.strip()]

    @staticmethod
    def _encode_models(models: Optional[List[str]]) -> Optional[str]:
        if not models:
            return None
        clean = [str(model).strip() for model in models if str(model).strip()]
        return json.dumps(clean, separators=(",", ":")) if clean else None

    def _check_row(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        code: str,
        session_id: Optional[str],
        model_alias: Optional[str],
        bind_session: bool,
        require_session: bool,
    ) -> InviteValidationResult:
        if not row["is_active"]:
            return InviteValidationResult(False, "revoked", code)

        expires_at = self._parse_dt(row["expires_at"])
        if expires_at is not None and expires_at <= self._utc_now():
            return InviteValidationResult(False, "expired", code)

        model = str(model_alias or "").strip()
        allowed_models = self._allowed_models(row["allowed_model_aliases"])
        if model and allowed_models and model not in set(allowed_models):
            return InviteValidationResult(False, "model_not_allowed", code)

        normalized_session = self._normalize_session_id(session_id)
        if require_session and not normalized_session:
            return InviteValidationResult(False, "session_required", code)
        existing_session = str(row["session_id"] or "").strip()
        if existing_session:
            if (require_session or normalized_session) and normalized_session != existing_session:
                return InviteValidationResult(False, "session_mismatch", code)
        elif bind_session and normalized_session:
            now = self._utc_now().isoformat()
            conn.execute(
                "UPDATE invite_codes SET session_id = ?, bound_at = ? WHERE code = ?",
                (normalized_session, now, code),
            )

        return InviteValidationResult(True, "", code)

    def validate_code(self, code: str) -> bool:
        """Check if an invite code is valid and active.

        Also updates last_used_at timestamp on successful validation.

        To avoid excessive write amplification (e.g. from debounced UI validation
        or multiple concurrent WS connections), the last_used_at field is
        rate-limited to at most once per minute per code.

        Args:
            code: The invite code to validate.

        Returns:
            True if the code exists and is active, False otherwise.
        """
        if not code or not isinstance(code, str):
            return False

        code = code.strip().upper()
        if not code:
            return False

        return self.check_code(code).ok

    def check_code(
        self,
        code: str,
        *,
        session_id: Optional[str] = None,
        model_alias: Optional[str] = None,
        bind_session: bool = True,
        require_session: bool = False,
        update_last_used: bool = True,
    ) -> InviteValidationResult:
        """Validate an invite code without consuming LLM quota."""
        if not code or not isinstance(code, str):
            return InviteValidationResult(False, "missing")

        code = code.strip().upper()
        if not code:
            return InviteValidationResult(False, "missing")

        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT * FROM invite_codes WHERE code = ?", (code,))
                row = cursor.fetchone()

                if row is None:
                    return InviteValidationResult(False, "not_found", code)

                result = self._check_row(
                    conn,
                    row,
                    code=code,
                    session_id=session_id,
                    model_alias=model_alias,
                    bind_session=bind_session,
                    require_session=require_session,
                )
                if not result.ok:
                    return result

                if update_last_used:
                    should_update_last_used = True
                    last_used_dt = self._parse_dt(row["last_used_at"])
                    now_dt = self._utc_now()
                    if last_used_dt is not None:
                        should_update_last_used = (
                            now_dt - last_used_dt
                        ).total_seconds() >= 60
                    if should_update_last_used:
                        conn.execute(
                            "UPDATE invite_codes SET last_used_at = ? WHERE code = ?",
                            (now_dt.isoformat(), code),
                        )
                conn.commit()
                return result
        except sqlite3.Error:
            return InviteValidationResult(False, "store_error", code)

    def consume_llm_call(
        self,
        code: str,
        *,
        session_id: Optional[str] = None,
        model_alias: Optional[str] = None,
        require_session: bool = False,
    ) -> InviteValidationResult:
        """Validate an invite code and consume one LLM call quota."""
        if not code or not isinstance(code, str):
            return InviteValidationResult(False, "missing")

        code = code.strip().upper()
        today = self._utc_now().date().isoformat()

        try:
            with self._get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute("SELECT * FROM invite_codes WHERE code = ?", (code,))
                row = cursor.fetchone()
                if row is None:
                    return InviteValidationResult(False, "not_found", code)

                result = self._check_row(
                    conn,
                    row,
                    code=code,
                    session_id=session_id,
                    model_alias=model_alias,
                    bind_session=True,
                    require_session=require_session,
                )
                if not result.ok:
                    return result

                max_uses = row["max_uses"]
                use_count = int(row["use_count"] or 0)
                if max_uses is not None and use_count >= int(max_uses):
                    return InviteValidationResult(False, "usage_exhausted", code)

                daily_quota = row["daily_quota"]
                daily_used_on = str(row["daily_used_on"] or "")
                daily_use_count = int(row["daily_use_count"] or 0)
                if daily_used_on != today:
                    daily_use_count = 0
                if daily_quota is not None and daily_use_count >= int(daily_quota):
                    return InviteValidationResult(False, "daily_quota_exhausted", code)

                now = self._utc_now().isoformat()
                conn.execute(
                    """
                    UPDATE invite_codes
                    SET use_count = use_count + 1,
                        daily_used_on = ?,
                        daily_use_count = ?,
                        last_used_at = ?
                    WHERE code = ?
                    """,
                    (today, daily_use_count + 1, now, code),
                )
                conn.commit()
                return InviteValidationResult(True, "", code)
        except sqlite3.Error:
            return InviteValidationResult(False, "store_error", code)

    def create_code(
        self,
        note: Optional[str] = None,
        *,
        expires_at: Optional[str] = None,
        max_uses: Optional[int] = None,
        daily_quota: Optional[int] = None,
        allowed_model_aliases: Optional[List[str]] = None,
    ) -> str:
        """Generate and store a new invite code.

        Args:
            note: Optional note/description for the code.

        Returns:
            The newly created invite code.
        """
        code = _generate_code()
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            # Handle potential (very unlikely) collision
            for _ in range(10):
                try:
                    conn.execute(
                        """
                        INSERT INTO invite_codes (
                            code, created_at, is_active, note, expires_at, max_uses,
                            daily_quota, allowed_model_aliases
                        )
                        VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                        """,
                        (
                            code,
                            now,
                            note,
                            expires_at,
                            max_uses,
                            daily_quota,
                            self._encode_models(allowed_model_aliases),
                        ),
                    )
                    conn.commit()
                    return code
                except sqlite3.IntegrityError:
                    code = _generate_code()

            raise RuntimeError("Failed to generate unique invite code")

    def list_codes(self, include_revoked: bool = True) -> List[dict]:
        """List all invite codes.

        Args:
            include_revoked: If True, include revoked codes in the list.

        Returns:
            List of dicts with code details.
        """
        with self._get_conn() as conn:
            if include_revoked:
                cursor = conn.execute("SELECT * FROM invite_codes ORDER BY created_at DESC")
            else:
                cursor = conn.execute(
                    "SELECT * FROM invite_codes WHERE is_active = 1 ORDER BY created_at DESC"
                )

            return [dict(row) for row in cursor.fetchall()]

    def revoke_code(self, code: str) -> bool:
        """Revoke an invite code.

        Args:
            code: The invite code to revoke.

        Returns:
            True if the code was found and revoked, False if not found.
        """
        if not code or not isinstance(code, str):
            return False

        code = code.strip().upper()

        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE invite_codes SET is_active = 0 WHERE code = ?",
                (code,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_code(self, code: str) -> Optional[dict]:
        """Get details for a specific invite code.

        Args:
            code: The invite code to look up.

        Returns:
            Dict with code details, or None if not found.
        """
        if not code or not isinstance(code, str):
            return None

        code = code.strip().upper()

        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM invite_codes WHERE code = ?",
                (code,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
