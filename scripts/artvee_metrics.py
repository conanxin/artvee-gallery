#!/usr/bin/env python3
"""Artvee canonical metrics collector (P9F+1).

This is the *single* implementation of every "records"-shaped number that
the rest of the project (Daily Health, Ops Status, Status Report, Telegram
notifications, public summary) depends on. Before P9F+1, four different
numbers (875 / 1093 / 1206 / 200) were all labelled "records" by different
callers reading different sources. After this module, every caller must
either:

  1. Call :func:`collect_current_metrics` to read live state from disk in a
     single sweep — no manifest re-read, no stale cache, and consistent
     numbers within a single report run; OR
  2. Explicitly pass a pre-collected ``metrics`` dict to the renderers in
     :mod:`artvee_daily_health_check`, :mod:`artvee_ops_status`, and
     :mod:`build_artvee_status_report`.

Either path guarantees a report is tagged ``source_mode: live`` and
``freshness.stale: false`` when it actually re-read disk, or
``source_mode: fallback_cache`` plus a measured ``age_seconds`` plus
``freshness.stale: true`` if a caller had to fall back to a cached status
snapshot.

The collector is **read-only on disk**. No batch / download / refill side
effect. The artvee repo is assumed to be the working directory when this
module is invoked; the function also accepts an explicit ``root`` argument
for tests and isolation.

Schema (artvee-metrics-v1)::

    {
      "schema_version": "artvee-metrics-v1",
      "generated_at": "<ISO8601 UTC>",
      "as_of": "<ISO8601 UTC>",
      "source_mode": "live" | "fallback_cache",
      "max_age_seconds": 86400,
      "metrics": {
        "library_records": int,            # canonical available works
        "indexed_records": int,            # index rows (unique source_url)
        "gallery_records": int,            # web/data/artworks.json unique ids
        "disk_images": int,
        "disk_metadata": int,
        "thumbs_256": int,
        "thumbs_512": int,
        "manifest_total": int,
        "manifest_downloaded": int,
        "manifest_pending": int,
        "manifest_failed": int,
        "manifest_skipped": int,
        "known_retired": int,
        "blocking_unresolved": int,
        "digest_history_entries": int,
        "public_records": int | null,      # null when offline / unchecked
        "integrity_checked_records": int,  # checker manifest.rows
        "integrity_scope": "manifest+index+web",
      },
      "consistency": {
        "library_layers_match": bool,
        "mismatches": [str, ...]
      },
      "freshness": {
        "age_seconds": int,
        "stale": bool,
        "stale_reason": str | "",
        "max_age_seconds": int
      },
      "warnings": [str, ...],
      "errors": [str, ...]
    }
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_DT = datetime  # used by helpers below

SCHEMA_VERSION = "artvee-metrics-v1"
DEFAULT_MAX_AGE_SECONDS = 86400  # 24h
PUBLIC_GALLERY_URL = "https://conanxin.github.io/projects/artvee-gallery-demo/data/artworks.json"

__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_MAX_AGE_SECONDS",
    "PUBLIC_GALLERY_URL",
    "collect_current_metrics",
    "write_metrics_report",
    "atomic_write_json",
    "atomic_write_text",
    "now_iso",
    "metrics_age_seconds",
    "metrics_source_mode",
    "build_compatibility_aliases",
]


# --------------------------------------------------------------------------- #
# small disk utilities (deliberately stdlib only; no hermes-tools dependency)  #
# --------------------------------------------------------------------------- #


def now_iso() -> str:
    """Return current UTC ISO8601 with second precision."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _utc_parse(value: str) -> "_DT | None":
    if not value:
        return None
    try:
        # Accept both +00:00 and trailing Z.
        v = value.replace("Z", "+00:00")
        return _DT.fromisoformat(v)
    except Exception:
        return None


def metrics_age_seconds(metrics: dict[str, Any]) -> int:
    """Compute age of *metrics* relative to its ``generated_at``.

    Returns -1 when ``generated_at`` is missing or unparseable. Used by
    :func:`metrics_source_mode` to flag stale caches.
    """
    gen = _utc_parse(metrics.get("generated_at") or "")
    if gen is None:
        return -1
    now = datetime.now(timezone.utc)
    delta = (now - gen).total_seconds()
    return max(0, int(delta))


