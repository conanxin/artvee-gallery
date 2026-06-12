#!/usr/bin/env python3
"""
Artvee Known-Retired URL Marker
================================

P6B fix: the 4 "unresolved loser" URLs from P4B / P5A have been verified
unreachable via repeated HTTP HEAD probes (30s timeouts, no responses).
They are not blocked from gallery / public demo / digest — they simply
do not appear in the public surface because they were never in
``web/data/artworks.json`` (we only have metadata for what we've
successfully downloaded). They DO show up in runtime reports as
"unresolved" and tend to cause confusion in status reviews.

This helper promotes them to an explicit ``KNOWN_RETIRED`` set so
future reports can split:

- ``known_retired`` = N (audited, not blocking)
- ``blocking_unresolved`` = M (need attention)

The output is a *runtime artifact* under ``reports/runtime/`` and is
NOT meant to be committed to git (it can be regenerated from the
canonical unresolved report at any time).

Safety
------

- Pure local read/write. **No network access.** No retry, no HEAD probe.
- Refuses to overwrite an existing output file unless ``--force`` is given.
- Refuses to write outside the ``reports/runtime/`` directory even
  if ``--out`` is overridden (the suffix is enforced).
- The original unresolved report is NEVER modified.
- dry-run is the default. Use ``--apply`` to write.

Inputs / outputs
----------------

Input (any of these, by ``--input`` path):

- ``reports/runtime/p5a-unresolved-losers.json``
- ``reports/runtime/p4b-unresolved-losers.json``

Both contain a list of dicts with at least ``source_url``. The script
tries to enrich each record by looking up the URL in
``web/data/artworks.json`` (if present) for ``title`` / ``artist`` /
``category`` / ``stable_id`` — this is optional, the script still
works for fully-unknown losers.

Output:

- ``reports/runtime/p6b-known-retired-urls.json`` (default)

Each record has:

- ``source_url``           — the unreachable URL
- ``title``                — best-effort title from web/data (may be null)
- ``artist``               — best-effort artist from web/data (may be null)
- ``category``             — best-effort category from web/data (may be null)
- ``stable_id``            — best-effort stable_id from web/data (may be null)
- ``retired_reason``       — e.g. "P5A HTTP timeout (30s); unreachable"
- ``first_seen_phase``     — derived from input filename (e.g. "P4B", "P5A")
- ``last_checked_phase``   — same as first_seen_phase unless a later
                              report exists (current implementation: same)
- ``status``               — always "known_retired"
- ``should_retry``         — always False
- ``marked_at``            — ISO 8601 timestamp of when this script ran
- ``marker_version``       — this script's __version__ constant
"""
import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

DEFAULT_INPUT = "reports/runtime/p5a-unresolved-losers.json"
DEFAULT_OUTPUT = "reports/runtime/p6b-known-retired-urls.json"
WEB_DATA = Path("web/data/artworks.json")

# For audit / safety: keep output path under reports/runtime/
OUTPUT_RUNTIME_PREFIX = Path("reports/runtime/")


