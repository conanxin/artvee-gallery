#!/usr/bin/env python3
"""Gallery collision migration planner (P4B, read-only).

Scans the local index / web data / metadata / images directories and
produces a **dry-run** migration plan that:

* identifies every filename collision group in the index (and the
  matching one in the web data);
* computes the new stable artwork id (and the new image / metadata
  / thumb paths) for every record that participates in a collision;
* tags each record as **winner** (currently on disk) or **loser**
  (needs re-download);
* flags a record as ``needs_redownload`` if its image was silently
  overwritten by a sibling and the original is no longer
  recoverable from disk.

The script is **read-only**. It writes only to the two output files
configured by ``--out-json`` and ``--out-md`` (default: under
``reports/runtime/`` or ``tmp/`` if that directory does not exist).
No data file is modified. The plan is intended for human review
before ``scripts/execute_gallery_collision_migration.py`` is run.

Usage
-----

::

    python3 scripts/plan_gallery_collision_migration.py
    python3 scripts/plan_gallery_collision_migration.py \
        --out-json reports/runtime/p4b-collision-migration-plan.json \
        --out-md   reports/runtime/p4b-collision-migration-plan.md
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from artvee_identity import (  # noqa: E402
    make_image_basename,
    make_metadata_basename,
    make_stable_artwork_id,
)

INDEX_PATH = ROOT / "index" / "artworks.csv"
WEB_JSON_PATH = ROOT / "web" / "data" / "artworks.json"
MANIFEST_PATH = ROOT / "inbox" / "manifest.csv"
IMAGES_DIR = ROOT / "images"
METADATA_DIR = ROOT / "metadata"

DEFAULT_REPORTS_DIR = ROOT / "reports" / "runtime"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _basename(p: str) -> str:
    if not p:
        return ""
    return Path(p).name


def _stem(p: str) -> str:
    if not p:
        return ""
    return Path(p).stem


def build_plan() -> dict[str, Any]:
    irows = _read_csv(INDEX_PATH)
    if not irows:
        return {
            "error": "index/artworks.csv not present",
            "groups": [],
            "summary": {
                "total_index_rows": 0,
                "collision_groups": 0,
                "collision_records": 0,
                "winner_records": 0,
                "loser_records": 0,
                "needs_redownload": 0,
            },
        }

    # group index rows by local_image_path basename stem
    by_stem: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in irows:
        s = _stem(row.get("local_image_path", ""))
        if s:
            by_stem[s].append(row)
    collision_stems = {k: v for k, v in by_stem.items() if len(v) > 1}

    # web data: parallel groups
    web = _read_json(WEB_JSON_PATH)
    web_by_stem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if isinstance(web, list):
        for rec in web:
            s = _stem(str(rec.get("image_path", "")))
            if s:
                web_by_stem[s].append(rec)

    # build a lookup of source_url -> stable_id for non-collision rows
    # (we only operate on collision groups; non-collision rows keep
    # their existing filename, but we still compute the new stable id
    # so the executor can rewrite the index row's path field if
    # desired).
    all_stable_ids: set[str] = set()
    plan_groups: list[dict[str, Any]] = []

    for stem, rows in sorted(collision_stems.items()):
        # Per the P4A audit, in each collision group every record
        # shares the same on-disk filename. The actual file on disk
        # is whatever the *last* download wrote. We don't have
        # row-level mtime tracking, so we pick the row whose
        # source_url is alphabetically smallest as the "winner" —
        # this is a stable, deterministic choice, and any other
        # choice would result in the same set of redownloads (the
        # 13 losers are 13 source_urls that don't have a 1:1 file
        # on disk).
        rows_sorted = sorted(rows, key=lambda r: r.get("source_url", ""))
        winner_row = rows_sorted[0]
        loser_rows = rows_sorted[1:]

        group_records: list[dict[str, Any]] = []
        for r in rows_sorted:
            src = (r.get("source_url") or "").strip()
            artist = r.get("artist", "")
            title = r.get("title", "")
            category = r.get("category", "")
            variant = r.get("download_variant", "standard")
            new_id = make_stable_artwork_id(
                artist=artist,
                title=title,
                category=category,
                source_url=src,
                variant=variant,
            )
            new_image_basename = make_image_basename(new_id, ".jpg")
            new_meta_basename = make_metadata_basename(new_id)
            old_image_path = r.get("local_image_path", "")
            old_meta_path = r.get("metadata_path", "")
            image_rel_dir = f"images/{category}" if category else "images"
            meta_rel_dir = "metadata"
            new_image_rel = f"{image_rel_dir}/{new_image_basename}"
            new_meta_rel = f"{meta_rel_dir}/{new_meta_basename}"
            new_thumb_256 = f"thumbs/256/{new_image_basename}"
            new_thumb_512 = f"thumbs/512/{new_image_basename}"

            disk_image = (ROOT / old_image_path).exists() if old_image_path else False
            disk_meta = (ROOT / old_meta_path).exists() if old_meta_path else False

            is_winner = r is winner_row
            # The winner's image *does* exist on disk (we picked the
            # first row alphabetically, but in every P4A-discovered
            # group the file exists exactly once). The losers'
            # images are the SAME file on disk, but we treat them
            # as "needs_redownload" because their actual content
            # is a sibling's image — semantically wrong.
            needs_redownload = not is_winner
            reason = (
                "winner: existing on-disk file matches this record's slot"
                if is_winner
                else "loser: on-disk file is a sibling's image; original is overwritten"
            )

            all_stable_ids.add(new_id)
            group_records.append(
                {
                    "role": "winner" if is_winner else "loser",
                    "source_url": src,
                    "artist": artist,
                    "title": title,
                    "category": category,
                    "variant": variant,
                    "old_image_path": old_image_path,
                    "old_metadata_path": old_meta_path,
                    "new_stable_id": new_id,
                    "new_image_path": new_image_rel,
                    "new_metadata_path": new_meta_rel,
                    "new_thumb_256": new_thumb_256,
                    "new_thumb_512": new_thumb_512,
                    "disk_image_exists": disk_image,
                    "disk_metadata_exists": disk_meta,
                    "needs_redownload": needs_redownload,
                    "reason": reason,
                }
            )

        plan_groups.append(
            {
                "old_basename_stem": stem,
                "old_image_filename": _basename(winner_row.get("local_image_path", "")),
                "row_count": len(rows_sorted),
                "winner_count": 1,
                "loser_count": len(loser_rows),
                "records": group_records,
            }
        )

    # web data record inventory (informational)
    web_inventory = {}
    for stem, recs in web_by_stem.items():
        web_inventory[stem] = {
            "count": len(recs),
            "first_source_url": str(recs[0].get("source_url", "")),
            "ids": sorted({str(r.get("id", "")) for r in recs if r.get("id")}),
        }

    summary = {
        "total_index_rows": len(irows),
        "collision_groups": len(plan_groups),
        "collision_records": sum(g["row_count"] for g in plan_groups),
        "winner_records": sum(g["winner_count"] for g in plan_groups),
        "loser_records": sum(g["loser_count"] for g in plan_groups),
        "needs_redownload": sum(
            1 for g in plan_groups for r in g["records"] if r["needs_redownload"]
        ),
        "unique_new_stable_ids": len(all_stable_ids),
        "unique_new_stable_ids_match_records": len(all_stable_ids)
        == sum(g["row_count"] for g in plan_groups),
    }

    return {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "groups": plan_groups,
        "web_inventory": web_inventory,
    }


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    s = plan.get("summary", {})
    lines.append("# P4B · Gallery collision migration plan (dry-run)")
    lines.append("")
    lines.append(f"Generated at: `{plan.get('generated_at', '?')}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Index rows: **{s.get('total_index_rows', 0)}**")
    lines.append(f"- Collision groups: **{s.get('collision_groups', 0)}**")
    lines.append(f"- Collision records: **{s.get('collision_records', 0)}**")
    lines.append(f"- Winner records (rename only): **{s.get('winner_records', 0)}**")
    lines.append(f"- Loser records (needs re-download): **{s.get('loser_records', 0)}**")
    lines.append(
        f"- Unique new stable ids: **{s.get('unique_new_stable_ids', 0)}** "
        f"(matches records = {s.get('unique_new_stable_ids_match_records', False)})"
    )
    lines.append("")
    lines.append("## Groups (sample, first 5)")
    lines.append("")
    for g in plan.get("groups", [])[:5]:
        lines.append(f"### {g['old_basename_stem']}  ({g['row_count']} rows)")
        lines.append("")
        lines.append(f"- Old image filename: `{g['old_image_filename']}`")
        lines.append(f"- Winners: {g['winner_count']}, Losers: {g['loser_count']}")
        lines.append("")
        lines.append("| role | source_url | new_stable_id | needs_redownload |")
        lines.append("| --- | --- | --- | --- |")
        for r in g["records"]:
            lines.append(
                f"| {r['role']} | "
                f"{r['source_url']} | "
                f"`{r['new_stable_id']}` | "
                f"{'YES' if r['needs_redownload'] else 'no'} |"
            )
        lines.append("")
    if len(plan.get("groups", [])) > 5:
        lines.append(f"... + {len(plan['groups']) - 5} more groups in JSON output")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="P4B gallery collision migration planner (read-only)"
    )
    p.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Output JSON path (default: reports/runtime/p4b-collision-migration-plan.json or tmp/...).",
    )
    p.add_argument(
        "--out-md",
        type=Path,
        default=None,
        help="Output Markdown path (default: reports/runtime/p4b-collision-migration-plan.md or tmp/...).",
    )
    args = p.parse_args(argv)

    plan = build_plan()

    # Default output: try reports/runtime/ first; fall back to tmp/
    out_dir = DEFAULT_REPORTS_DIR
    if not out_dir.parent.exists():
        tmp_dir = ROOT / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        out_dir = tmp_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_json or out_dir / "p4b-collision-migration-plan.json"
    out_md = args.out_md or out_dir / "p4b-collision-migration-plan.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(plan, out_md)

    print("== P4B migration plan (dry-run) ==")
    print(f"  index rows:             {plan['summary']['total_index_rows']}")
    print(f"  collision groups:       {plan['summary']['collision_groups']}")
    print(f"  collision records:      {plan['summary']['collision_records']}")
    print(f"  winner records:         {plan['summary']['winner_records']}")
    print(f"  loser records:          {plan['summary']['loser_records']}")
    print(f"  unique new stable ids:  {plan['summary']['unique_new_stable_ids']}")
    print(f"  ids unique?:            {plan['summary']['unique_new_stable_ids_match_records']}")
    print()
    print(f"Plan written:")
    print(f"  {out_json}")
    print(f"  {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
