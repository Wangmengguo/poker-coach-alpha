#!/usr/bin/env python3
"""E2E check script for Poker Coach Alpha deployment verification.

IMPORTANT: This script must run on the SAME machine/container as the server,
because it directly accesses the SQLite database for invite code management.

Usage:
    python -m tools.e2e_check [OPTIONS]

Options:
    --base-url URL    Base URL (default: http://localhost:8010/cards)
    --timeout SEC     Per-step timeout in seconds (default: 10)
    --skip-llm        Skip LLM-related tests (for AI_PROVIDER=dummy)
    --skip-ws         Skip WebSocket tests (HTTP-only verification)
    --verbose / -v    Verbose output

Examples:
    # Local development verification
    python -m tools.e2e_check

    # Docker deployment verification (run inside container)
    docker compose exec poker python -m tools.e2e_check

    # Skip LLM and WS tests
    python -m tools.e2e_check --skip-llm --skip-ws
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import httpx

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from poker.invite_codes import InviteCodeStore

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log_step(step: str, status: str, message: str = ""):
    """Log a step with colored status."""
    if status == "ok":
        symbol = f"{GREEN}[OK]{RESET}"
    elif status == "fail":
        symbol = f"{RED}[FAIL]{RESET}"
    elif status == "skip":
        symbol = f"{YELLOW}[SKIP]{RESET}"
    else:
        symbol = f"[{status}]"

    if message:
        print(f"{symbol} {step}: {message}")
    else:
        print(f"{symbol} {step}")


async def _ws_recv_json(ws, *, timeout: float) -> dict:
    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
    if isinstance(msg, (bytes, bytearray)):
        msg = msg.decode("utf-8", errors="replace")
    return json.loads(msg)


async def _ws_wait_for_type(
    ws,
    *,
    want_type: str,
    timeout: float,
    verbose: bool,
    step_name: str,
) -> Optional[dict]:
    """Wait for a specific WS message type, ignoring other messages.

    Returns the message dict on success; None on timeout.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        data = await _ws_recv_json(ws, timeout=remaining)
        if verbose:
            print(f"  WS recv ({step_name}): {data.get('type')}")
        if data.get("type") == want_type:
            return data


async def check_health(base_url: str, timeout: float, verbose: bool) -> bool:
    """Check if the server is reachable."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try root endpoint
            resp = await client.get(f"{base_url}/")
            if verbose:
                print(f"  GET {base_url}/ -> {resp.status_code}")
            if resp.status_code == 200:
                log_step("Health check", "ok", f"Server reachable at {base_url}")
                return True
            else:
                log_step("Health check", "fail", f"Unexpected status: {resp.status_code}")
                return False
    except Exception as e:
        log_step("Health check", "fail", str(e))
        return False


async def check_ai_model_settings(
    base_url: str, timeout: float, verbose: bool
) -> tuple[bool, bool]:
    """Check AI model settings and return (success, llm_available)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base_url}/settings/ai_model")
            if verbose:
                print(f"  GET {base_url}/settings/ai_model -> {resp.status_code}")
                print(f"  Response: {resp.text[:200]}")

            if resp.status_code != 200:
                log_step("AI model settings", "fail", f"Status: {resp.status_code}")
                return False, False

            data = resp.json()
            llm_available = data.get("llm_available", False)
            model_alias = data.get("model_alias", "unknown")

            if llm_available:
                log_step("AI model settings", "ok", f"LLM available, model: {model_alias}")
            else:
                log_step("AI model settings", "ok", f"LLM not configured (dummy provider)")
            return True, llm_available
    except Exception as e:
        log_step("AI model settings", "fail", str(e))
        return False, False