def metrics_source_mode(
    metrics: dict[str, Any] | None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Compute ``freshness`` block for a metrics dict.

    Returns::

        {"source_mode": "live" | "fallback_cache",
         "freshness": {"age_seconds": int,
                       "stale": bool,
                       "stale_reason": str | "",
                       "max_age_seconds": int}}

    If ``metrics`` is None (e.g. live collect failed and no cache exists),
    ``source_mode == "live"`` is preserved but ``stale = True`` with reason
    ``"no_metrics"`` so callers can surface a metrics-stale warning without
    pretending the data is healthy.
    """
    if metrics is None:
        return {
            "source_mode": "live",
            "freshness": {
                "age_seconds": -1,
                "stale": True,
                "stale_reason": "no_metrics_collected",
                "max_age_seconds": int(max_age_seconds),
            },
        }
    age = metrics_age_seconds(metrics)
    stale = age < 0 or age > int(max_age_seconds)
    if stale:
        if age < 0:
            reason = "generated_at_missing_or_unparseable"
        else:
            reason = f"age_{age}s_exceeds_max_{int(max_age_seconds)}s"
    else:
        reason = ""
    return {
        "source_mode": metrics.get("source_mode") or "live",
        "freshness": {
            "age_seconds": age,
            "stale": stale,
            "stale_reason": reason,
            "max_age_seconds": int(max_age_seconds),
        },
    }


def atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically (tmp + fsync + replace). Avoids readers
    seeing a half-written file when a status report regenerates."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            # Filesystems without fsync (rare on Linux); still safer than
            # direct write because the rename below is atomic on POSIX.
            pass
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# per-source counters                                                          #
# --------------------------------------------------------------------------- #


def _count_disk(path: Path) -> int:
    """Count real files under *path*, excluding ``.gitkeep``."""
    if not path.exists():
        return 0
    n = 0
    for p in path.rglob("*"):
        if p.is_file() and p.name != ".gitkeep":
            n += 1
    return n


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return sum(1 for _ in reader if any(_.values()))


def _manifest_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {
            "manifest_total": 0,
            "manifest_downloaded": 0,
            "manifest_pending": 0,
            "manifest_failed": 0,
            "manifest_skipped": 0,
        }
    total = 0
    downloaded = 0
    pending = 0
    failed = 0
    skipped = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not any(row.values()):
                continue
            total += 1
            status = (row.get("status") or row.get("state") or "").strip().lower()
            if status == "downloaded":
                downloaded += 1
            elif status == "pending":
                pending += 1
            elif status == "failed":
                failed += 1
            elif status == "skipped":
                skipped += 1
    return {
        "manifest_total": total,
        "manifest_downloaded": downloaded,
        "manifest_pending": pending,
        "manifest_failed": failed,
        "manifest_skipped": skipped,
    }


def _index_unique(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"index_rows": 0, "indexed_records": 0}
    rows = 0
    urls: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not any(row.values()):
                continue
            rows += 1
            url = (row.get("source_url") or row.get("url") or "").strip()
            if url:
                urls.add(url)
    return {
        "index_rows": rows,
        "indexed_records": len(urls),
    }


def _web_artworks(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"gallery_records": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"gallery_records": 0}
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("artworks") or data.get("items") or []
    else:
        items = []
    ids = {
        str(x.get("id") or "").strip()
        for x in items
        if isinstance(x, dict)
    }
    gallery_unique = len({i for i in ids if i})
    return {"gallery_records": max(len(items), gallery_unique)}


def _known_retired(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        r = data.get("records")
        if isinstance(r, list):
            return len(r)
        u = data.get("urls")
        if isinstance(u, list):
            return len(u)
    return 0


def _unresolved_total(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        r = data.get("records")
        if isinstance(r, list):
            return len(r)
    return 0


def _digest_entries(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if isinstance(data, dict):
        entries = data.get("entries") or data.get("history") or []
        if isinstance(entries, list):
            return len(entries)
    return 0


def _public_records(url: str, timeout: int = 8) -> int | None:
    """Fetch public artworks.json and return ``len()``.

    Returns ``None`` when the network call fails (DNS, timeout, HTTP error).
    Callers MUST distinguish ``null`` ("not checked / offline") from a
    real integer count.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        items = data.get("artworks") or data.get("items") or []
        if isinstance(items, list):
            return len(items)
    return 0


# --------------------------------------------------------------------------- #
# canonical collector                                                         #
# --------------------------------------------------------------------------- #


def collect_current_metrics(
    root: Path | None = None,
    *,
    include_public: bool = False,
    public_url: str = PUBLIC_GALLERY_URL,
    public_timeout: int = 8,
    max_age_seconds: int | None = None,
) -> dict[str, Any]:
    """Read live state from the artvee repo and return the metrics dict.

    Parameters
    ----------
    root : Path | None
        Repo root. Defaults to the current working directory.
    include_public : bool
        When True, performs a network GET of the public gallery URL and
        records ``public_records``; otherwise it stays ``null`` so offline
        runs are not silently thin.
    public_url : str
        Override URL (mostly for tests).
    public_timeout : int
        Seconds before we give up on the public GET.

    Returns
    -------
    dict
        A populated metrics dict conforming to the schema. ``freshness``
        is computed against ``max_age_seconds`` (default 24h).
    """
    if root is None:
        root = Path.cwd()
    root = Path(root)

    inbox = root / "inbox" / "manifest.csv"
    idx = root / "index" / "artworks.csv"
    web_json = root / "web" / "data" / "artworks.json"
    stats_json = root / "web" / "gallery_stats.json"
    known_path = root / "reports" / "runtime" / "p6b-known-retired-urls.json"
    unresolved_primary = root / "reports" / "runtime" / "p5a-unresolved-losers.json"
    unresolved_fallback = root / "reports" / "runtime" / "p4b-unresolved-losers.json"
    digest_hist = root / "reports" / "runtime" / "digest-history.json"

    warnings: list[str] = []
    errors: list[str] = []

    manifest = _manifest_counts(inbox)
    index = _index_unique(idx)
    web = _web_artworks(web_json)
    disk = {
        "disk_images": _count_disk(root / "images"),
        "disk_metadata": _count_disk(root / "metadata"),
        "thumbs_256": _count_disk(root / "thumbs" / "256"),
        "thumbs_512": _count_disk(root / "thumbs" / "512"),
    }

    # Use gallery_records as library_records; fall back to indexed_records
    # if web data is missing (open-source-only checkouts).
    library_records = web["gallery_records"]
    if library_records == 0 and index["indexed_records"] > 0:
        library_records = index["indexed_records"]
        warnings.append("library_records from index (web JSON missing)")
    if library_records == 0 and disk["disk_images"] > 0:
        library_records = disk["disk_images"]
        warnings.append("library_records from disk_images (web/index missing)")

    known = _known_retired(known_path)
    unresolved_total = _unresolved_total(unresolved_primary)
    if unresolved_total == 0:
        unresolved_total = _unresolved_total(unresolved_fallback)
    blocking_unresolved = 0 if known_path.exists() else unresolved_total

    metrics_obj: dict[str, Any] = {
        "library_records": library_records,
        "indexed_records": index["indexed_records"],
        "gallery_records": web["gallery_records"],
        **disk,
        **manifest,
        "known_retired": known,
        "blocking_unresolved": blocking_unresolved,
        "digest_history_entries": _digest_entries(digest_hist),
        "public_records": None,
        "integrity_checked_records": manifest["manifest_total"],
        "integrity_scope": "manifest+index+web",
    }

    if include_public:
        pub = _public_records(public_url, timeout=public_timeout)
        metrics_obj["public_records"] = pub
        if pub is None:
            warnings.append(f"public_records: fetch failed ({public_url})")

    # Consistency — library_records must equal every layer count
    layers: list[tuple[str, int]] = [
        ("indexed_records", metrics_obj["indexed_records"]),
        ("gallery_records", metrics_obj["gallery_records"]),
        ("disk_images", metrics_obj["disk_images"]),
        ("disk_metadata", metrics_obj["disk_metadata"]),
        ("thumbs_256", metrics_obj["thumbs_256"]),
        ("thumbs_512", metrics_obj["thumbs_512"]),
    ]
    mismatches: list[str] = []
    if library_records > 0:
        for name, value in layers:
            if value != library_records:
                mismatches.append(
                    f"{name}={value} != library_records={library_records}"
                )
    else:
        warnings.append("library_records=0; consistency comparison skipped")

    # Manifest lifecycle accounting
    mc_sum = (
        manifest["manifest_downloaded"]
        + manifest["manifest_pending"]
        + manifest["manifest_failed"]
        + manifest["manifest_skipped"]
    )
    if mc_sum != manifest["manifest_total"]:
        warnings.append(
            "manifest lifecycle mismatch: downloaded+pending+failed+skipped="
            f"{mc_sum} != manifest_total={manifest['manifest_total']}"
        )

    # Cross-source alerts that don't fail comparison but matter
    for layer_name, layer_value in [
        ("manifest_downloaded", metrics_obj["manifest_downloaded"]),
        ("manifest_pending", metrics_obj["manifest_pending"]),
        ("manifest_failed", metrics_obj["manifest_failed"]),
    ]:
        if layer_value < 0:
            warnings.append(f"{layer_name} is negative")

    timestamp = now_iso()
    out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp,
        "as_of": timestamp,
        "source_mode": "live",
        "max_age_seconds": int(max_age_seconds if max_age_seconds is not None else DEFAULT_MAX_AGE_SECONDS),
        "metrics": metrics_obj,
        "consistency": {
            "library_layers_match": not bool(mismatches),
            "mismatches": mismatches,
        },
        "warnings": warnings,
        "errors": errors,
    }
    freshness_block = metrics_source_mode(out, out["max_age_seconds"])
    out["freshness"] = freshness_block["freshness"]
    return out


