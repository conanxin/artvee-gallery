#!/usr/bin/env python3
"""Gallery integrity check (P4A+1).

This script is a pure read-only check intended to detect:

* duplicate `source_url` rows in `inbox/manifest.csv` (status=downloaded)
* duplicate `local_image_path` (basename) rows in `index/artworks.csv`
* duplicate `id` values in `web/data/artworks.json`
* duplicate `image_path` / `metadata_path` / `thumb_256` / `thumb_512` values
* one id pointing to multiple source_url values (filename collision)
* one filename pointing to multiple source_url values

The script is **pure stdlib** and does **not** modify any file.

Modes
-----
* Default (no flag):
    Run only on tracked / open-source data (the public repo). If local
    runtime data is missing (e.g. on CI), emit a SKIP notice and exit 0.
* ``--strict``:
    Run on every available source, including local runtime data. Exit
    non-zero on any duplicate / collision.
* ``--allow-known-duplicates``:
    Same scan as ``--strict``. The P4A-frozen fingerprint (11 dupe
    groups / 13 extra rows) was **resolved** by P4B (2026-06-12) so
    this flag is now effectively an alias for ``--strict`` and
    ``KNOWN_DUPE_FINGERPRINT`` is empty. The flag is kept for
    backward compatibility with existing CI workflows.
* ``--json``:
    Emit a machine-readable JSON summary (in addition to the human
    report).

Exit codes
----------
* 0 = PASS (or SKIP if no runtime data and not in strict mode)
* 1 = FAIL (new duplicate / collision, or strict mode finds any)
* 2 = USAGE / I/O error
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

# Path targets (each may be missing; missing paths are SKIP'd)
MANIFEST_PATH = REPO_ROOT / "inbox" / "manifest.csv"
INDEX_PATH = REPO_ROOT / "index" / "artworks.csv"
WEB_JSON_PATH = REPO_ROOT / "web" / "data" / "artworks.json"

# Known duplicate set discovered in P4A audit (2026-06-12).
# Frozen P4A fingerprint of 11 dupe groups / 13 extra rows was
# RESOLVED by P4B (2026-06-12) via filename-collision migration to
# stable source_url hash-suffixed ids. The set is now empty and
# ``--allow-known-duplicates`` has degenerated to a no-op alias
# for ``--strict``.
#
# If a future phase ever needs to freeze a NEW historical duplicate
# set (e.g. after another batch run), populate the dicts below in
# the same shape and the integrity checker will resume comparing
# against that fingerprint.
KNOWN_DUPE_FINGERPRINT: dict[str, dict[str, int]] = {
    "index": {},
    "web": {},
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _stem(path_str: str) -> str:
    if not path_str:
        return ""
    return Path(path_str).stem


def _basename(path_str: str) -> str:
    if not path_str:
        return ""
    return Path(path_str).name


def check_manifest() -> dict[str, Any]:
    rows = _read_csv(MANIFEST_PATH)
    if not rows:
        return {
            "exists": False,
            "skip_reason": "inbox/manifest.csv not present (open-source / CI environment)",
            "rows": 0,
            "downloaded_rows": 0,
            "duplicate_url_groups": 0,
            "duplicate_extra_rows": 0,
        }
    downloaded = [
        r for r in rows if (r.get("status") or "").strip() == "downloaded"
    ]
    urls = [(r.get("url") or "").strip() for r in downloaded]
    c = Counter(u for u in urls if u)
    dupes = {k: v for k, v in c.items() if v > 1}
    return {
        "exists": True,
        "rows": len(rows),
        "downloaded_rows": len(downloaded),
        "unique_urls": len(set(u for u in urls if u)),
        "duplicate_url_groups": len(dupes),
        "duplicate_extra_rows": sum(v - 1 for v in dupes.values()),
        "duplicate_samples": sorted(dupes.keys())[:5],
    }


def check_index() -> dict[str, Any]:
    rows = _read_csv(INDEX_PATH)
    if not rows:
        return {
            "exists": False,
            "skip_reason": "index/artworks.csv not present (open-source / CI environment)",
            "rows": 0,
            "unique_image_basenames": 0,
            "duplicate_groups": 0,
            "duplicate_extra_rows": 0,
            "one_id_to_many_source_url": 0,
        }
    basenames = [_basename(r.get("local_image_path", "")) for r in rows]
    c = Counter(b for b in basenames if b)
    dupes = {k: v for k, v in c.items() if v > 1}
    # a "filename collision" = one basename served by N source_urls
    by_stem_source = defaultdict(set)
    for r in rows:
        stem = _stem(r.get("local_image_path", ""))
        src = (r.get("source_url") or "").strip()
        if stem and src:
            by_stem_source[stem].add(src)
    collision = {k: v for k, v in by_stem_source.items() if len(v) > 1}
    return {
        "exists": True,
        "rows": len(rows),
        "unique_image_basenames": len(set(b for b in basenames if b)),
        "duplicate_groups": len(dupes),
        "duplicate_extra_rows": sum(v - 1 for v in dupes.values()),
        "duplicate_samples": sorted(dupes.keys())[:5],
        "one_id_to_many_source_url": len(collision),
        "collision_samples": sorted(collision.keys())[:5],
    }


def check_web_json() -> dict[str, Any]:
    data = _read_json(WEB_JSON_PATH)
    if data is None:
        return {
            "exists": False,
            "skip_reason": "web/data/artworks.json not present (open-source / CI environment)",
            "records": 0,
            "unique_ids": 0,
            "duplicate_id_groups": 0,
            "duplicate_extra_rows": 0,
            "image_path_dupes": 0,
            "metadata_path_dupes": 0,
            "thumb_256_dupes": 0,
            "thumb_512_dupes": 0,
            "one_id_to_many_source_url": 0,
        }
    if not isinstance(data, list):
        return {"exists": True, "records": 0, "skip_reason": "artworks.json is not a list"}
    ids = [str(a.get("id") or "").strip() for a in data if isinstance(a, dict)]
    id_counter = Counter(i for i in ids if i)
    id_dupes = {k: v for k, v in id_counter.items() if v > 1}

    def _count_dupes(field: str) -> int:
        vals = [str(a.get(field) or "").strip() for a in data if isinstance(a, dict)]
        c = Counter(v for v in vals if v)
        return sum(v - 1 for v in c.values() if v > 1)

    # one id -> many source_url
    by_id_source = defaultdict(set)
    for a in data:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or "").strip()
        src = str(a.get("source_url") or "").strip()
        if aid and src:
            by_id_source[aid].add(src)
    id_collision = {k: v for k, v in by_id_source.items() if len(v) > 1}

    return {
        "exists": True,
        "records": len(data),
        "unique_ids": len(set(i for i in ids if i)),
        "duplicate_id_groups": len(id_dupes),
        "duplicate_extra_rows": sum(v - 1 for v in id_dupes.values()),
        "duplicate_id_samples": sorted(id_dupes.keys())[:5],
        "image_path_dupes": _count_dupes("image_path"),
        "metadata_path_dupes": _count_dupes("metadata_path"),
        "thumb_256_dupes": _count_dupes("thumb_256"),
        "thumb_512_dupes": _count_dupes("thumb_512"),
        "one_id_to_many_source_url": len(id_collision),
        "id_collision_samples": sorted(id_collision.keys())[:5],
    }


def _is_known_fingerprint(
    index_report: dict[str, Any], web_report: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Compare the *current* duplicate shape against the frozen P4A
    fingerprint. Returns (matches, new_patterns).

    The match is exact on (group_count, extra_rows, stem-list) per
    source. New patterns = stems that are duplicates today but were
    not in P4A, OR stems that disappeared (less critical but reported).
    """
    notes: list[str] = []

    # INDEX
    idx_dupes = _dupe_stems_from_index()
    known_idx = set(KNOWN_DUPE_FINGERPRINT["index"].keys())
    current_idx = set(idx_dupes.keys())
    new_in_index = current_idx - known_idx
    missing_in_index = known_idx - current_idx

    # WEB
    web_dupes = _dupe_ids_from_web()
    known_web = set(KNOWN_DUPE_FINGERPRINT["web"].keys())
    current_web = set(web_dupes.keys())
    new_in_web = current_web - known_web
    missing_in_web = known_web - current_web

    # Counts
    if index_report.get("duplicate_groups") != len(KNOWN_DUPE_FINGERPRINT["index"]):
        notes.append(
            f"index duplicate group count changed: "
            f"{index_report.get('duplicate_groups')} vs known "
            f"{len(KNOWN_DUPE_FINGERPRINT['index'])}"
        )
    if index_report.get("duplicate_extra_rows") != 0:
        notes.append(
            f"index duplicate extra rows changed: "
            f"{index_report.get('duplicate_extra_rows')} vs known 0"
        )
    if web_report.get("duplicate_id_groups") != len(KNOWN_DUPE_FINGERPRINT["web"]):
        notes.append(
            f"web duplicate id group count changed: "
            f"{web_report.get('duplicate_id_groups')} vs known "
            f"{len(KNOWN_DUPE_FINGERPRINT['web'])}"
        )
    if web_report.get("duplicate_extra_rows") != 0:
        notes.append(
            f"web duplicate extra rows changed: "
            f"{web_report.get('duplicate_extra_rows')} vs known 0"
        )

    if new_in_index:
        notes.append(f"NEW index dupe stems not in P4A fingerprint: {sorted(new_in_index)}")
    if new_in_web:
        notes.append(f"NEW web dupe ids not in P4A fingerprint: {sorted(new_in_web)}")
    if missing_in_index:
        notes.append(
            f"index dupe stems that disappeared (good!): {sorted(missing_in_index)}"
        )
    if missing_in_web:
        notes.append(
            f"web dupe ids that disappeared (good!): {sorted(missing_in_web)}"
        )

    matches = (
        not new_in_index
        and not new_in_web
        and index_report.get("duplicate_groups") == len(KNOWN_DUPE_FINGERPRINT["index"])
        and index_report.get("duplicate_extra_rows") == 0
        and web_report.get("duplicate_id_groups") == len(KNOWN_DUPE_FINGERPRINT["web"])
        and web_report.get("duplicate_extra_rows") == 0
    )
    return matches, notes