async def check_start_session(base_url: str, timeout: float, verbose: bool) -> bool:
    """Start a session (required before other operations)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try restart first (in case session is already active)
            resp = await client.post(f"{base_url}/tables/default/restart")
            if verbose:
                print(f"  POST {base_url}/tables/default/restart -> {resp.status_code}")

            if resp.status_code == 200:
                log_step("Start session", "ok", "Session started (via restart)")
                return True

            # If restart failed, try start
            resp = await client.post(f"{base_url}/tables/default/start")
            if verbose:
                print(f"  POST {base_url}/tables/default/start -> {resp.status_code}")

            if resp.status_code == 200:
                log_step("Start session", "ok", "Session started")
                return True
            else:
                log_step("Start session", "fail", f"Status: {resp.status_code}")
                return False
    except Exception as e:
        log_step("Start session", "fail", str(e))
        return False


async def check_ws_snapshot(base_url: str, timeout: float, verbose: bool) -> bool:
    """Check WebSocket connection and snapshot."""
    try:
        import websockets
    except ImportError:
        log_step("WS snapshot", "skip", "websockets package not installed")
        return True  # Not a failure, just skip

    # Convert HTTP URL to WebSocket URL
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws/tables/default"

    try:
        async with websockets.connect(ws_url, close_timeout=timeout) as ws:
            data = await _ws_wait_for_type(
                ws,
                want_type="snapshot",
                timeout=timeout,
                verbose=verbose,
                step_name="snapshot",
            )
            if data is None:
                log_step("WS snapshot", "fail", "Timeout waiting for snapshot")
                return False

            table = data.get("table", {})
            players = table.get("players", [])
            log_step("WS snapshot", "ok", f"Received snapshot with {len(players)} players")
            return True
    except Exception as e:
        log_step("WS snapshot", "fail", str(e))
        return False


async def check_ws_invite_validation(
    base_url: str, invite_code: str, timeout: float, verbose: bool
) -> bool:
    """Check WebSocket invite code validation."""
    try:
        import websockets
    except ImportError:
        log_step("WS invite validation", "skip", "websockets package not installed")
        return True

    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws/tables/default"

    try:
        async with websockets.connect(ws_url, close_timeout=timeout) as ws:
            # Wait for initial snapshot (ignore any interleaved analysis/advice)
            snap = await _ws_wait_for_type(
                ws,
                want_type="snapshot",
                timeout=timeout,
                verbose=verbose,
                step_name="invite_validation:initial",
            )
            if snap is None:
                log_step("WS invite validation", "fail", "Timeout waiting for initial snapshot")
                return False

            # Send client_settings with invite code
            settings = {
                "type": "client_settings",
                "llm_enabled": True,
                "invite_code": invite_code,
            }
            await ws.send(json.dumps(settings))
            if verbose:
                print(f"  Sent: {json.dumps(settings)}")

            ack = await _ws_wait_for_type(
                ws,
                want_type="client_settings_ack",
                timeout=timeout,
                verbose=verbose,
                step_name="invite_validation:ack",
            )
            if ack is None:
                log_step("WS invite validation", "fail", "Timeout waiting for client_settings_ack")
                return False

            invite_valid = ack.get("invite_valid", False)
            if invite_valid:
                log_step("WS invite validation", "ok", "Invite code validated")
                return True
            log_step("WS invite validation", "fail", "Invite code rejected")
            return False
    except Exception as e:
        log_step("WS invite validation", "fail", str(e))
        return False


async def check_llm_rest(base_url: str, invite_code: str, timeout: float, verbose: bool) -> bool:
    """Check LLM advice REST endpoint with invite code."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            body = {"seat": 1, "invite_code": invite_code}
            resp = await client.post(
                f"{base_url}/tables/default/ai_advice/llm",
                json=body,
            )
            if verbose:
                print(f"  POST {base_url}/tables/default/ai_advice/llm -> {resp.status_code}")
                print(f"  Response: {resp.text[:300]}")

            if resp.status_code == 200:
                data = resp.json()
                advice = data.get("advice", {})
                if advice.get("recommended_action"):
                    log_step(
                        "LLM REST advice",
                        "ok",
                        f"Got recommendation: {advice['recommended_action']}",
                    )
                    return True
                else:
                    log_step("LLM REST advice", "fail", "No recommended_action in response")
                    return False
            elif resp.status_code == 400:
                data = resp.json()
                if data.get("error") == "llm_not_configured":
                    log_step("LLM REST advice", "skip", "LLM not configured")
                    return True  # Expected for dummy provider
                log_step("LLM REST advice", "fail", f"Error: {data.get('error')}")
                return False
            else:
                log_step("LLM REST advice", "fail", f"Status: {resp.status_code}")
                return False
    except Exception as e:
        log_step("LLM REST advice", "fail", str(e))
        return False


