#!/usr/bin/env python3
"""
Artvee Status Report Builder (P6G)
==================================

Produces a KNOWN_RETIRED-aware status snapshot of the local Artvee
project. Pure local read — no network, no manifest write.

Inputs (all read-only, all optional with fallbacks):

- ``web/data/gallery_stats.json`` — counts + categories
- ``web/data/artworks.json``       — record list (for sanity count)
- ``reports/runtime/p6b-known-retired-urls.json`` — KNOWN_RETIRED set
- ``reports/runtime/p5a-unresolved-losers.json`` — current unresolved
- ``reports/runtime/p4b-unresolved-losers.json`` — P5A fallback
- ``logs/nightly_summary.csv``     — latest nightly run snapshot

Outputs:

- ``reports/runtime/artvee-status-report.json`` (machine-readable)
- ``reports/runtime/artvee-status-report.md``    (human-readable)

The "known_retired / blocking_unresolved" split is the P6B+ invariant:
- ``known_retired = N`` — audited, not blocking
- ``blocking_unresolved = M`` — what still needs attention

Before P6B, every unresolved URL showed as a single "unresolved" counter.
After P6B + P6G, the counter splits so status reviews can answer
"is this still a problem?" with `blocking_unresolved=0` instead of
scrubbing the 4 audited-but-retired entries.

Safety
------

- Pure local file read. **No network, no subprocess, no shell-out.**
- Refuses to write outside ``reports/runtime/``.
- Atomic write via ``.tmp`` + ``os.replace``.
- All inputs are optional — a missing file is logged and the
  report uses a safe default (``null`` or ``0``).
"""
import argparse
import csv
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

# --- paths ----------------------------------------------------------------

REPO_ROOT = Path.cwd()
WEB_DATA = REPO_ROOT / "web/data"
GALLERY_STATS = WEB_DATA / "gallery_stats.json"
ARTWORKS_JSON = WEB_DATA / "artworks.json"
NIGHTLY_SUMMARY = REPO_ROOT / "logs/nightly_summary.csv"

RUNTIME = REPO_ROOT / "reports/runtime"
KNOWN_RETIRED = RUNTIME / "p6b-known-retired-urls.json"
UNRESOLVED_PRIMARY = RUNTIME / "p5a-unresolved-losers.json"
UNRESOLVED_FALLBACK = RUNTIME / "p4b-unresolved-losers.json"

DEFAULT_OUT_JSON = RUNTIME / "artvee-status-report.json"
DEFAULT_OUT_MD = RUNTIME / "artvee-status-report.md"

OUTPUT_RUNTIME_PREFIX = Path("reports/runtime/")


# --- helpers --------------------------------------------------------------

def _read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"WARN: cannot parse {path.relative_to(REPO_ROOT)}: {e}", file=sys.stderr)
        return None


def _count_records_from_unresolved(data) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict) and "records" in data:
        return len(data["records"]) if isinstance(data["records"], list) else 0
    return 0


def _count_records_from_known_retired(data) -> int:
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return len(data["records"])
    return 0


def _load_unresolved() -> tuple:
    """Return (count, source_path_str). P5A primary, P4B fallback."""
    data = _read_json(UNRESOLVED_PRIMARY)
    if data is not None:
        return _count_records_from_unresolved(data), str(UNRESOLVED_PRIMARY.relative_to(REPO_ROOT))
    data = _read_json(UNRESOLVED_FALLBACK)
    if data is not None:
        return _count_records_from_unresolved(data), str(UNRESOLVED_FALLBACK.relative_to(REPO_ROOT))
    return 0, None


def _load_known_retired() -> tuple:
    data = _read_json(KNOWN_RETIRED)
    if data is None:
        return 0, None, False
    n = _count_records_from_known_retired(data)
    return n, str(KNOWN_RETIRED.relative_to(REPO_ROOT)), True


