"""Invite code management for API access control.

This module provides SQLite-backed storage and validation for invite codes.
Invite codes are used to gate access to LLM-powered AI Coach features.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _generate_code() -> str:
    """Generate a random invite code in format POKER-XXXXXX."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(6))
    return f"POKER-{suffix}"


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
            conn.commit()

    def validate_code(self, code: str) -> bool:
        """Check if an invite code is valid and active.

        Also updates last_used_at timestamp on successful validation.

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

        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT is_active FROM invite_codes WHERE code = ?",
                (code,),
            )
            row = cursor.fetchone()

            if row is None:
                return False

            if not row["is_active"]:
                return False

            # Update last_used_at
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE invite_codes SET last_used_at = ? WHERE code = ?",
                (now, code),
            )
            conn.commit()
            return True

    def create_code(self, note: Optional[str] = None) -> str:
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
                        INSERT INTO invite_codes (code, created_at, is_active, note)
                        VALUES (?, ?, 1, ?)
                        """,
                        (code, now, note),
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
                cursor = conn.execute(
                    "SELECT * FROM invite_codes ORDER BY created_at DESC"
                )
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