def _detect_phase_from_filename(p: Path) -> str:
    m = re.search(r"(p\d+[a-z]*)(?:-|$)", p.stem, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return "UNKNOWN"


def _load_web_data_index() -> dict:
    """Build a source_url -> record dict from web/data/artworks.json if present.

    The "stable_id" field varies across phases; we try several keys for
    robustness without making this a hard dependency.
    """
    if not WEB_DATA.is_file():
        return {}
    try:
        data = json.loads(WEB_DATA.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict = {}
    if not isinstance(data, list):
        return out
    for r in data:
        if not isinstance(r, dict):
            continue
        url = r.get("source_url")
        if isinstance(url, str) and url:
            out[url] = r
    return out


def _enrich(rec: dict, web_index: dict) -> dict:
    """Map raw unresolved record + web_data lookup to the retired schema."""
    url = rec.get("source_url") or rec.get("url") or ""
    web_match = web_index.get(url, {}) if url else {}

    # Stable id: try common key names
    stable_id = (
        rec.get("stable_id")
        or rec.get("id")
        or web_match.get("stable_id")
        or web_match.get("id")
    )

    return {
        "source_url": url,
        "title": rec.get("title") or web_match.get("title"),
        "artist": rec.get("artist") or web_match.get("artist"),
        "category": rec.get("category") or web_match.get("category"),
        "stable_id": stable_id,
        "retired_reason": _derive_retired_reason(rec),
        "first_seen_phase": rec.get("_phase", "UNKNOWN"),
        "last_checked_phase": rec.get("_phase", "UNKNOWN"),
        "status": "known_retired",
        "should_retry": False,
        "marked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "marker_version": __version__,
    }


def _derive_retired_reason(rec: dict) -> str:
    err = (rec.get("error") or "").strip()
    if not err:
        return "Unreachable after multiple probes (P5A HTTP HEAD, P4B page.goto)"
    # Truncate long playwright stack traces; keep first line.
    first_line = err.splitlines()[0][:200] if err else ""
    return f"Multiple probe failures; first-line error: {first_line}"


def _fallback_input(preferred: Path, repo_root: Path) -> Path:
    """If preferred input does not exist, try the P4B fallback."""
    if preferred.is_file():
        return preferred
    fallback = repo_root / "reports/runtime/p4b-unresolved-losers.json"
    return fallback if fallback.is_file() else preferred


def main():
    ap = argparse.ArgumentParser(
        description="Mark unresolved Artvee URLs as KNOWN_RETIRED (P6B, no network)"
    )
    ap.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"Unresolved report path (default: {DEFAULT_INPUT}; falls back to p4b if missing)",
    )
    ap.add_argument(
        "--out",
        default=DEFAULT_OUTPUT,
        help=f"Output retired manifest path (default: {DEFAULT_OUTPUT}; must be under reports/runtime/)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually write the output file (default is dry-run)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file",
    )
    args = ap.parse_args()

    repo_root = Path.cwd()
    in_path = (repo_root / args.input).resolve()
    out_path = (repo_root / args.out).resolve()

    # Safety: out_path must be under reports/runtime/
    try:
        out_path.relative_to((repo_root / OUTPUT_RUNTIME_PREFIX).resolve())
    except ValueError:
        print(
            f"REFUSE: --out must be under {OUTPUT_RUNTIME_PREFIX}; got {out_path}",
            file=sys.stderr,
        )
        return 2

    # Fallback to P4B if P5A missing
    actual_input = _fallback_input(in_path, repo_root)
    if not actual_input.is_file():
        print(f"ERROR: input not found: {in_path} (and no P4B fallback)", file=sys.stderr)
        return 1

    used_fallback = actual_input != in_path
    if used_fallback:
        print(f"[fallback] {in_path.name} missing → using {actual_input.name}")

    try:
        data = json.loads(actual_input.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: cannot parse {actual_input}: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, list):
        print(f"ERROR: expected list at {actual_input}, got {type(data).__name__}", file=sys.stderr)
        return 1

    phase = _detect_phase_from_filename(actual_input)
    web_index = _load_web_data_index()

    enriched = []
    for rec in data:
        if not isinstance(rec, dict):
            continue
        rec = dict(rec)  # copy
        rec["_phase"] = phase
        enriched.append(_enrich(rec, web_index))

    summary = {
        "generated_by": "scripts/mark_known_retired_urls.py",
        "version": __version__,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "input_path": str(actual_input.relative_to(repo_root)),
        "input_fallback_used": used_fallback,
        "input_count": len(data),
        "output_count": len(enriched),
        "phase": phase,
        "records": enriched,
    }

    if not args.apply:
        print(f"DRY-RUN: would write {len(enriched)} records to {out_path.relative_to(repo_root)}")
        print("  phase:", phase)
        print("  status: known_retired")
        print("  should_retry: False")
        return 0

    if out_path.is_file() and not args.force:
        print(f"REFUSE: {out_path.relative_to(repo_root)} already exists; use --force to overwrite", file=sys.stderr)
        return 3

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out_path)
    print(f"APPLY: wrote {len(enriched)} records to {out_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
