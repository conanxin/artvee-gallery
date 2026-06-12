#!/usr/bin/env python3
"""Cleanup legacy rollback orphan files (P5C).

P4B filename collision migration deliberately kept old winner
files as rollback safety. After P5A (content healing) and P5B
(first approved publish with the fix live on Pages), those
orphans are no longer needed and can be safely removed.

This script:
1. Reads web/data/artworks.json
2. Collects all currently-referenced paths (image_path, metadata_path,
   thumb_256, thumb_512)
3. Scans images/, metadata/, thumbs/256/, thumbs/512/ for files
   NOT referenced
4. Cross-checks against p5a-legacy-orphans-report.json (when present)
   to ensure we're not deleting more than expected
5. Defaults to dry-run; --apply is required to actually delete

Safety:
- --dry-run is the default
- --apply must be explicit
- --expected-count defaults to 46 (the P5A audit count); refuses
  to proceed if actual count mismatches (in --apply mode)
- Never touches: dist/, digests/, reports/, logs/, web/data/, index/,
  inbox/, scripts/, docs/
- Never commits the result JSON (caller's responsibility)
- Writes the result to reports/runtime/ (gitignored in P5A)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

WEB_DATA = ROOT / "web" / "data" / "artworks.json"
SCAN_DIRS = [
    ROOT / "images",
    ROOT / "metadata",
    ROOT / "thumbs" / "256",
    ROOT / "thumbs" / "512",
]
PROTECTED_TOP_DIRS = {
    "dist", "digests", "reports", "logs", "web", "index", "inbox",
    "scripts", "docs", ".git", ".github", "examples",
}
REPORTS_DIR = ROOT / "reports" / "runtime"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
META_EXT = {".json"}


def _normalize_rel(p: str | Path) -> str:
    """Normalize a reference path: strip leading './' and '../'."""
    s = str(p).replace("\\", "/")
    # drop leading ./ and ../
    while s.startswith("./"):
        s = s[2:]
    while s.startswith("../"):
        s = s[3:]
    return s.lstrip("/")


def collect_referenced_paths() -> set[Path]:
    """Return the set of absolute paths currently referenced by web/data."""
    if not WEB_DATA.exists():
        print(f"WARN: {WEB_DATA} missing; treating as empty", file=sys.stderr)
        return set()

    web = json.loads(WEB_DATA.read_text(encoding="utf-8"))
    refs: set[Path] = set()
    for a in web:
        for key in ("image_path", "metadata_path", "thumb_256", "thumb_512"):
            rel = a.get(key, "")
            if not rel:
                continue
            rel = _normalize_rel(rel)
            # the rel paths in web are typically "./images/..." or
            # relative; resolve against ROOT
            abs_path = (ROOT / rel).resolve()
            refs.add(abs_path)
    return refs


def scan_orphans(referenced: set[Path]) -> tuple[list[Path], int]:
    """Walk SCAN_DIRS; return (orphan_files, total_size_bytes)."""
    orphans: list[Path] = []
    total = 0
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            # Only consider image or metadata files
            if p.suffix.lower() not in IMAGE_EXT and p.suffix.lower() not in META_EXT:
                continue
            try:
                rp = p.resolve()
            except Exception:
                continue
            if rp not in referenced:
                orphans.append(p)
                total += p.stat().st_size
    return sorted(orphans), total


def cross_check_p5a(orphans: list[Path]) -> dict[str, Any]:
    """If P5A report exists, verify orphan basenames match."""
    p5a_report = REPORTS_DIR / "p5a-legacy-orphans-report.json"
    if not p5a_report.exists():
        return {"p5a_report": "not_found", "match": "unknown"}
    p5a = json.loads(p5a_report.read_text(encoding="utf-8"))
    p5a_files: set[str] = set()
    for k in ("orphan_images", "orphan_metadata", "orphan_thumbs_256", "orphan_thumbs_512"):
        for rel in p5a.get(k, {}).get("files", []):
            p5a_files.add(Path(rel).name)
    # Match orphans by basename
    orphan_basenames = {p.name for p in orphans}
    only_in_current = sorted(orphan_basenames - p5a_files)
    only_in_p5a = sorted(p5a_files - orphan_basenames)
    return {
        "p5a_report": str(p5a_report.relative_to(ROOT)),
        "p5a_total_files": p5a.get("total_orphan_files"),
        "current_orphan_basenames": len(orphan_basenames),
        "only_in_current": only_in_current[:20],
        "only_in_p5a": only_in_p5a[:20],
        "match": "ok" if not only_in_current and not only_in_p5a else "mismatch",
    }


def cross_check_missing_refs(referenced: set[Path]) -> list[tuple[str, str]]:
    """Return list of (id, key) for any web record referencing a missing file."""
    if not WEB_DATA.exists():
        return []
    web = json.loads(WEB_DATA.read_text(encoding="utf-8"))
    missing: list[tuple[str, str]] = []
    for a in web:
        for key in ("image_path", "metadata_path", "thumb_256", "thumb_512"):
            rel = a.get(key, "")
            if not rel:
                continue
            rel = _normalize_rel(rel)
            abs_path = (ROOT / rel).resolve()
            if not abs_path.exists():
                missing.append((a.get("id", "<no-id>"), key))
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Cleanup legacy rollback orphan files (P5C)"
    )
    ap.add_argument(
        "--apply", action="store_true",
        help="Actually delete orphan files (default is dry-run)"
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Dry-run mode (this is the default; --dry-run is a no-op for clarity)"
    )
    ap.add_argument(
        "--expected-count", type=int, default=46,
        help="Expected orphan count (refuses apply if mismatch). "
             "Pass 0 to disable the check (use with care)."
    )
    ap.add_argument(
        "--json-out", type=Path, default=None,
        help="Write result JSON to this path (relative to repo root)"
    )
    args = ap.parse_args()

    mode = "apply" if args.apply else "dry-run"
    print(f"[*] P5C orphan cleanup · mode={mode}")

    # 1. Collect referenced
    referenced = collect_referenced_paths()
    print(f"[*] Currently referenced files: {len(referenced)}")

    # 2. Scan for orphans
    orphans, total_size = scan_orphans(referenced)
    print(f"[*] Found orphan files: {len(orphans)}")
    print(f"[*] Orphan total size:   {total_size} bytes "
          f"({total_size / 1024 / 1024:.2f} MB)")

    # 3. Cross-check missing referenced
    missing = cross_check_missing_refs(referenced)
    print(f"[*] Missing referenced files (pre-cleanup): {len(missing)}")
    if missing:
        print("    (these would be a problem - referenced but not on disk)")
        for m in missing[:5]:
            print(f"      {m}")

    # 4. Cross-check against P5A report
    cross = cross_check_p5a(orphans)
    print(f"[*] P5A cross-check: {cross.get('match')}")
    if cross.get("match") == "mismatch":
        print(f"    only_in_current: {cross.get('only_in_current')}")
        print(f"    only_in_p5a:     {cross.get('only_in_p5a')}")

    # 5. Sanity gate
    expected = args.expected_count
    if expected > 0 and len(orphans) != expected:
        msg = (f"orphan count {len(orphans)} != expected {expected}; "
               f"{'REFUSING to apply' if args.apply else 'dry-run continues'}")
        print(f"[!] {msg}")
        if args.apply:
            # Write report then exit non-zero
            result = {
                "mode": mode,
                "ts": datetime.now().isoformat(timespec="seconds"),
                "expected_count": expected,
                "actual_count": len(orphans),
                "orphan_count": len(orphans),
                "orphan_size_bytes": total_size,
                "missing_referenced_files": len(missing),
                "cross_check_p5a": cross,
                "orphans": [
                    {"path": str(p.relative_to(ROOT)), "size": p.stat().st_size}
                    for p in orphans
                ],
                "deleted_count": 0,
                "deleted_size_bytes": 0,
                "error": "count_mismatch",
            }
            if args.json_out:
                out = (ROOT / args.json_out).resolve()
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            return 2

    # 6. Apply or dry-run
    deleted = 0
    deleted_size = 0
    delete_errors: list[dict[str, str]] = []
    if args.apply:
        for p in orphans:
            try:
                size = p.stat().st_size
                p.unlink()
                deleted += 1
                deleted_size += size
            except Exception as e:
                delete_errors.append({
                    "path": str(p.relative_to(ROOT)),
                    "error": str(e),
                })
        print(f"[*] DELETED {deleted} files / {deleted_size} bytes")
        if delete_errors:
            print(f"[!] {len(delete_errors)} delete errors:")
            for e in delete_errors[:5]:
                print(f"    {e}")

        # Re-check missing referenced (post-cleanup)
        post_missing = cross_check_missing_refs(referenced)
        if post_missing:
            print(f"[!] POST-CLEANUP missing referenced: {len(post_missing)}")
            for m in post_missing[:5]:
                print(f"    {m}")
    else:
        # Dry-run: show first 10
        print("[*] Dry-run: would delete (first 10):")
        for p in orphans[:10]:
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            print(f"    {p.relative_to(ROOT)}  ({size} bytes)")

    # 7. Write result JSON (if requested)
    # Note: in apply mode, we capture deleted files BEFORE deletion
    # (we already collected them in `orphans` list)
    result = {
        "mode": mode,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "expected_count": expected,
        "actual_count": len(orphans),
        "orphan_count": len(orphans),
        "orphan_size_bytes": total_size,
        "missing_referenced_files_pre": len(missing),
        "cross_check_p5a": cross,
        "orphans": [
            {
                "path": str(p.relative_to(ROOT)),
                "size": p.stat().st_size if p.exists() else 0,
            }
            for p in orphans
        ],
        "deleted_count": deleted,
        "deleted_size_bytes": deleted_size,
        "delete_errors": delete_errors,
    }
    if args.apply:
        result["missing_referenced_files_post"] = len(cross_check_missing_refs(referenced))

    if args.json_out:
        out = (ROOT / args.json_out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[*] Result written: {out.relative_to(ROOT)}")

    # 8. Final status
    if not args.apply:
        print("\n[dry-run] pass --apply to actually delete")
    elif delete_errors:
        print(f"\n[apply] {deleted} deleted, {len(delete_errors)} errors")
        return 1
    elif missing:
        # Should never reach here if --apply was true and missing
        print("\n[apply] FAILED: missing referenced files detected")
        return 1
    else:
        print(f"\n[apply] PASS: {deleted} files deleted, {deleted_size} bytes freed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