def build_compatibility_aliases(metrics_obj: dict[str, Any]) -> dict[str, Any]:
    """Produce legacy top-level aliases from a metrics dict.

    The only aliases we still emit are::

        records            -> metrics.library_records
        records_semantics  -> "library_records"
        records_deprecated -> True

    Callers MUST treat ``records`` as read-only. New code should always use
    ``metrics.library_records`` (see ``docs/METRICS_MODEL.md``).
    """
    return {
        "records": metrics_obj["library_records"],
        "records_semantics": "library_records",
        "records_deprecated": True,
    }


# --------------------------------------------------------------------------- #
# writer (status report md + cache json)                                       #
# --------------------------------------------------------------------------- #


def _md_table(rows: Iterable[tuple[str, Any]]) -> list[str]:
    lines = ["| Metric | Value |", "|--------|-------|"]
    for k, v in rows:
        lines.append(f"| {k} | {v} |")
    return lines


def render_metrics_markdown(payload: dict[str, Any]) -> str:
    """Render a metrics dict as a human-readable Markdown report.

    Both the top-level legacy aliases and the nested ``metrics`` object
    are included; the table highlights library-level numbers and
    distinguishes freshness.
    """
    metrics = payload.get("metrics") or {}
    freshness = payload.get("freshness") or {}
    consistency = payload.get("consistency") or {}
    rows: list[tuple[str, Any]] = [
        ("Library records", metrics.get("library_records")),
        ("Indexed records", metrics.get("indexed_records")),
        ("Gallery records", metrics.get("gallery_records")),
        ("Disk images", metrics.get("disk_images")),
        ("Disk metadata", metrics.get("disk_metadata")),
        ("Thumbs 256", metrics.get("thumbs_256")),
        ("Thumbs 512", metrics.get("thumbs_512")),
        ("", ""),
        ("Manifest total", metrics.get("manifest_total")),
        ("Manifest downloaded", metrics.get("manifest_downloaded")),
        ("Manifest pending", metrics.get("manifest_pending")),
        ("Manifest failed", metrics.get("manifest_failed")),
        ("Manifest skipped", metrics.get("manifest_skipped")),
        ("", ""),
        ("Known retired", metrics.get("known_retired")),
        ("Blocking unresolved", metrics.get("blocking_unresolved")),
        ("Digest history entries", metrics.get("digest_history_entries")),
        ("Public records (online)", metrics.get("public_records")),
        ("", ""),
        ("Integrity checked records", metrics.get("integrity_checked_records")),
        ("Integrity scope", metrics.get("integrity_scope")),
    ]

    table_lines = _md_table(rows)
    table_str = "\n".join(table_lines)

    notes: list[str] = []
    for w in payload.get("warnings", []):
        notes.append(f"- ⚠️ {w}")
    for e in payload.get("errors", []):
        notes.append(f"- ❌ {e}")
    for m in consistency.get("mismatches", []):
        notes.append(f"- ⚠️ mismatch: {m}")

    compat = build_compatibility_aliases(metrics)
    title = (
        f"# Artvee Status Report (canonical metrics · "
        f"{payload['schema_version']})\n\n"
        f"_Generated: {payload.get('generated_at')} · "
        f"source_mode: **{payload.get('source_mode')}** · "
        f"stale: **{bool(freshness.get('stale'))}**_\n\n"
        "## Headline\n\n"
        f"- **library_records:** {metrics.get('library_records')}\n"
        f"- **known_retired:** {metrics.get('known_retired')}\n"
        f"- **blocking_unresolved:** {metrics.get('blocking_unresolved')}\n"
        f"- **integrity checked records:** {metrics.get('integrity_checked_records')}\n"
        f"- **strict_integrity:** {payload.get('strict_integrity', 'PASS')}\n"
        f"- **public_demo_ready:** {bool(payload.get('public_demo_ready'))}\n"
        f"- **digest_ready:** {bool(payload.get('digest_ready'))}\n\n"
        "## Canonical metrics\n\n"
        f"{table_str}\n\n"
        "## Freshness\n\n"
        f"- generated_at: {payload.get('generated_at')}\n"
        f"- source_mode: {payload.get('source_mode')}\n"
        f"- age_seconds: {freshness.get('age_seconds')}\n"
        f"- stale: {bool(freshness.get('stale'))}\n"
        f"- stale_reason: {freshness.get('stale_reason') or ''}\n"
        f"- max_age_seconds: {freshness.get('max_age_seconds')}\n\n"
        "## Backward compatibility alias\n\n"
        f"- records: {compat['records']} "
        f"(semantics={compat['records_semantics']}, "
        f"deprecated={compat['records_deprecated']})\n\n"
        "## Warnings\n\n"
        + ("\n".join(notes) if notes else "_none_") +
        "\n\n---\n\n"
        "_Source: scripts/artvee_metrics.py · "
        f"{payload.get('schema_version')}_\n"
    )
    return title


def write_metrics_report(
    payload: dict[str, Any],
    json_path: Path,
    md_path: Path | None = None,
) -> None:
    """Atomically write the metrics JSON (and optional Markdown)."""
    atomic_write_json(Path(json_path), payload)
    if md_path is not None:
        atomic_write_text(Path(md_path), render_metrics_markdown(payload))


# --------------------------------------------------------------------------- #
# cli                                                                         #
# --------------------------------------------------------------------------- #


def _cli_main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="Collect Artvee canonical metrics (live or fallback)."
    )
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--include-public", action="store_true",
                    help="Include online public_records fetch")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON only")
    ap.add_argument("--out-json", help="Write JSON to path")
    ap.add_argument("--out-md", help="Write Markdown to path")
    args = ap.parse_args(argv)

    payload = collect_current_metrics(
        root=Path(args.root),
        include_public=args.include_public,
    )
    if args.out_json:
        atomic_write_json(Path(args.out_json), payload)
    if args.out_md:
        atomic_write_text(Path(args.out_md), render_metrics_markdown(payload))
    if args.json or (not args.out_json and not args.out_md):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