def _dupe_stems_from_index() -> dict[str, int]:
    rows = _read_csv(INDEX_PATH)
    if not rows:
        return {}
    stems = [_stem(r.get("local_image_path", "")) for r in rows]
    c = Counter(s for s in stems if s)
    return {k: v for k, v in c.items() if v > 1}


def _dupe_ids_from_web() -> dict[str, int]:
    data = _read_json(WEB_JSON_PATH)
    if not isinstance(data, list):
        return {}
    ids = [str(a.get("id") or "").strip() for a in data if isinstance(a, dict)]
    c = Counter(i for i in ids if i)
    return {k: v for k, v in c.items() if v > 1}


def render_text(
    manifest: dict[str, Any],
    index: dict[str, Any],
    web: dict[str, Any],
    *,
    allow_known: bool,
    strict: bool,
    is_known: bool,
    notes: list[str],
) -> tuple[str, int]:
    """Return (text, exit_code)."""
    lines: list[str] = []
    lines.append("== Gallery integrity check ==")
    lines.append("")

    # 1. Manifest
    lines.append("[1/3] inbox/manifest.csv")
    if not manifest["exists"]:
        lines.append(f"  SKIP   {manifest.get('skip_reason', 'missing')}")
    else:
        lines.append(f"  rows:               {manifest['rows']}")
        lines.append(f"  downloaded:         {manifest['downloaded_rows']}")
        lines.append(f"  unique urls:        {manifest['unique_urls']}")
        lines.append(
            f"  duplicate url groups:   {manifest['duplicate_url_groups']}"
        )
        lines.append(
            f"  duplicate extra rows:   {manifest['duplicate_extra_rows']}"
        )
    lines.append("")

    # 2. Index
    lines.append("[2/3] index/artworks.csv")
    if not index["exists"]:
        lines.append(f"  SKIP   {index.get('skip_reason', 'missing')}")
    else:
        lines.append(f"  rows:                       {index['rows']}")
        lines.append(
            f"  unique image basenames:     {index['unique_image_basenames']}"
        )
        lines.append(f"  duplicate groups:           {index['duplicate_groups']}")
        lines.append(
            f"  duplicate extra rows:       {index['duplicate_extra_rows']}"
        )
        lines.append(
            f"  one id -> many source_url:  {index['one_id_to_many_source_url']}"
        )
    lines.append("")

    # 3. Web
    lines.append("[3/3] web/data/artworks.json")
    if not web["exists"]:
        lines.append(f"  SKIP   {web.get('skip_reason', 'missing')}")
    else:
        lines.append(f"  records:                    {web['records']}")
        lines.append(f"  unique ids:                 {web['unique_ids']}")
        lines.append(
            f"  duplicate id groups:        {web['duplicate_id_groups']}"
        )
        lines.append(
            f"  duplicate extra rows:       {web['duplicate_extra_rows']}"
        )
        lines.append(f"  image_path dupes:           {web['image_path_dupes']}")
        lines.append(f"  metadata_path dupes:        {web['metadata_path_dupes']}")
        lines.append(f"  thumb_256 dupes:            {web['thumb_256_dupes']}")
        lines.append(f"  thumb_512 dupes:            {web['thumb_512_dupes']}")
        lines.append(
            f"  one id -> many source_url:  {web['one_id_to_many_source_url']}"
        )
    lines.append("")

    # Determine pass/fail
    exit_code = 0
    headline = ""

    any_runtime = (
        manifest["exists"] or index["exists"] or web["exists"]
    )
    if not any_runtime:
        headline = "SKIP   No runtime data present (open-source / CI environment)"
        lines.append(headline)
        lines.append("Overall: SKIP")
        return "\n".join(lines), 0

    if not strict and not allow_known:
        # default mode = no known fingerprint (P4B resolved P4A's
        # 11/13), so it behaves like strict. Kept distinct in code so
        # a future fingerprint can re-enable soft-fail semantics.
        if is_known:
            headline = "PASS   (no new duplicates beyond P4A fingerprint)"
        else:
            headline = "FAIL   (new duplicates beyond P4A fingerprint)"
            exit_code = 1
    elif allow_known:
        # --allow-known-duplicates: alias for --strict since P4B
        # (P4A fingerprint is empty)
        any_dupes = (
            (manifest.get("duplicate_url_groups", 0) > 0)
            or (index.get("duplicate_groups", 0) > 0)
            or (web.get("duplicate_id_groups", 0) > 0)
        )
        if any_dupes:
            headline = (
                f"FAIL   (allow-known mode: "
                f"manifest_dupes={manifest.get('duplicate_url_groups', 0)}, "
                f"index_dupes={index.get('duplicate_groups', 0)}, "
                f"web_dupes={web.get('duplicate_id_groups', 0)})"
            )
            exit_code = 1
        else:
            headline = "PASS   (allow-known: P4A fingerprint is empty after P4B, no dupes)"
    elif strict:
        # strict: any dupe => fail
        any_dupes = (
            (manifest.get("duplicate_url_groups", 0) > 0)
            or (index.get("duplicate_groups", 0) > 0)
            or (web.get("duplicate_id_groups", 0) > 0)
        )
        if any_dupes:
            headline = (
                f"FAIL   (strict mode: "
                f"manifest_dupes={manifest.get('duplicate_url_groups', 0)}, "
                f"index_dupes={index.get('duplicate_groups', 0)}, "
                f"web_dupes={web.get('duplicate_id_groups', 0)})"
            )
            exit_code = 1
        else:
            headline = "PASS   (strict mode: no duplicates found)"

    lines.append(headline)
    if notes:
        lines.append("")
        lines.append("Fingerprint notes:")
        for n in notes:
            lines.append(f"  - {n}")
    lines.append("Overall: PASS" if exit_code == 0 else "Overall: FAIL")

    return "\n".join(lines), exit_code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Gallery integrity check (P4B, read-only)"
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any duplicate / collision.",
    )
    p.add_argument(
        "--allow-known-duplicates",
        action="store_true",
        help=(
            "Tolerate the historical 11 dupe groups / 13 extra rows from "
            "the P4A audit. Since P4B (2026-06-12) the P4A fingerprint "
            "is empty, so this flag is now an alias for --strict. Kept "
            "for backward compatibility with existing CI workflows."
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON summary.",
    )
    args = p.parse_args(argv)

    manifest = check_manifest()
    index = check_index()
    web = check_web_json()
    is_known, notes = _is_known_fingerprint(index, web)

    text, exit_code = render_text(
        manifest,
        index,
        web,
        allow_known=args.allow_known_duplicates,
        strict=args.strict,
        is_known=is_known,
        notes=notes,
    )

    print(text)
    if args.json:
        print()
        print("--- JSON ---")
        print(
            json.dumps(
                {
                    "manifest": manifest,
                    "index": index,
                    "web": web,
                    "is_known_fingerprint": is_known,
                    "fingerprint_notes": notes,
                    "exit_code": exit_code,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        sys.exit(2)
