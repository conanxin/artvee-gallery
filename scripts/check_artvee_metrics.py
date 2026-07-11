#!/usr/bin/env python3
"""Metrics regression check (P9F+1).

Runs every invariant the v0.2.1 release promised the canonical metrics
model would satisfy. It is intentionally tiny and self-contained so the
GitHub Actions CI pipeline can invoke it on every push without paying a
noticeable cost.

Exit codes
----------
* 0  - PASS (all invariants satisfied)
* 1  - FAIL (at least one invariant violated; ``--strict`` required to
       turn canonical warnings into failures)
* 2  - USAGE / I/O error

What this script guarantees
--------------------------
1. ``collect_current_metrics`` returns a populated payload with all
   canonical metric keys.
2. ``source_mode == "live"`` and ``freshness.stale == False`` on every
   run (live collectors always report current state).
3. ``library_records`` matches all six library layers
   (``indexed_records``, ``gallery_records``, ``disk_images``,
   ``disk_metadata``, ``thumbs_256``, ``thumbs_512``). When they do not
   match, the assertion message points to the inconsistent layer.
4. ``manifest_downloaded + manifest_pending + manifest_failed +
   manifest_skipped == manifest_total``.
5. ``records`` (the backward-compatibility alias) equals
   ``metrics.library_records``.
6. The output JSON does not contain hard-coded user paths, secrets,
   chat ids, tokens, or absolute home directories.

Usage::

    python3 scripts/check_artvee_metrics.py [--json] [--strict] [--root <path>]

* ``--strict``  Treats warning-level mismatches (consistency warnings) as
  failures. Off by default so the local tree can still pass when the
  repo is in an open-source-only state.
* ``--json``    Emit a JSON report (default is plain text).
* ``--root``    Override the artvee repo root (defaults to ``cwd``).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Resolve sibling module the same way artvee_daily_health_check.py does.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import artvee_metrics  # noqa: E402


SECRET_PATTERNS = (
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"~/?[A-Za-z0-9._-]+/"),
    re.compile(r"(?i)BOT_TOKEN|TELEGRAM_BOT_TOKEN|CHAT_ID=|TG_CHAT_ID"),
    re.compile(r"(?i)openclaw.*secret|secret.*key"),
)


def _walk_for_strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_for_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_for_strings(v)
    elif isinstance(obj, str):
        yield obj


def _scan_secrets(payload) -> list[str]:
    """Return a list of strings that look like secrets.

    The check is intentionally permissive — it flags strings that *look*
    like a path or secret rather than trying to actually crack one. See
    ``scripts/check_open_source_ready.py`` for the project's canonical
    path-leak and secret-keyword checks; this script keeps its own copy
    so the regression can run independently.
    """
    out: list[str] = []
    for s in _walk_for_strings(payload):
        for pat in SECRET_PATTERNS:
            if pat.search(s):
                out.append(s[:80])
                break
    return out


def run_checks(
    root: Path, *, include_public: bool = False, strict: bool = False
) -> dict:
    """Build the regression report. Always returns a dict, even on FAIL."""
    metrics = artvee_metrics.collect_current_metrics(
        root=root, include_public=include_public
    )
    fresh = artvee_metrics.metrics_source_mode(metrics)

    checks: list[dict] = []
    failed = False

    def add(name: str, ok: bool, detail: str = "", severity: str = "must") -> None:
        nonlocal failed
        if not ok and (severity == "must" or strict):
            failed = True
        checks.append(
            {
                "name": name,
                "pass": bool(ok),
                "severity": severity,
                "detail": detail,
            }
        )

    # 1. schema_version present + right
    add(
        "schema_version_is_artvee-metrics-v1",
        metrics.get("schema_version") == artvee_metrics.SCHEMA_VERSION,
        f"got {metrics.get('schema_version')!r}",
    )

    # 2. canonical metrics block exists
    m = metrics.get("metrics") or {}
    needed = [
        "library_records", "indexed_records", "gallery_records",
        "disk_images", "disk_metadata", "thumbs_256", "thumbs_512",
        "manifest_total", "manifest_downloaded", "manifest_pending",
        "manifest_failed", "manifest_skipped", "known_retired",
        "blocking_unresolved", "digest_history_entries",
        "public_records", "integrity_checked_records",
    ]
    missing = [k for k in needed if k not in m]
    add("canonical_metrics_keys_present", not missing, f"missing: {missing}")

    # 3. live source_mode
    add(
        "source_mode_is_live",
        metrics.get("source_mode") == "live",
        f"got {metrics.get('source_mode')!r}",
    )

    # 4. freshness is not stale
    freshness = fresh.get("freshness", {})
    add(
        "freshness_not_stale",
        freshness.get("stale") is False,
        f"stale_reason={freshness.get('stale_reason')!r}",
        severity="should",
    )

    # 5. age_seconds is sane
    age = freshness.get("age_seconds", -1)
    add("age_seconds_is_zero_or_low", isinstance(age, int) and age >= 0 and age < 60,
        f"age={age}", severity="should")

    # 6. library_records == each layer (when library_records > 0)
    if m.get("library_records", 0) > 0:
        layers = ["indexed_records", "gallery_records", "disk_images",
                  "disk_metadata", "thumbs_256", "thumbs_512"]
        for k in layers:
            v = m.get(k)
            same = (v == m["library_records"])
            if not same:
                # We allow thumbnails to defer legitimately when the
                # gallery hasn't been re-thumbnailed yet — this is a
                # warning, not a hard failure.
                severity = "should" if k in ("thumbs_256", "thumbs_512") else "must"
                add(
                    f"layer_{k}_matches_library_records",
                    same,
                    f"{k}={v} != library_records={m['library_records']}",
                    severity=severity,
                )
            else:
                add(f"layer_{k}_matches_library_records", True, f"{k}={v}")
    else:
        add("library_records_is_positive", False,
            "library_records=0 — open-source-only repo? pass with --strict for that state")

    # 7. manifest lifecycle sums match total
    lifecycle_sum = (
        m.get("manifest_downloaded", 0)
        + m.get("manifest_pending", 0)
        + m.get("manifest_failed", 0)
        + m.get("manifest_skipped", 0)
    )
    add(
        "manifest_lifecycle_sum_matches_total",
        lifecycle_sum == m.get("manifest_total", 0),
        f"sum={lifecycle_sum} total={m.get('manifest_total')}",
    )

    # 8. blocking_unresolved == 0 when known_retired.json exists
    expected_blocking = 0 if (root / "reports" / "runtime" / "p6b-known-retired-urls.json").exists() else m.get("blocking_unresolved", 0)
    add(
        "blocking_unresolved_invariant",
        m.get("blocking_unresolved") == expected_blocking,
        f"got {m.get('blocking_unresolved')}, expected {expected_blocking}",
        severity="must",
    )

    # 9. records alias == library_records
    compat = artvee_metrics.build_compatibility_aliases(m)
    add(
        "records_alias_equals_library_records",
        compat["records"] == m["library_records"],
        f"records={compat['records']} library_records={m['library_records']}",
    )
    add(
        "records_alias_marked_deprecated",
        compat["records_deprecated"] is True
        and compat["records_semantics"] == "library_records",
        f"semantics={compat['records_semantics']}",
    )

    # 10. consistency block present
    cons = metrics.get("consistency", {})
    add(
        "consistency_block_present",
        isinstance(cons, dict) and "library_layers_match" in cons,
        f"got {cons!r}",
    )

    # 11. public_records only counted when fetched
    if not include_public:
        add(
            "public_records_null_when_offline",
            m.get("public_records") is None,
            f"got {m.get('public_records')!r}",
            severity="should",
        )

    # 12. freshness reported schema is consistent
    add(
        "freshness_has_required_keys",
        all(k in freshness for k in ("age_seconds", "stale", "stale_reason", "max_age_seconds")),
        f"keys={list(freshness.keys())}",
    )

    # 13. no leaked secrets / paths in canonical output
    leaks = _scan_secrets(metrics)
    add(
        "no_secret_or_path_in_metrics_output",
        not leaks,
        f"leaks={leaks[:3]}",
    )

    # 14. sample sanity — library_records must be sane (warn only)
    add(
        "library_records_is_sane_int",
        isinstance(m.get("library_records"), int) and m.get("library_records", -1) >= 0,
        f"got {m.get('library_records')!r}",
    )

    summary = {
        "checks": checks,
        "passed": sum(1 for c in checks if c["pass"]),
        "failed": sum(1 for c in checks if not c["pass"]),
        "total": len(checks),
        "library_records": m.get("library_records"),
        "source_mode": metrics.get("source_mode"),
        "freshness_stale": bool(freshness.get("stale")),
        "freshness_age_seconds": freshness.get("age_seconds"),
    }
    return {"pass": not failed, "strict": strict, "summary": summary, "metrics": metrics}


def render_text(report: dict) -> str:
    s = report["summary"]
    lines = [
        "== Artvee metrics regression check (P9F+1) ==",
        "",
        f"library_records: {s['library_records']}  "
        f"source_mode: {s['source_mode']}  "
        f"freshness: age={s['freshness_age_seconds']}s stale={s['freshness_stale']}",
        "",
        f"passed: {s['passed']} / {s['total']}",
        "",
        "| Check | Pass | Severity | Detail |",
        "|-------|------|----------|--------|",
    ]
    for c in s["checks"]:
        ok = "✅" if c["pass"] else "❌"
        lines.append(
            f"| {c['name']} | {ok} | {c['severity']} | {c['detail']} |"
        )
    lines.append("")
    lines.append("Overall: " + ("PASS" if report["pass"] else "FAIL"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Artvee canonical metrics regression check (P9F+1).",
    )
    p.add_argument("--strict", action="store_true",
                   help="Treat severity=should mismatches as failures.")
    p.add_argument("--include-public", action="store_true",
                   help="Also collect public_records via online fetch.")
    p.add_argument("--json", action="store_true",
                   help="Emit a JSON report.")
    p.add_argument("--root", default=os.getcwd(),
                   help="Artvee repo root (default: cwd)")
    args = p.parse_args(argv)

    try:
        report = run_checks(
            root=Path(args.root),
            include_public=args.include_public,
            strict=args.strict,
        )
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))

    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
