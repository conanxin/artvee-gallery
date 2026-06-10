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

    Public demo record (after rewrite):
      - thumb_256 / thumb_512: "<base_url>/assets/thumbs/256|512/<basename>.jpg"
      - image_path:            "<base_url>/assets/thumbs/512/<basename>.jpg"  (fallback to 512)
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
    # source_url and other fields pass through unchanged
    return r


# ---------- main export ----------

def export(out_dir: Path, limit: int, strategy: str, base_url: str, dry_run: bool) -> int:
    out_dir = out_dir.resolve()
    if strategy not in STRATEGIES:
        print(f"ERROR: unknown --strategy={strategy}. Choose from: {list(STRATEGIES)}", file=sys.stderr)
        return 3

    arts_all = load_json(SRC_DATA / "artworks.json")
    stats_src = load_json(SRC_DATA / "gallery_stats.json")

    selector = STRATEGIES[strategy]
    picked = selector(arts_all, limit)
    if not picked:
        print("ERROR: selected 0 records (source is empty?)", file=sys.stderr)
        return 2

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

    # Copy web/* (index.html, app.js, style.css)
    for name in ("index.html", "app.js", "style.css"):
        src = SRC_WEB / name
        if not src.exists():
            print(f"ERROR: missing web file: {src}", file=sys.stderr)
            return 2
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
    print(f"[i] preview: cd {out_dir} && python3 -m http.server 8890")
    return 0


def main():
    p = argparse.ArgumentParser(description="Artvee Public Demo Exporter")
    p.add_argument("--limit", type=int, default=100,
                   help="Max records to include in the demo (default: 100)")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT,
                   help=f"Output directory (default: {DEFAULT_OUT})")
    p.add_argument("--base-url", default=".",
                   help="Base URL prefix for asset paths in the exported JSON "
                        "(default: '.' = relative; use 'https://cdn.example.com/artvee' for public CDN)")
    p.add_argument("--strategy", choices=list(STRATEGIES.keys()), default="recent",
                   help="Selection strategy: recent (default) | diverse")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be exported without writing anything")
    args = p.parse_args()

    return export(args.out_dir, args.limit, args.strategy, args.base_url, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
