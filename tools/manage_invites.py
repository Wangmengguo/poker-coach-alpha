#!/usr/bin/env python3
"""CLI tool for managing invite codes.

Usage:
    python -m tools.manage_invites create [--note "description"]
    python -m tools.manage_invites list [--active-only]
    python -m tools.manage_invites revoke <CODE>
    python -m tools.manage_invites check <CODE>

Examples:
    python -m tools.manage_invites create --note "For friend A"
    python -m tools.manage_invites list
    python -m tools.manage_invites revoke POKER-ABC123
    python -m tools.manage_invites check POKER-ABC123
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from poker.invite_codes import InviteCodeStore


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new invite code."""
    store = InviteCodeStore()
    allowed_models = None
    if args.models:
        allowed_models = [part.strip() for part in args.models.split(",") if part.strip()]
    code = store.create_code(
        note=args.note,
        expires_at=args.expires_at,
        max_uses=args.max_uses,
        daily_quota=args.daily_quota,
        allowed_model_aliases=allowed_models,
    )
    print(f"Created invite code: {code}")
    if args.note:
        print(f"Note: {args.note}")
    if args.expires_at:
        print(f"Expires: {args.expires_at}")
    if args.max_uses is not None:
        print(f"Max uses: {args.max_uses}")
    if args.daily_quota is not None:
        print(f"Daily quota: {args.daily_quota}")
    if allowed_models:
        print(f"Models: {', '.join(allowed_models)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all invite codes."""
    store = InviteCodeStore()
    codes = store.list_codes(include_revoked=not args.active_only)

    if not codes:
        print("No invite codes found.")
        return 0

    # Header
    print(
        f"{'CODE':<16} {'STATUS':<10} {'USES':<9} {'DAILY':<9} "
        f"{'EXPIRES':<20} {'LAST USED':<20} {'MODELS':<20} {'NOTE'}"
    )
    print("-" * 125)

    for c in codes:
        status = "active" if c["is_active"] else "REVOKED"
        max_uses = c.get("max_uses")
        uses = f"{c.get('use_count', 0)}/{max_uses if max_uses is not None else '-'}"
        daily_quota = c.get("daily_quota")
        daily = f"{c.get('daily_use_count', 0)}/{daily_quota if daily_quota is not None else '-'}"
        expires = c.get("expires_at", "")[:19] if c.get("expires_at") else "-"
        last_used = c["last_used_at"][:19] if c["last_used_at"] else "-"
        models = c.get("allowed_model_aliases") or "-"
        note = c["note"] or "-"
        print(
            f"{c['code']:<16} {status:<10} {uses:<9} {daily:<9} "
            f"{expires:<20} {last_used:<20} {models:<20} {note}"
        )

    print(f"\nTotal: {len(codes)} code(s)")
    active_count = sum(1 for c in codes if c["is_active"])
    print(f"Active: {active_count}, Revoked: {len(codes) - active_count}")
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    """Revoke an invite code."""
    store = InviteCodeStore()
    code = args.code.strip().upper()

    if store.revoke_code(code):
        print(f"Revoked: {code}")
        return 0
    else:
        print(f"Code not found: {code}")
        return 1


def cmd_check(args: argparse.Namespace) -> int:
    """Check if an invite code is valid."""
    store = InviteCodeStore()
    code = args.code.strip().upper()

    # Validate first (updates last_used_at on success)
    is_valid = store.validate_code(code)

    info = store.get_code(code)
    if info is None:
        print(f"Code not found: {code}")
        return 1

    print(f"Code: {info['code']}")
    print(f"Status: {'active' if info['is_active'] else 'REVOKED'}")
    print(f"Created: {info['created_at']}")
    print(f"Last used: {info['last_used_at'] or 'never'}")
    print(f"Expires: {info.get('expires_at') or '-'}")
    print(f"Uses: {info.get('use_count', 0)}/{info.get('max_uses') or '-'}")
    print(f"Daily uses: {info.get('daily_use_count', 0)}/{info.get('daily_quota') or '-'}")
    print(f"Models: {info.get('allowed_model_aliases') or '-'}")
    print(f"Session: {info.get('session_id') or '-'}")
    print(f"Note: {info['note'] or '-'}")

    if is_valid:
        print("\n[OK] This code is valid and can be used.")
        return 0
    print("\n[WARN] This code is not valid (missing or revoked).")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage invite codes for Poker Coach Alpha",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = subparsers.add_parser("create", help="Create a new invite code")
    p_create.add_argument("--note", "-n", help="Optional note/description")
    p_create.add_argument("--expires-at", help="ISO datetime, e.g. 2026-05-01T00:00:00+00:00")
    p_create.add_argument("--max-uses", type=int, help="Maximum total LLM calls")
    p_create.add_argument("--daily-quota", type=int, help="Maximum LLM calls per UTC day")
    p_create.add_argument(
        "--models",
        help="Comma-separated allowed model aliases/tiers, e.g. fast,balanced",
    )
    p_create.set_defaults(func=cmd_create)

    # list
    p_list = subparsers.add_parser("list", help="List all invite codes")
    p_list.add_argument(
        "--active-only", "-a", action="store_true", help="Only show active codes"
    )
    p_list.set_defaults(func=cmd_list)

    # revoke
    p_revoke = subparsers.add_parser("revoke", help="Revoke an invite code")
    p_revoke.add_argument("code", help="The invite code to revoke")
    p_revoke.set_defaults(func=cmd_revoke)

    # check
    p_check = subparsers.add_parser("check", help="Check if an invite code is valid")
    p_check.add_argument("code", help="The invite code to check")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
