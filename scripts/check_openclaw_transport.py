#!/usr/bin/env python3
"""
Artvee Gallery · OpenClaw Transport Health Check (P7B+3)
========================================================
Cheap, side-effect-free probe of the OpenClaw gateway transport.

Why this exists
---------------
The Artvee daily-health pipeline occasionally hits
``OpenClaw transport timeout`` errors when the gateway's HTTP / WS
endpoint is overloaded or briefly restarting. Before declaring MEDIA
"deferred", we want a way to ask the gateway ``are you alive?`` without
sending a real Telegram message (which would burn budget on a probe).

This script:
1. Resolves the OpenClaw binary (CLI flag > env vars > PATH).
2. Runs ``openclaw --version`` as a low-cost liveness probe.
3. If ``--extended`` is given, also runs ``openclaw browser status``
   which is a read-only WS / in-process RPC probe (no message send).
4. Optionally probes the local gateway HTTP port (default 18789) with
   a short TCP connect (no payload, no auth, no message).

It NEVER sends a Telegram message, NEVER reads / writes gallery data,
and NEVER modifies any pending files. Output is structured JSON so
``artvee_daily_health_check.py`` can embed it in its report.

Usage
-----
::

    # JSON only
    python3 scripts/check_openclaw_transport.py

    # JSON + run the extended browser probe
    python3 scripts/check_openclaw_transport.py --extended

    # Custom binary, custom gateway port, human-readable text
    python3 scripts/check_openclaw_transport.py --openclaw-bin /usr/local/bin/openclaw \\
        --gateway-port 18789 --text
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Same resolver the notifier uses, so probes are aligned with the
# real call path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from artvee_telegram_notify import _resolve_openclaw_bin  # noqa: E402

DEFAULT_GATEWAY_PORT = 18789
PROBE_TIMEOUT_SECONDS = 4.0


def _resolve_binary(cli_path: str | None) -> tuple[str | None, str]:
    """Return (resolved_path, source). source is one of:
    cli | env:ARTVEE_OPENCLAW_BIN | env:OPENCLAW_BIN | path | None.
    Never includes any secret.
    """
    if cli_path:
        return cli_path, "cli"
    artvee = os.environ.get("ARTVEE_OPENCLAW_BIN", "").strip()
    if artvee and (Path(artvee).is_file() or shutil.which(artvee)):
        return artvee, "env:ARTVEE_OPENCLAW_BIN"
    plain = os.environ.get("OPENCLAW_BIN", "").strip()
    if plain and (Path(plain).is_file() or shutil.which(plain)):
        return plain, "env:OPENCLAW_BIN"
    which = shutil.which("openclaw")
    if which:
        return which, "path"
    return None, "missing"


def _run(cmd: list[str], timeout: float) -> tuple[int, str, str, int]:
    """Run a subprocess; return (returncode, stdout, stderr, elapsed_ms)."""
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = int((time.time() - t0) * 1000)
        return result.returncode, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired as e:
        elapsed = int((time.time() - t0) * 1000)
        out = (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return 124, out, err, elapsed
    except FileNotFoundError as e:
        elapsed = int((time.time() - t0) * 1000)
        return 127, "", f"binary not found: {e}", elapsed


def _probe_tcp(host: str, port: int, timeout: float) -> tuple[bool, int, str]:
    """Non-payload TCP connect probe. Returns (ok, elapsed_ms, error)."""
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, int((time.time() - t0) * 1000), ""
    except socket.timeout:
        return False, int((time.time() - t0) * 1000), f"timeout after {timeout}s"
    except ConnectionRefusedError as e:
        return False, int((time.time() - t0) * 1000), f"connection refused: {e}"
    except OSError as e:
        return False, int((time.time() - t0) * 1000), f"{type(e).__name__}: {e}"


def _classify(returncode: int, stdout: str, stderr: str) -> tuple[str, str]:
    """Map a probe result to (status, error_class)."""
    if returncode == 0:
        return "ok", ""
    if returncode == 124:
        return "timeout", "subprocess_timeout"
    if returncode == 127:
        return "missing", "binary_not_found"
    if returncode in (1, 2):
        # openclaw uses 1/2 for CLI/usage errors. Try to classify from output.
        text = (stderr or stdout or "").lower()
        if "auth" in text or "unauthorized" in text or "token" in text:
            return "error", "auth_error"
        if "connection" in text or "transport" in text or "econn" in text:
            return "error", "transport_error"
        return "error", f"exit_{returncode}"
    return "error", f"exit_{returncode}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--openclaw-bin", default=None,
                        help="Path or command name for the OpenClaw binary (overrides env vars)")
    parser.add_argument("--gateway-port", type=int, default=DEFAULT_GATEWAY_PORT,
                        help=f"Local gateway TCP port to probe (default: {DEFAULT_GATEWAY_PORT})")
    parser.add_argument("--gateway-host", default="127.0.0.1",
                        help="Local gateway host to probe (default: 127.0.0.1)")
    parser.add_argument("--timeout", type=float, default=PROBE_TIMEOUT_SECONDS,
                        help=f"Per-probe timeout in seconds (default: {PROBE_TIMEOUT_SECONDS})")
    parser.add_argument("--extended", action="store_true",
                        help="Also run the (read-only) openclaw browser status probe")
    parser.add_argument("--text", action="store_true",
                        help="Print a human-readable summary in addition to the JSON envelope")
    args = parser.parse_args()

    # Reuse the notifier's resolver first (so we match the production
    # call path); fall back to our local resolver if it fails.
    resolved = None
    try:
        resolved = _resolve_openclaw_bin(args.openclaw_bin)
    except Exception:
        pass
    if not resolved:
        resolved, source = _resolve_binary(args.openclaw_bin)
    else:
        source = "notifier:resolve"

    payload: dict[str, Any] = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "binary": {
            "resolved": resolved,
            "source": source,
        },
        "probes": {},
    }

    # Probe 1: --version (always)
    if resolved and (Path(resolved).is_file() or shutil.which(resolved)):
        rc, out, err, elapsed = _run([resolved, "--version"], args.timeout)
        status, error_class = _classify(rc, out, err)
        payload["probes"]["version"] = {
            "status": status,
            "error_class": error_class,
            "returncode": rc,
            "elapsed_ms": elapsed,
            # Don't print full stdout/stderr (could include version banners
            # referencing internal paths); keep a short preview only.
            "stdout_preview": (out or "")[:200].strip(),
        }
    else:
        payload["probes"]["version"] = {
            "status": "missing",
            "error_class": "binary_not_found",
            "returncode": None,
            "elapsed_ms": 0,
            "stdout_preview": "",
        }

    # Probe 2: local gateway TCP connect
    tcp_ok, tcp_ms, tcp_err = _probe_tcp(args.gateway_host, args.gateway_port, args.timeout)
    payload["probes"]["gateway_tcp"] = {
        "status": "ok" if tcp_ok else "error",
        "error_class": "" if tcp_ok else "tcp_connect_failed",
        "elapsed_ms": tcp_ms,
        "host": args.gateway_host,
        "port": args.gateway_port,
        "error": tcp_err,
    }

    # Probe 3 (optional, --extended): browser status (read-only RPC).
    if args.extended and resolved and (Path(resolved).is_file() or shutil.which(resolved)):
        rc, out, err, elapsed = _run([resolved, "browser", "status"], args.timeout)
        status, error_class = _classify(rc, out, err)
        payload["probes"]["browser_status"] = {
            "status": status,
            "error_class": error_class,
            "returncode": rc,
            "elapsed_ms": elapsed,
            "stdout_preview": (out or "")[:200].strip(),
        }

    # Aggregate
    statuses = [p.get("status") for p in payload["probes"].values()]
    if all(s == "ok" for s in statuses):
        payload["status"] = "ok"
    elif "missing" in statuses:
        payload["status"] = "missing"
    elif "timeout" in statuses:
        payload["status"] = "timeout"
    else:
        payload["status"] = "error"

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.text:
        summary = (
            f"\n=== OpenClaw transport check ===\n"
            f"binary   : {payload['binary']['resolved']} ({payload['binary']['source']})\n"
            f"status   : {payload['status']}\n"
            f"version  : {payload['probes'].get('version', {}).get('status', '?')} "
            f"({payload['probes'].get('version', {}).get('elapsed_ms', '?')}ms)\n"
            f"tcp:{args.gateway_port}     : {payload['probes']['gateway_tcp']['status']} "
            f"({payload['probes']['gateway_tcp']['elapsed_ms']}ms)\n"
        )
        if "browser_status" in payload["probes"]:
            summary += (
                f"browser  : {payload['probes']['browser_status']['status']} "
                f"({payload['probes']['browser_status']['elapsed_ms']}ms)\n"
            )
        print(summary, file=sys.stderr)

    # Exit 0 if ok, 1 if error, 2 if missing.
    return {"ok": 0, "error": 1, "missing": 2, "timeout": 1}.get(payload["status"], 1)


if __name__ == "__main__":
    sys.exit(main())
