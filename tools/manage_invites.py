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
    code = store.create_code(note=args.note)
    print(f"Created invite code: {code}")
    if args.note:
        print(f"Note: {args.note}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all invite codes."""
    store = InviteCodeStore()
    codes = store.list_codes(include_revoked=not args.active_only)

    if not codes:
        print("No invite codes found.")
        return 0

    # Header
    print(f"{'CODE':<16} {'STATUS':<10} {'CREATED':<20} {'LAST USED':<20} {'NOTE'}")
    print("-" * 90)

    for c in codes:
        status = "active" if c["is_active"] else "REVOKED"
        created = c["created_at"][:19] if c["created_at"] else "-"
        last_used = c["last_used_at"][:19] if c["last_used_at"] else "-"
        note = c["note"] or "-"
        print(f"{c['code']:<16} {status:<10} {created:<20} {last_used:<20} {note}")

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
