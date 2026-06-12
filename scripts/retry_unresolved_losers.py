#!/usr/bin/env python3
"""Retry unresolved losers from P4B (P5A content healing).

Lightweight version: uses direct HTTP fetch (no playwright browser)
to avoid the 30-90s timeout hangs that blocked P4B.

Reads reports/runtime/p4b-unresolved-losers.json, attempts
a quick HTTP check for each URL, and writes new reports.

Does NOT modify pending queue, does NOT run full batch/refill.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import urllib.request
import urllib.error

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "runtime"
P4B_UNRESOLVED = REPORTS_DIR / "p4b-unresolved-losers.json"
P5A_RESOLVED = REPORTS_DIR / "p5a-resolved-losers.json"
P5A_UNRESOLVED = REPORTS_DIR / "p5a-unresolved-losers.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (ArtveeGallery/1.0)"}

def http_check(url: str, timeout: int = 15) -> tuple[bool, int, str]:
    """Return (reachable, status_code, error_or_empty)."""
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status, ""
    except urllib.error.HTTPError as e:
        # 404 means page is gone (not a timeout)
        return False, e.code, str(e)
    except Exception as e:
        return False, 0, str(e)


def load_p4b_unresolved() -> list[dict[str, Any]]:
    if not P4B_UNRESOLVED.exists():
        return []
    return json.loads(P4B_UNRESOLVED.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry P4B unresolved losers (lightweight)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan, don't fetch")
    args = parser.parse_args()

    unresolved = load_p4b_unresolved()
    if not unresolved:
        print("No P4B unresolved losers found.")
        return 0

    print(f"[*] P4B unresolved losers: {len(unresolved)}")
    for i, item in enumerate(unresolved, 1):
        print(f"  {i}. {item.get('source_url', 'N/A')}")

    if args.dry_run:
        print("\n(dry-run) would HTTP-check each with 15s timeout")
        return 0

    resolved: list[dict[str, Any]] = []
    still_unresolved: list[dict[str, Any]] = []

    for i, item in enumerate(unresolved, start=1):
        src = item.get("source_url", "")
        print(f"\n== [{i}/{len(unresolved)}] Checking {src} ==")

        reachable, code, err = http_check(src, timeout=15)
        if reachable:
            # Page is reachable but we don't re-download (too slow/risky)
            # Just record that it's reachable now
            resolved.append({
                **item,
                "p5a_reachable": True,
                "p5a_http_status": code,
                "p5a_checked_at": datetime.now().isoformat(timespec="seconds"),
                "p5a_strategy": "http_head_15s",
                "p5a_note": "page reachable but not re-downloaded in P5A (deferred to user manual download)",
            })
            print(f"  ✅ REACHABLE (status {code}) — deferred to manual download")
        else:
            still_unresolved.append({
                **item,
                "p5a_reachable": False,
                "p5a_http_status": code,
                "p5a_error": err,
                "p5a_checked_at": datetime.now().isoformat(timespec="seconds"),
                "p5a_strategy": "http_head_15s",
            })
            print(f"  ❌ UNREACHABLE (status {code}) — {err[:80]}")
        time.sleep(1)  # be polite

    # Write reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    P5A_RESOLVED.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    P5A_UNRESOLVED.write_text(
        json.dumps(still_unresolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\n[*] Results: {len(resolved)} reachable, {len(still_unresolved)} still unreachable")
    print(f"  written: {P5A_RESOLVED}")
    print(f"  written: {P5A_UNRESOLVED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