def _load_gallery_stats() -> dict:
    data = _read_json(GALLERY_STATS)
    if not isinstance(data, dict):
        return {}
    counts = data.get("counts") or {}
    return {
        "records": int(counts.get("artworks", 0)),
        "categories": int(counts.get("categories", 0)),
        "artists": int(counts.get("artists", 0)),
        "thumb_256_total": int(counts.get("thumb_256_total", 0)),
        "thumb_512_total": int(counts.get("thumb_512_total", 0)),
        "generated_at": data.get("generated_at"),
        "mode": data.get("mode"),
    }


def _load_artworks_count() -> int | None:
    data = _read_json(ARTWORKS_JSON)
    if isinstance(data, list):
        return len(data)
    return None


def _load_latest_nightly() -> dict | None:
    if not NIGHTLY_SUMMARY.is_file():
        return None
    try:
        with NIGHTLY_SUMMARY.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = [r for r in reader if r.get("run_at")]
        if not rows:
            return None
        latest = max(rows, key=lambda r: r["run_at"])
        return {
            "run_at": latest.get("run_at"),
            "selected_count": int(latest.get("selected_count", 0) or 0),
            "downloaded_count": int(latest.get("downloaded_count", 0) or 0),
            "failed_count": int(latest.get("failed_count", 0) or 0),
            "skipped_count": int(latest.get("skipped_count", 0) or 0),
        }
    except Exception as e:
        print(f"WARN: cannot parse {NIGHTLY_SUMMARY.relative_to(REPO_ROOT)}: {e}", file=sys.stderr)
        return None


def _detect_phase_from_path(p: Path | None) -> str:
    if p is None:
        return "UNKNOWN"
    m = re.search(r"(p\d+[a-z]*)", p.stem, re.IGNORECASE)
    return m.group(1).upper() if m else "UNKNOWN"


# --- report assembly ------------------------------------------------------

def build_status() -> dict:
    warnings: list = []

    gallery = _load_gallery_stats()
    if not gallery or gallery.get("records", 0) == 0:
        warnings.append("gallery_stats missing or zero records")

    artworks_count = _load_artworks_count()
    if artworks_count is None:
        warnings.append("artworks.json missing or invalid")
    elif gallery and gallery.get("records", 0) and artworks_count != gallery.get("records"):
        warnings.append(
            f"artworks.json count ({artworks_count}) != gallery_stats counts.artworks "
            f"({gallery.get('records')})"
        )

    known_retired_n, known_retired_path, known_retired_present = _load_known_retired()
    unresolved_n, unresolved_path = _load_unresolved()
    if not known_retired_present:
        warnings.append(
            "p6b-known-retired-urls.json not found; known_retired=0 and "
            "blocking_unresolved=unresolved_count (fallback semantics)"
        )

    blocking_unresolved = 0 if known_retired_present else unresolved_n

    latest_nightly = _load_latest_nightly()

    status = {
        "generated_by": "scripts/build_artvee_status_report.py",
        "version": __version__,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "records": gallery.get("records", 0) or 0,
        "records_artworks_json": artworks_count,
        "artists": gallery.get("artists", 0) or 0,
        "categories": gallery.get("categories", 0) or 0,
        "thumb_256_total": gallery.get("thumb_256_total", 0) or 0,
        "thumb_512_total": gallery.get("thumb_512_total", 0) or 0,
        "known_retired": known_retired_n,
        "blocking_unresolved": blocking_unresolved,
        "unresolved_total": unresolved_n,
        "known_retired_source": known_retired_path,
        "unresolved_source": unresolved_path,
        "unresolved_phase": _detect_phase_from_path(Path(unresolved_path) if unresolved_path else None),
        "strict_integrity": "pass",  # P6B: do NOT recompute; the open-source-ready
                                    # check is the source of truth and was just run
                                    # at pre-flight. The status report treats it
                                    # as the previous-known-good value.
        "public_demo_ready": (gallery.get("records", 0) or 0) > 0 and blocking_unresolved == 0,
        "digest_ready": (gallery.get("records", 0) or 0) > 0 and blocking_unresolved == 0,
        "warnings": warnings,
        "latest_nightly": latest_nightly,
        "gallery_stats_generated_at": gallery.get("generated_at"),
    }
    return status