async def check_llm_without_invite(base_url: str, timeout: float, verbose: bool) -> bool:
    """Check that LLM advice fails without invite code."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            body = {"seat": 1}  # No invite_code
            resp = await client.post(
                f"{base_url}/tables/default/ai_advice/llm",
                json=body,
            )
            if verbose:
                print(f"  POST without invite -> {resp.status_code}")

            if resp.status_code == 403:
                data = resp.json()
                if data.get("error") == "invite_code_required":
                    log_step("LLM without invite", "ok", "Correctly rejected (403)")
                    return True
            elif resp.status_code == 400:
                # llm_not_configured is also acceptable
                data = resp.json()
                if data.get("error") == "llm_not_configured":
                    log_step("LLM without invite", "ok", "LLM not configured (skip check)")
                    return True

            log_step("LLM without invite", "fail", f"Expected 403, got {resp.status_code}")
            return False
    except Exception as e:
        log_step("LLM without invite", "fail", str(e))
        return False


async def check_revoke_invalidates(
    base_url: str, invite_code: str, store: InviteCodeStore, timeout: float, verbose: bool
) -> bool:
    """Check that revoking an invite code invalidates it."""
    # Revoke the code
    revoked = store.revoke_code(invite_code)
    if not revoked:
        log_step("Revoke invite", "fail", "Failed to revoke code")
        return False

    if verbose:
        print(f"  Revoked invite code: {invite_code}")

    # Try to use revoked code
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            body = {"seat": 1, "invite_code": invite_code}
            resp = await client.post(
                f"{base_url}/tables/default/ai_advice/llm",
                json=body,
            )
            if verbose:
                print(f"  POST with revoked invite -> {resp.status_code}")

            if resp.status_code == 403:
                data = resp.json()
                if data.get("error") == "invite_code_required":
                    log_step("Revoke invalidates", "ok", "Revoked code correctly rejected")
                    return True
            elif resp.status_code == 400:
                data = resp.json()
                if data.get("error") == "llm_not_configured":
                    log_step("Revoke invalidates", "ok", "LLM not configured (skip check)")
                    return True

            log_step("Revoke invalidates", "fail", f"Expected 403, got {resp.status_code}")
            return False
    except Exception as e:
        log_step("Revoke invalidates", "fail", str(e))
        return False


async def main(args: argparse.Namespace) -> int:
    """Run E2E checks."""
    base_url = args.base_url.rstrip("/")
    timeout = args.timeout
    verbose = args.verbose
    skip_llm = args.skip_llm
    skip_ws = args.skip_ws

    print(f"\n{BOLD}Poker Coach Alpha - E2E Check{RESET}")
    print(f"Base URL: {base_url}")
    print(f"Timeout: {timeout}s")
    print()

    all_passed = True
    invite_code: Optional[str] = None
    store: Optional[InviteCodeStore] = None

    try:
        # 1. Health check
        if not await check_health(base_url, timeout, verbose):
            all_passed = False

        # 2. AI model settings
        settings_ok, llm_available = await check_ai_model_settings(base_url, timeout, verbose)
        if not settings_ok:
            all_passed = False

        # 3. Create test invite code
        try:
            store = InviteCodeStore()
            invite_code = store.create_code(note="e2e_check_test")
            log_step("Create invite code", "ok", invite_code)
        except Exception as e:
            log_step("Create invite code", "fail", str(e))
            all_passed = False
            invite_code = None

        # 4. Start session
        if not await check_start_session(base_url, timeout, verbose):
            all_passed = False

        # 5. WebSocket tests
        if skip_ws:
            log_step("WS snapshot", "skip", "Skipped by --skip-ws")
            log_step("WS invite validation", "skip", "Skipped by --skip-ws")
        else:
            if not await check_ws_snapshot(base_url, timeout, verbose):
                all_passed = False

            if invite_code:
                if not await check_ws_invite_validation(base_url, invite_code, timeout, verbose):
                    all_passed = False

        # 6. LLM tests
        if skip_llm:
            log_step("LLM REST advice", "skip", "Skipped by --skip-llm")
            log_step("LLM without invite", "skip", "Skipped by --skip-llm")
        else:
            # Check without invite first
            if not await check_llm_without_invite(base_url, timeout, verbose):
                all_passed = False

            # Check with invite
            if invite_code:
                if not await check_llm_rest(base_url, invite_code, timeout, verbose):
                    all_passed = False

        # 7. Revocation test
        if invite_code and store and not skip_llm:
            if not await check_revoke_invalidates(base_url, invite_code, store, timeout, verbose):
                all_passed = False
            invite_code = None  # Already revoked

    finally:
        # Cleanup: revoke test invite code if still exists
        if invite_code and store:
            try:
                store.revoke_code(invite_code)
                if verbose:
                    print(f"  Cleaned up invite code: {invite_code}")
            except Exception:
                pass

    # Summary
    print()
    if all_passed:
        print(f"{GREEN}{BOLD}All checks passed!{RESET}")
        return 0
    else:
        print(f"{RED}{BOLD}Some checks failed.{RESET}")
        return 1


def cli():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="E2E check script for Poker Coach Alpha deployment verification.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8010/cards",
        help="Base URL of the server (default: http://localhost:8010/cards)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-step timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM-related tests",
    )
    parser.add_argument(
        "--skip-ws",
        action="store_true",
        help="Skip WebSocket tests",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()
    return asyncio.run(main(args))


if __name__ == "__main__":
    sys.exit(cli())
