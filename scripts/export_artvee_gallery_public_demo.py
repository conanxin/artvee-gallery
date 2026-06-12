#!/usr/bin/env python3
"""
Artvee Gallery · Public Demo Exporter (P2)
============================================
读取 P1 生成的 web/data/*.json + thumbs/{256,512}/，导出精选静态 demo 到
dist/artvee-gallery-public-demo/，可被任意静态服务器托管。

设计要点：
  - 只读 P1 输出：从不修改 web/、thumbs/、web/data/
  - 不复制原图：public demo 不包含 images/ 1.4G
  - 路径改写：local 模式的 "../images/..." / "../thumbs/..." 改写为 "./assets/thumbs/..."
  - 详情页 fallback：image_path 直接指向 512 缩略图（用户要的是"看图"，不是"下原图"）
  - 保留 source_url：详情面板仍可跳回 artvee.com 原页面
  - 精选策略：recent (按 downloaded_at 倒序) / diverse (按 category 轮转)
  - 退出码：0 ok / 2 source missing / 3 strategy 错误
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DATA = BASE_DIR / "web" / "data"
SRC_THUMBS_256 = BASE_DIR / "thumbs" / "256"
SRC_THUMBS_512 = BASE_DIR / "thumbs" / "512"
SRC_WEB = BASE_DIR / "web"
DEFAULT_OUT = BASE_DIR / "dist" / "artvee-gallery-public-demo"


# ---------- IO helpers ----------

def load_json(path: Path):
    if not path.exists():
        print(f"ERROR: source not found: {path}", file=sys.stderr)
        sys.exit(2)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------- selection strategies ----------

def select_recent(arts: list[dict], limit: int) -> list[dict]:
    """Sort by downloaded_at desc; ties broken by id for stability."""
    return sorted(
        arts,
        key=lambda a: (a.get("downloaded_at") or "", a.get("id") or ""),
        reverse=True,
    )[:limit]


def select_diverse(arts: list[dict], limit: int) -> list[dict]:
    """Round-robin by category, then by downloaded_at desc within each category."""
    by_cat: dict[str, list[dict]] = {}
    for a in arts:
        cat = a.get("category") or "uncategorized"
        by_cat.setdefault(cat, []).append(a)
    for cat in by_cat:
        by_cat[cat].sort(
            key=lambda a: (a.get("downloaded_at") or "", a.get("id") or ""),
            reverse=True,
        )
    # Round-robin: pop one from each non-empty bucket in turn
    queues = {cat: deque(items) for cat, items in by_cat.items()}
    order = sorted(queues.keys())  # stable order
    picked: list[dict] = []
    while queues and len(picked) < limit:
        progress = False
        for cat in order:
            if not queues[cat]:
                continue
            picked.append(queues[cat].popleft())
            progress = True
            if len(picked) >= limit:
                break
        if not progress:
            break
    return picked


STRATEGIES = {
    "recent": select_recent,
    "diverse": select_diverse,
}


# ---------- path rewriting ----------

def rewrite_paths(record: dict, base_url: str) -> dict:
    """
    P1 record may have:
      - thumb_256 / thumb_512: "../thumbs/256|512/<basename>.jpg"  (local mode)
      - image_path:             "../images/<category>/<basename>.jpg" (P1 local)
      - metadata_path:          "../metadata/<basename>.json" (P1 local)

    Public demo record (after rewrite):
      - thumb_256 / thumb_512: "<base_url>/assets/thumbs/256|512/<basename>.jpg"
      - image_path:            "<base_url>/assets/thumbs/512/<basename>.jpg"  (fallback to 512)
      - metadata_path:         DROPPED (the public demo has no metadata/ folder; the
                               front-end shows "—" if empty, which is the correct UX)
      - source_url:            kept verbatim (https://artvee.com/...)
    """
    base = base_url.rstrip("/") if base_url else "."

    def _aset(path: str, size: int) -> str:
        # Convert "../thumbs/256/xxx.jpg" → "<base>/assets/thumbs/256/xxx.jpg"
        if not path:
            return ""
        filename = Path(path).name
        return f"{base}/assets/thumbs/{size}/{filename}"

    r = dict(record)  # shallow copy
    r["thumb_256"] = _aset(record.get("thumb_256", ""), 256)
    r["thumb_512"] = _aset(record.get("thumb_512", ""), 512)
    # image_path: in P1 it's the local original; for public demo we point at the 512 thumb.
    # If the source record had image_path under images/ we replace it; if it was already
    # empty, leave empty.
    src_image = record.get("image_path", "")
    if src_image:
        r["image_path"] = _aset(src_image, 512)
    else:
        r["image_path"] = r["thumb_512"]
    # P4D: drop metadata_path from public export. It points at local
    # "../metadata/<basename>.json" which (a) leaks the source-machine folder
    # layout in the public JSON, and (b) the public demo does not actually ship
    # any metadata/ folder, so the path is dangling. The front-end shows "—"
    # for a missing metadata_path, which is the correct public-demo UX.
    r.pop("metadata_path", None)
    # source_url and other fields pass through unchanged
    return r


# ---------- main export ----------

def export(
    out_dir: Path,
    limit: int,
    strategy: str,
    base_url: str,
    dry_run: bool,
    exclude_duplicate_source_url_groups: bool = False,
    require_unique_source_url: bool = False,
    exclude_risk: str | None = None,
    visual_qa_path: Path | None = None,
    require_prompt_fields: bool = False,
) -> int:
    out_dir = out_dir.resolve()
    if strategy not in STRATEGIES:
        print(f"ERROR: unknown --strategy={strategy}. Choose from: {list(STRATEGIES)}", file=sys.stderr)
        return 3

    arts_all = load_json(SRC_DATA / "artworks.json")
    stats_src = load_json(SRC_DATA / "gallery_stats.json")

    # P4D public-safety guard: if requested, drop every record whose source_url
    # is shared with another record in the *global* web/data. This skips entire
    # groups so the public demo never publishes a known buggy URL label.
    if exclude_duplicate_source_url_groups:
        url_counts: Counter = Counter(a.get("source_url", "") for a in arts_all)
        duplicated = {url for url, c in url_counts.items() if c > 1 and url}
        before = len(arts_all)
        arts_all = [a for a in arts_all if a.get("source_url", "") not in duplicated]
        after = len(arts_all)
        print(f"[guard] --exclude-duplicate-source-url-groups: "
              f"dropped {before - after} record(s) across {len(duplicated)} duplicated source_url group(s)")

    selector = STRATEGIES[strategy]
    picked = selector(arts_all, limit)
    if not picked:
        print("ERROR: selected 0 records (source is empty after guards?)", file=sys.stderr)
        return 2

    # P4D public-safety guard: if requested, after selection, ensure no
    # source_url appears more than once in the picked set. Otherwise refuse.
    if require_unique_source_url:
        picked_urls = Counter(a.get("source_url", "") for a in picked)
        dupes = {url: c for url, c in picked_urls.items() if c > 1 and url}
        if dupes:
            print(f"ERROR: --require-unique-source-url failed: "
                  f"{len(dupes)} duplicated source_url(s) in selected set. "
                  f"First 3: {list(dupes.items())[:3]}", file=sys.stderr)
            return 4

    # P5E visual-QA risk guard. If a visual-QA JSON is provided and
    # --exclude-risk is set, look up the risk_level for each picked record
    # and drop any that meet the threshold. Records without a risk_level
    # in the QA output pass through (defensive: do not punish records that
    # have not been audited yet).
    if exclude_risk and visual_qa_path:
        qa_path = visual_qa_path.resolve()
        if not qa_path.exists():
            print(f"WARN: --exclude-risk {exclude_risk} requested but "
                  f"visual QA file not found: {qa_path}. Proceeding without filter.",
                  file=sys.stderr)
        else:
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            qa_by_id: dict[str, str] = {}
            for rec in qa.get("records", []):
                rid = rec.get("id", "")
                lvl = rec.get("risk_level", "none")
                if rid:
                    qa_by_id[rid] = lvl
            risk_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
            threshold = risk_rank.get(exclude_risk, 3)
            before = len(picked)
            kept: list[dict] = []
            dropped_ids: list[str] = []
            for a in picked:
                rid = a.get("id", "")
                lvl = qa_by_id.get(rid, "none")
                if risk_rank.get(lvl, 0) >= threshold:
                    dropped_ids.append(f"{rid}({lvl})")
                else:
                    kept.append(a)
            picked = kept
            print(f"[guard] --exclude-risk {exclude_risk}: dropped "
                  f"{before - len(picked)} record(s); kept {len(picked)}. "
                  f"Dropped: {dropped_ids[:5]}{'...' if len(dropped_ids) > 5 else ''}")
            if not picked:
                print("ERROR: --exclude-risk removed all candidates; cannot export.",
                      file=sys.stderr)
                return 5

    # P5E prompt-fields guard. If --require-prompt-fields is set, drop
    # any record that has *any* of the optional prompt fields
    # (prompt_seed, use_cases, visual_notes) but leaves one of them
    # empty. Records with none of these fields pass through
    # (defensive: the public demo gallery JSON is not required to
    # surface prompt metadata; the digest is).
    if require_prompt_fields:
        PROMPT_FIELDS = ("prompt_seed", "use_cases", "visual_notes")
        before = len(picked)
        kept: list[dict] = []
        dropped: list[str] = []
        for a in picked:
            present = [f for f in PROMPT_FIELDS if f in a]
            if not present:
                kept.append(a)
                continue
            empty = [f for f in present if not a.get(f)]
            if isinstance(a.get("use_cases"), list) and len(a["use_cases"]) == 0:
                empty.append("use_cases")
            if empty:
                dropped.append(f"{a.get('id')}({','.join(empty)})")
            else:
                kept.append(a)
        picked = kept
        print(f"[guard] --require-prompt-fields: dropped "
              f"{before - len(picked)} record(s); kept {len(picked)}. "
              f"Dropped: {dropped[:5]}{'...' if len(dropped) > 5 else ''}")
        if not picked:
            print("ERROR: --require-prompt-fields removed all candidates; cannot export.",
                  file=sys.stderr)
            return 6

    # Verify all needed thumbs exist
    missing: list[tuple[str, int]] = []
    for a in picked:
        stem = a.get("id") or Path(a.get("image_path", "")).stem
        for sz in (256, 512):
            src = (SRC_THUMBS_256 if sz == 256 else SRC_THUMBS_512) / f"{stem}.jpg"
            if not src.exists():
                missing.append((stem, sz))
    if missing:
        sample = missing[:5]
        print(f"ERROR: {len(missing)} thumb(s) missing. First 5: {sample}", file=sys.stderr)
        return 2

    # Rewrite records
    exported = [rewrite_paths(a, base_url) for a in picked]

    if dry_run:
        print(f"[dry-run] would write to: {out_dir}")
        print(f"[dry-run] {len(exported)} records, strategy={strategy}")
        cats = Counter(r.get("category") for r in exported)
        print(f"[dry-run] category distribution: {dict(cats)}")
        for sz in (256, 512):
            total = sum((out_dir / f"assets/thumbs/{sz}").glob("*.jpg") for _ in [0]) if False else 0
            # estimate: we will copy len(exported) files per size
            print(f"[dry-run] thumbs {sz}: would copy {len(exported)} files")
        return 0

    # Materialize
    out_assets_thumbs = out_dir / "assets" / "thumbs"
    (out_assets_thumbs / "256").mkdir(parents=True, exist_ok=True)
    (out_assets_thumbs / "512").mkdir(parents=True, exist_ok=True)
    (out_dir / "data").mkdir(parents=True, exist_ok=True)

    # Copy web/* (index.html, app.js, style.css). For index.html we do a
    # text-level patch to swap the LOCAL-only subtitle
    # ("本地图库浏览 · 数据来自 index/artworks.csv + metadata/") for a
    # public-safe one that does not contain the forbidden substrings
    # `metadata/` or `images/`.
    for name in ("index.html", "app.js", "style.css"):
        src = SRC_WEB / name
        if not src.exists():
            print(f"ERROR: missing web file: {src}", file=sys.stderr)
            return 2
        if name == "index.html":
            html = src.read_text(encoding="utf-8")
            PUBLIC_SUBTITLE = (
                "Artvee Gallery · Public Demo · "
                "数据来自 artvee.com 公共领域艺术作品库"
            )
            html = html.replace(
                "本地图库浏览 · 数据来自 index/artworks.csv + metadata/",
                PUBLIC_SUBTITLE,
            )
            (out_dir / name).write_text(html, encoding="utf-8")
        else:
            shutil.copy2(src, out_dir / name)

    # Copy selected thumbs only
    copied_256 = 0
    copied_512 = 0
    for a in exported:
        stem = a["id"]
        for sz in (256, 512):
            src = (SRC_THUMBS_256 if sz == 256 else SRC_THUMBS_512) / f"{stem}.jpg"
            dst = out_assets_thumbs / str(sz) / f"{stem}.jpg"
            shutil.copy2(src, dst)
            if sz == 256:
                copied_256 += 1
            else:
                copied_512 += 1

    # Write data/*.json
    (out_dir / "data" / "artworks.json").write_text(
        json.dumps(exported, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Build demo-specific stats
    demo_stats = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "public-demo",
        "base_url": base_url,
        "source": {
            "schema": "artvee-gallery/v1",
            "strategy": strategy,
            "limit": limit,
            "full_counts": stats_src.get("counts", {}),
        },
        "counts": {
            "artworks": len(exported),
            "categories": len({a.get("category") for a in exported if a.get("category")}),
            "artists": len({a.get("artist") for a in exported if a.get("artist")}),
            "thumb_256_total": copied_256,
            "thumb_512_total": copied_512,
        },
        "last_downloaded_at": max(
            (a.get("downloaded_at") or "" for a in exported), default=""
        ),
        "categories": dict(Counter(a.get("category") for a in exported if a.get("category")).most_common()),
    }
    (out_dir / "data" / "gallery_stats.json").write_text(
        json.dumps(demo_stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Report
    cats = Counter(r.get("category") for r in exported)
    print(f"[✓] exported {len(exported)} records (strategy={strategy})")
    print(f"[✓] wrote: {out_dir}/")
    print(f"    ├─ index.html, app.js, style.css  (copied from web/)")
    print(f"    ├─ data/artworks.json, gallery_stats.json")
    print(f"    └─ assets/thumbs/{{256,512}}/  {copied_256} + {copied_512} files")
    print(f"[i] category distribution: {dict(cats)}")
    print(f"[i] base-url: {base_url!r}")
    if exclude_duplicate_source_url_groups:
        print(f"[i] guard: --exclude-duplicate-source-url-groups was active")
    if require_unique_source_url:
        print(f"[i] guard: --require-unique-source-url was active (post-check PASS)")
    if exclude_risk:
        print(f"[i] guard: --exclude-risk {exclude_risk} was active (visual QA: {visual_qa_path})")
    if require_prompt_fields:
        print(f"[i] guard: --require-prompt-fields was active")
    print(f"[i] preview: cd {out_dir} && python3 -m http.server 8890")
    return 0


def main():
    p = argparse.ArgumentParser(description="Artvee Public Demo Exporter")
    p.add_argument("--limit", type=int, default=100,
                   help="Max records to include in the demo (default: 100). "
                        "If --exclude-duplicate-source-url-groups is set, the effective "
                        "limit may be lower because filtered groups reduce the pool.")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT,
                   help=f"Output directory (default: {DEFAULT_OUT})")
    p.add_argument("--base-url", default=".",
                   help="Base URL prefix for asset paths in the exported JSON "
                        "(default: '.' = relative; use 'https://cdn.example.com/artvee' for public CDN)")
    p.add_argument("--strategy", choices=list(STRATEGIES.keys()), default="recent",
                   help="Selection strategy: recent (default) | diverse")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be exported without writing anything")
    p.add_argument("--exclude-duplicate-source-url-groups",
                   action="store_true",
                   help="Public-safety guard (P4D). Before selection, scan the full "
                        "web/data/artworks.json for source_url values that map to "
                        "multiple records, and exclude those entire groups from the "
                        "export. Useful when the source data has a known build-script "
                        "label bug (e.g. P4A+1 § 6.4 Le_rêve source_url mismatch) "
                        "where the *image* is correct but the *source_url label* is "
                        "wrong. Skipping the whole group keeps the public demo clean "
                        "until the build bug is fixed (P5+).")
    p.add_argument("--require-unique-source-url",
                   action="store_true",
                   help="Public-safety guard (P4D). After selection, refuse to write "
                        "the export if the selected records contain any source_url "
                        "more than once. Exits non-zero. Pairs naturally with "
                        "--exclude-duplicate-source-url-groups so the export cannot "
                        "leak the bug by accident.")
    p.add_argument("--exclude-risk", choices=("low", "medium", "high"),
                   default=None,
                   help="Visual-QA guard (P5E). After selection, drop every record "
                        "whose risk_level in the visual-QA JSON is at or above the "
                        "given threshold. Requires --visual-qa. Records with no "
                        "risk_level (not yet audited) pass through. Use 'high' to "
                        "only exclude clearly broken images; 'medium' also demotes "
                        "tiny files / near-monochrome / extreme-aspect records.")
    p.add_argument("--visual-qa", type=Path, default=None,
                   help="Path to a P5D visual-QA JSON (records[].risk_level). "
                        "Required when --exclude-risk is set. "
                        "Default: reports/runtime/p5d-visual-qa-full.json")
    p.add_argument("--require-prompt-fields", action="store_true",
                   help="P5E curation guard. Drop any record that has at least "
                        "one of (prompt_seed, use_cases, visual_notes) and leaves "
                        "any of those empty. Records with none of these fields "
                        "pass through (defensive — the public demo JSON is not "
                        "required to surface prompt metadata).")
    args = p.parse_args()

    # Default --visual-qa path if --exclude-risk is set and no explicit path
    if args.exclude_risk and not args.visual_qa:
        default_qa = (BASE_DIR / "reports" / "runtime" / "p5d-visual-qa-full.json").resolve()
        args.visual_qa = default_qa

    return export(
        args.out_dir, args.limit, args.strategy, args.base_url, args.dry_run,
        exclude_duplicate_source_url_groups=args.exclude_duplicate_source_url_groups,
        require_unique_source_url=args.require_unique_source_url,
        exclude_risk=args.exclude_risk,
        visual_qa_path=args.visual_qa,
        require_prompt_fields=args.require_prompt_fields,
    )


if __name__ == "__main__":
    sys.exit(main())