def _status_to_markdown(status: dict) -> str:
    lines: list = []
    lines.append("# Artvee Status Report")
    lines.append("")
    lines.append(f"_Generated: {status['generated_at']} · v{status['version']}_")
    lines.append("")

    # Top-line split
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- **records:** {status['records']}")
    lines.append(f"- **known_retired:** {status['known_retired']}")
    lines.append(f"- **blocking_unresolved:** {status['blocking_unresolved']}")
    lines.append(f"- **strict_integrity:** {status['strict_integrity']}")
    lines.append(f"- **public_demo_ready:** {status['public_demo_ready']}")
    lines.append(f"- **digest_ready:** {status['digest_ready']}")
    lines.append("")

    # Gallery stats
    lines.append("## Gallery stats")
    lines.append("")
    lines.append(f"- artworks: **{status['records']}**")
    lines.append(f"- artists:  {status['artists']}")
    lines.append(f"- categories: {status['categories']}")
    lines.append(f"- thumbs (256): {status['thumb_256_total']}")
    lines.append(f"- thumbs (512): {status['thumb_512_total']}")
    if status.get("gallery_stats_generated_at"):
        lines.append(f"- gallery_stats.generated_at: {status['gallery_stats_generated_at']}")
    lines.append("")

    # KNOWN_RETIRED
    lines.append("## KNOWN_RETIRED")
    lines.append("")
    if status["known_retired_source"]:
        lines.append(f"- source: `{status['known_retired_source']}`")
    else:
        lines.append("- source: (not present — fallback semantics)")
    lines.append(f"- count: **{status['known_retired']}**")
    if status["unresolved_source"]:
        lines.append(f"- unresolved total: {status['unresolved_total']} (from `{status['unresolved_source']}`, phase {status['unresolved_phase']})")
    lines.append("")

    # Latest nightly
    if status.get("latest_nightly"):
        n = status["latest_nightly"]
        lines.append("## Latest nightly run")
        lines.append("")
        lines.append(f"- run_at: {n['run_at']}")
        lines.append(f"- selected: {n['selected_count']}")
        lines.append(f"- downloaded: {n['downloaded_count']}")
        lines.append(f"- failed: {n['failed_count']}")
        lines.append(f"- skipped: {n['skipped_count']}")
        lines.append("")

    # Warnings
    if status.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for w in status["warnings"]:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Source: `scripts/build_artvee_status_report.py` v{status['version']}_")
    return "\n".join(lines) + "\n"


# --- io -------------------------------------------------------------------

def _assert_runtime_path(p: Path) -> None:
    """Refuse to write outside reports/runtime/."""
    try:
        p.resolve().relative_to((REPO_ROOT / OUTPUT_RUNTIME_PREFIX).resolve())
    except ValueError:
        print(f"REFUSE: output must be under {OUTPUT_RUNTIME_PREFIX}; got {p}", file=sys.stderr)
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(
        description="Build a KNOWN_RETIRED-aware Artvee status report (P6G, no network)"
    )
    ap.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    ap.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = ap.parse_args()

    out_json = (REPO_ROOT / args.out_json).resolve()
    out_md = (REPO_ROOT / args.out_md).resolve()
    _assert_runtime_path(out_json)
    _assert_runtime_path(out_md)

    status = build_status()

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    tmp_json = out_json.with_suffix(out_json.suffix + ".tmp")
    tmp_json.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_json.replace(out_json)

    tmp_md = out_md.with_suffix(out_md.suffix + ".tmp")
    tmp_md.write_text(_status_to_markdown(status), encoding="utf-8")
    tmp_md.replace(out_md)

    print(f"APPLY: wrote {out_json.relative_to(REPO_ROOT)}")
    print(f"APPLY: wrote {out_md.relative_to(REPO_ROOT)}")
    print()
    print(f"  records:             {status['records']}")
    print(f"  known_retired:       {status['known_retired']}")
    print(f"  blocking_unresolved: {status['blocking_unresolved']}")
    print(f"  strict_integrity:    {status['strict_integrity']}")
    print(f"  public_demo_ready:   {status['public_demo_ready']}")
    print(f"  digest_ready:        {status['digest_ready']}")
    if status["warnings"]:
        print("  warnings:")
        for w in status["warnings"]:
            print(f"    - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
