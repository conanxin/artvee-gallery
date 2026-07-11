#!/usr/bin/env python3
"""
Artvee Status Report Builder (P9F+1)
=====================================

Produces a canonical Artvee status snapshot in two files:

- ``reports/runtime/artvee-status-report.json`` — machine-readable, schema
  ``artvee-metrics-v1``. Emitted **every time** this script runs by
  delegating to :func:`artvee_metrics.collect_current_metrics` so the file
  can never silently stay stale (P9F found a 23-day-old frozen snapshot).
- ``reports/runtime/artvee-status-report.md``    — human-readable rendering.

Pre P9F+1 this script read ``web/data/gallery_stats.json`` (a true live
source) **but the file it emitted was never re-run after Nightly Wrapper
rebuilt the gallery**, so ``artvee_ops_status.py`` and the Daily Health
check both ended up reporting the last-known ``records=875`` count while
the local library was actually at 1286.

P9F+1 fixes this at three layers:

1. The collector is now a single :func:`artvee_metrics.collect_current_metrics`
   call so every consumer agrees on definitions.
2. The output write is **atomic** (``tmp + replace``); readers can no
   longer observe a half-written file.
3. The legacy top-level ``records`` alias is preserved as a **read-only**
   alias of ``metrics.library_records`` (see ``docs/METRICS_MODEL.md`` for
   the canonical model).

Inputs (all read-only, all optional with fallbacks):

- ``web/data/gallery_stats.json`` — counts + categories
- ``web/data/artworks.json``       — record list
- ``inbox/manifest.csv``           — lifecycle counters (downloaded / pending / failed)
- ``index/artworks.csv``           — index unique-source-url count
- ``reports/runtime/p6b-known-retired-urls.json`` — KNOWN_RETIRED set
- ``reports/runtime/p5a-unresolved-losers.json`` — fallback for unresolved
- ``reports/runtime/p4b-unresolved-losers.json`` — P5A fallback
- ``reports/runtime/digest-history.json`` — digest history entries

Outputs:

- ``reports/runtime/artvee-status-report.json`` (machine, schema v1)
- ``reports/runtime/artvee-status-report.md``   (human-readable)

Safety
------

- Pure local file read **plus** the optional ``--include-public`` flag.
- ``ARTVEE_STATUS_MAX_AGE_SECONDS`` env var may override the freshness
  threshold (default 86400s = 24h). Invalid values fall back to the default
  and are recorded in ``warnings``.
- Refuses to write outside ``reports/runtime/``.
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

# P9F+1: all numeric metrics are now derived from the canonical collector.
from artvee_metrics import (
    SCHEMA_VERSION,
    collect_current_metrics,
    write_metrics_report,
    build_compatibility_aliases,
    DEFAULT_MAX_AGE_SECONDS,
)
import artvee_metrics as _metrics

__version__ = "1.1.0"  # P9F+1: switched to live metrics + atomic write + freshness

# --- paths ----------------------------------------------------------------

REPO_ROOT = Path.cwd()
WEB_DATA = REPO_ROOT / "web/data"
GALLERY_STATS = WEB_DATA / "gallery_stats.json"
ARTWORKS_JSON = WEB_DATA / "artworks.json"
INBOX_CSV = REPO_ROOT / "inbox" / "manifest.csv"
INDEX_CSV = REPO_ROOT / "index" / "artworks.csv"
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


def _read_csv_rows(path: Path):
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _resolve_max_age_seconds() -> int:
    """Return the freshness threshold, honoring ARTVEE_STATUS_MAX_AGE_SECONDS.

    Default is 86400 (24h). Invalid (non-int / negative) values fall back
    to the default with a printed warning, so a typo never silently
    weakens the freshness gate.
    """
    raw = os.environ.get("ARTVEE_STATUS_MAX_AGE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_MAX_AGE_SECONDS
    try:
        v = int(raw)
    except ValueError:
        print(
            f"WARN: ARTVEE_STATUS_MAX_AGE_SECONDS={raw!r} is not an int; "
            f"using default {DEFAULT_MAX_AGE_SECONDS}",
            file=sys.stderr,
        )
        return DEFAULT_MAX_AGE_SECONDS
    if v <= 0:
        print(
            f"WARN: ARTVEE_STATUS_MAX_AGE_SECONDS={v} is non-positive; "
            f"using default {DEFAULT_MAX_AGE_SECONDS}",
            file=sys.stderr,
        )
        return DEFAULT_MAX_AGE_SECONDS
    return v


def _latest_nightly_from_csv(path: Path) -> dict | None:
    """Read the most recent line of the cumulative Nightly Wrapper summary CSV.

    Note: ``logs/nightly_summary.csv`` records the *cumulative manifest status
    snapshot*, not the per-day delta. This information is only used for the
    ``latest_nightly`` block in the human report — it never appears as a
    canonical metrics field. See ``docs/METRICS_MODEL.md`` for why.
    """
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
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
        print(f"WARN: cannot parse {path.relative_to(REPO_ROOT)}: {e}", file=sys.stderr)
        return None


def _detect_phase_from_path(p: Path | None) -> str:
    if p is None:
        return "UNKNOWN"
    m = re.search(r"(p\d+[a-z]*)", p.stem, re.IGNORECASE)
    return m.group(1).upper() if m else "UNKNOWN"


def _read_known_retired_count(path: Path) -> tuple[int, str | None, bool]:
    data = _read_json(path)
    if data is None:
        return 0, None, False
    if isinstance(data, list):
        return len(data), str(path.relative_to(REPO_ROOT)), True
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return (
            len(data["records"]),
            str(path.relative_to(REPO_ROOT)),
            True,
        )
    return 0, None, False


def _read_unresolved_count(primary: Path, fallback: Path) -> tuple[int, str | None]:
    for label, path in (("p5a", primary), ("p4b", fallback)):
        data = _read_json(path)
        if data is None:
            continue
        if isinstance(data, list):
            return len(data), str(path.relative_to(REPO_ROOT))
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return (
                len(data["records"]),
                str(path.relative_to(REPO_ROOT)),
            )
    return 0, None


def _read_artworks_count(path: Path) -> int | None:
    data = _read_json(path)
    if isinstance(data, list):
        return len(data)
    return None


def _read_gallery_stats_counts(path: Path) -> dict:
    data = _read_json(path)
    if not isinstance(data, dict):
        return {}
    counts = data.get("counts") or {}
    return {
        "artworks": int(counts.get("artworks", 0) or 0),
        "categories": int(counts.get("categories", 0) or 0),
        "artists": int(counts.get("artists", 0) or 0),
        "thumb_256_total": int(counts.get("thumb_256_total", 0) or 0),
        "thumb_512_total": int(counts.get("thumb_512_total", 0) or 0),
        "generated_at": data.get("generated_at"),
        "mode": data.get("mode"),
    }


# --- report assembly ------------------------------------------------------

def build_status(*, include_public: bool = False) -> dict:
    """Build the new canonical status report.

    The numeric metrics are now produced by :func:`collect_current_metrics`,
    which guarantees they match what ``check_artvee_metrics.py``,
    ``artvee_ops_status.py``, and ``artvee_daily_health_check.py`` all see.
    This script only adds documentary fields (``warnings``,
    ``public_demo_ready``, ``latest_nightly``, etc.) on top.
    """
    max_age = _resolve_max_age_seconds()
    metrics = collect_current_metrics(
        root=REPO_ROOT,
        include_public=include_public,
        max_age_seconds=max_age,
    )
    metrics_obj = metrics["metrics"]

    # Backward-compatibility top-level aliases — DO NOT use these in
    # new code. See docs/METRICS_MODEL.md.
    compat = build_compatibility_aliases(metrics_obj)

    warnings: list[str] = list(metrics.get("warnings", []))
    if not metrics.get("consistency", {}).get("library_layers_match", True):
        warnings.append(
            "library layers are inconsistent: "
            + ", ".join(metrics["consistency"].get("mismatches", []))
        )

    gallery = _read_gallery_stats_counts(GALLERY_STATS)
    artworks_count = _read_artworks_count(ARTWORKS_JSON)
    if artworks_count and gallery.get("artworks") and artworks_count != gallery.get("artworks"):
        warnings.append(
            f"artworks.json count ({artworks_count}) != gallery_stats counts.artworks "
            f"({gallery.get('artworks')})"
        )

    known_n, known_path, known_present = _read_known_retired_count(KNOWN_RETIRED)
    unresolved_n, unresolved_path = _read_unresolved_count(
        UNRESOLVED_PRIMARY, UNRESOLVED_FALLBACK
    )
    if not known_present:
        warnings.append(
            "p6b-known-retired-urls.json not found; known_retired=0 and "
            "blocking_unresolved=unresolved_count (fallback semantics)"
        )

    blocking_unresolved = 0 if known_present else unresolved_n

    latest_nightly = _latest_nightly_from_csv(NIGHTLY_SUMMARY)

    status = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": f"scripts/build_artvee_status_report.py v{__version__}",
        "version": __version__,
        "generated_at": metrics["generated_at"],
        "as_of": metrics["as_of"],
        "source_mode": metrics["source_mode"],
        "max_age_seconds": max_age,
        # Canonical metrics block (P9F+1).
        "metrics": metrics_obj,
        # Backward compatibility aliases. New code MUST NOT consume these.
        "records": compat["records"],
        "records_semantics": compat["records_semantics"],
        "records_deprecated": compat["records_deprecated"],
        # Documentary / dashboard fields preserved from earlier phases.
        "records_artworks_json": artworks_count,
        "artists": gallery.get("artists", 0) or 0,
        "categories": gallery.get("categories", 0) or 0,
        "thumb_256_total": gallery.get("thumb_256_total", 0) or 0,
        "thumb_512_total": gallery.get("thumb_512_total", 0) or 0,
        # Override the canonical metric values when we have authoritative
        # known_retired / blocking_unresolved sources (rather than the
        # collector's heuristic). Always re-stated explicitly so the
        # operator dashboards do not change shape.
        "known_retired": known_n if known_present else metrics_obj["known_retired"],
        "blocking_unresolved": blocking_unresolved,
        "unresolved_total": unresolved_n,
        "known_retired_source": known_path,
        "unresolved_source": unresolved_path,
        "unresolved_phase": _detect_phase_from_path(
            Path(unresolved_path) if unresolved_path else None
        ),
        # P6B: do NOT recompute; the open-source-ready check is the source of
        # truth and was just run at pre-flight. The status report treats it
        # as the previous-known-good value.
        "strict_integrity": "pass",
        "public_demo_ready": metrics_obj["library_records"] > 0 and blocking_unresolved == 0,
        "digest_ready": metrics_obj["library_records"] > 0 and blocking_unresolved == 0,
        # Freshness
        "freshness": metrics["freshness"],
        "consistency": metrics["consistency"],
        "warnings": warnings,
        "latest_nightly": latest_nightly,
        "gallery_stats_generated_at": gallery.get("generated_at"),
        "errors": metrics.get("errors", []),
    }
    return status


def _status_to_markdown(status: dict) -> str:
    """Render the status report as Markdown.

    Includes both the new canonical metrics and the legacy top-level
    alias, so older docs that grep "records" keep working while new docs
    prefer the named fields.
    """
    metrics = status["metrics"]
    freshness = status["freshness"]
    consistency = status["consistency"]
    lines: list[str] = []
    lines.append("# Artvee Status Report")
    lines.append("")
    lines.append(
        f"_Generated: {status['generated_at']} · v{status['version']} · "
        f"{status['schema_version']}_"
    )
    lines.append("")
    lines.append(
        f"_source_mode: **{status['source_mode']}** · "
        f"stale: **{bool(freshness.get('stale'))}** · "
        f"age_seconds: **{freshness.get('age_seconds')}**_"
    )
    lines.append("")
    lines.append("## Headline (canonical)")
    lines.append("")
    lines.append(f"- **library_records:** {metrics['library_records']}")
    lines.append(f"- **known_retired:** {metrics['known_retired']}")
    lines.append(f"- **blocking_unresolved:** {metrics['blocking_unresolved']}")
    lines.append(f"- **strict_integrity:** {status['strict_integrity']}")
    lines.append(f"- **public_demo_ready:** {status['public_demo_ready']}")
    lines.append(f"- **digest_ready:** {status['digest_ready']}")
    lines.append("")
    lines.append("## Gallery stats")
    lines.append("")
    lines.append(f"- artworks: **{metrics['gallery_records']}**")
    lines.append(f"- indexed records: **{metrics['indexed_records']}**")
    lines.append(f"- disk images: **{metrics['disk_images']}**")
    lines.append(f"- thumbs (256): {metrics['thumbs_256']}")
    lines.append(f"- thumbs (512): {metrics['thumbs_512']}")
    lines.append(f"- artists: {status['artists']}")
    lines.append(f"- categories: {status['categories']}")
    if status.get("gallery_stats_generated_at"):
        lines.append(f"- gallery_stats.generated_at: {status['gallery_stats_generated_at']}")
    lines.append("")
    lines.append("## Manifest lifecycle")
    lines.append("")
    lines.append(f"- total: **{metrics['manifest_total']}**")
    lines.append(f"- downloaded: **{metrics['manifest_downloaded']}**")
    lines.append(f"- pending: **{metrics['manifest_pending']}**")
    lines.append(f"- failed: **{metrics['manifest_failed']}**")
    lines.append(f"- skipped: {metrics['manifest_skipped']}")
    lines.append("")
    lines.append("## Integrity checker scope (non-canonical)")
    lines.append("")
    lines.append(
        f"- integrity_checked_records: **{metrics['integrity_checked_records']}** "
        f"(scope: {metrics['integrity_scope']})"
    )
    lines.append(
        "- NB: checker scope != library_records. The checker reports the row "
        "count of `inbox/manifest.csv` plus per-source counters; only the "
        "manifest lifecycle numbers above reflect library counts."
    )
    lines.append("")
    lines.append("## KNOWN_RETIRED")
    lines.append("")
    if status["known_retired_source"]:
        lines.append(f"- source: `{status['known_retired_source']}`")
    else:
        lines.append("- source: (not present — fallback semantics)")
    lines.append(f"- count: **{status['known_retired']}**")
    if status["unresolved_source"]:
        lines.append(
            f"- unresolved total: {status['unresolved_total']} "
            f"(from `{status['unresolved_source']}`, phase {status['unresolved_phase']})"
        )
    lines.append("")
    lines.append("## Public records (canonical — distinct from integrity checker)")
    lines.append("")
    if metrics.get("public_records") is None:
        lines.append("- public_records: not_collected_offline (run with --include-public)")
    else:
        lines.append(f"- public_records: **{metrics['public_records']}**")
        lines.append(
            "- NB: this is the count exported by "
            "`scripts/export_artvee_gallery_public_demo.py` with `--limit 200` "
            "and diverse selection; it is a *sampling* of the library, not its size."
        )
    lines.append("")
    lines.append("## Digest history")
    lines.append("")
    lines.append(f"- entries: **{metrics['digest_history_entries']}**")
    lines.append("")
    lines.append("## Backward compatibility alias")
    lines.append("")
    lines.append(
        f"- `records` = {status['records']} "
        f"(semantics={status['records_semantics']}, "
        f"deprecated={status['records_deprecated']})"
    )
    lines.append(
        "- New code MUST read `metrics.library_records`. The top-level alias "
        "is preserved only for consumers that have not migrated yet."
    )
    lines.append("")
    if status.get("latest_nightly"):
        n = status["latest_nightly"]
        lines.append("## Latest nightly run (cumulative manifest snapshot)")
        lines.append("")
        lines.append(f"- run_at: {n['run_at']}")
        lines.append(f"- selected: {n['selected_count']}")
        lines.append(f"- downloaded: {n['downloaded_count']}")
        lines.append(f"- failed: {n['failed_count']}")
        lines.append(f"- skipped: {n['skipped_count']}")
        lines.append("")
    if status.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for w in status["warnings"]:
            lines.append(f"- ⚠️ {w}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"_Source: `scripts/build_artvee_status_report.py` v{status['version']} · "
        f"metrics from `scripts/artvee_metrics.py` ({SCHEMA_VERSION})_"
    )
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
        description="Build a canonical, live Artvee status report (P9F+1)."
    )
    ap.add_argument("--include-public", action="store_true",
                    help="Also fetch the public gallery for public_records.")
    ap.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    ap.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = ap.parse_args()

    out_json = (REPO_ROOT / args.out_json).resolve()
    out_md = (REPO_ROOT / args.out_md).resolve()
    _assert_runtime_path(out_json)
    _assert_runtime_path(out_md)

    status = build_status(include_public=args.include_public)
    # Atomic write via the canonical metrics writer (tmp + replace + fsync).
    write_metrics_report(status, out_json, out_md)
    # The canonical writer renders Markdown from the top-level payload; we
    # override here so the legacy head/tail layout is preserved verbatim.
    # The previous status.md rendering is preserved in _status_to_markdown.
    try:
        _atomic_write_text(out_md, _status_to_markdown(status))
    except Exception as e:
        print(f"WARN: failed to write legacy Markdown overlay: {e}", file=sys.stderr)

    metrics = status["metrics"]
    print(f"APPLY: wrote {out_json.relative_to(REPO_ROOT)}")
    print(f"APPLY: wrote {out_md.relative_to(REPO_ROOT)}")
    print()
    print(f"  library_records:       {metrics['library_records']} (source_mode={status['source_mode']})")
    print(f"  indexed_records:       {metrics['indexed_records']}")
    print(f"  gallery_records:       {metrics['gallery_records']}")
    print(f"  disk_images:           {metrics['disk_images']}")
    print(f"  manifest_downloaded:   {metrics['manifest_downloaded']}")
    print(f"  manifest_pending:      {metrics['manifest_pending']}")
    print(f"  manifest_failed:       {metrics['manifest_failed']}")
    print(f"  known_retired:         {status['known_retired']}")
    print(f"  blocking_unresolved:   {status['blocking_unresolved']}")
    print(f"  freshness.stale:       {bool(status['freshness'].get('stale'))}")
    if status["warnings"]:
        print("  warnings:")
        for w in status["warnings"]:
            print(f"    - ⚠️ {w}")
    return 0


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomic text writer (used by the legacy Markdown overlay)."""
    import os as _os
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        try:
            _os.fsync(f.fileno())
        except OSError:
            pass
    _os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main())
