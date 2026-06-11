#!/usr/bin/env python3
"""
Artvee Gallery Builder (P1)
============================
从 index/artworks.csv + metadata/*.json + images/ 生成：
  - thumbs/256/<basename>.jpg
  - thumbs/512/<basename>.jpg
  - web/data/artworks.json     (扁平记录数组，UI 消费)
  - web/data/gallery_stats.json (顶部统计：总数 / 分类 / 艺术家 / 最近更新)

设计要点：
  - 纯只读源数据：从不修改 images/、metadata/、index/artworks.csv
  - 增量构建：已存在缩略图自动跳过；只补缺失的
  - 路径模式可切换：local (相对路径，浏览器直接 ../images/...) 或 public (--base-url 拼绝对)
  - 退出码：成功 0，源数据缺失 2，依赖缺失 3
  - 性能：740 张一次 ~30s；失败单条不中断

安全：所有 .write 都是新文件/新目录，不会污染源数据。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_CSV = BASE_DIR / "index" / "artworks.csv"
METADATA_DIR = BASE_DIR / "metadata"
IMAGES_DIR = BASE_DIR / "images"
THUMBS_256_DIR = BASE_DIR / "thumbs" / "256"
THUMBS_512_DIR = BASE_DIR / "thumbs" / "512"
WEB_DATA_DIR = BASE_DIR / "web" / "data"
ARTWORKS_JSON = WEB_DATA_DIR / "artworks.json"
STATS_JSON = WEB_DATA_DIR / "gallery_stats.json"

THUMB_SIZES = (256, 512)
THUMB_QUALITY = 82

# ---------- IO helpers ----------

def read_artworks_index() -> list[dict[str, str]]:
    if not INDEX_CSV.exists():
        print(f"ERROR: index file not found: {INDEX_CSV}", file=sys.stderr)
        sys.exit(2)
    rows: list[dict[str, str]] = []
    with INDEX_CSV.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if any((v or "").strip() for v in row.values()):
                rows.append(row)
    return rows


def read_metadata(meta_rel_path: str) -> dict[str, Any] | None:
    """Try to read the metadata JSON pointed to by index. Return None on miss."""
    if not meta_rel_path:
        return None
    p = BASE_DIR / meta_rel_path
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARN: failed to read metadata {p}: {e}", file=sys.stderr)
        return None


def ensure_pillow():
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        print("ERROR: Pillow is required. Try: pip install Pillow", file=sys.stderr)
        return False


# ---------- thumbnail generation ----------

def make_thumb(src_path: Path, dst_path: Path, size: int) -> str:
    """
    Generate dst_path from src_path at the given max-edge size.
    Returns "created" | "skipped" | "error".
    Does not raise.
    """
    if dst_path.exists() and dst_path.stat().st_size > 0:
        return "skipped"
    try:
        from PIL import Image
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src_path) as im:
            im = im.convert("RGB") if im.mode in ("P", "RGBA", "LA") and not _has_alpha(im) else im
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.thumbnail((size, size), Image.Resampling.LANCZOS)
            im.save(dst_path, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return "created"
    except Exception as e:
        print(f"WARN: thumb fail {src_path} -> {dst_path}: {e}", file=sys.stderr)
        return "error"


def _has_alpha(im) -> bool:
    return im.mode in ("RGBA", "LA", "P") and "A" in (im.getbands() if hasattr(im, "getbands") else ())


# ---------- path mode ----------

def path_for(rel_path: str, mode: str, base_url: str | None) -> str:
    """Convert a project-relative path to either a ../-style local path or an absolute URL."""
    if not rel_path:
        return ""
    rel = rel_path.lstrip("./")
    if mode == "public":
        if not base_url:
            print("ERROR: --base-url required for --mode public", file=sys.stderr)
            sys.exit(2)
        return base_url.rstrip("/") + "/" + rel
    # local mode: prepend ../../ because web/index.html sits under web/
    return "../" + rel


# ---------- main build ----------

def build(mode: str, base_url: str | None, limit: int | None) -> int:
    if not ensure_pillow():
        return 3

    THUMBS_256_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_512_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_artworks_index()
    if limit is not None:
        rows = rows[:limit]
    print(f"[*] processing {len(rows)} artwork(s) (limit={limit})")

    artworks: list[dict[str, Any]] = []
    counters: dict[str, Counter] = {"created": Counter(), "skipped": Counter(), "error": Counter()}

    for i, row in enumerate(rows, start=1):
        img_rel = (row.get("local_image_path") or "").strip()
        meta_rel = (row.get("metadata_path") or "").strip()
        if not img_rel:
            print(f"  [{i}] SKIP (no image_path): {(row.get('source_url') or '')[:60]}")
            continue

        img_path = BASE_DIR / img_rel
        if not img_path.exists():
            print(f"  [{i}] SKIP (image missing on disk): {img_rel}")
            continue

        # basename without extension for thumbnail file naming
        stem = Path(img_rel).stem
        meta = read_metadata(meta_rel) or {}

        # Build artwork record
        record = {
            "id": stem,
            "title": (meta.get("title") or row.get("title") or "").strip(),
            "artist": (meta.get("artist") or row.get("artist") or "").strip(),
            "category": (meta.get("category") or row.get("category") or "").strip(),
            "download_variant": (meta.get("download_variant") or row.get("download_variant") or "standard").strip(),
            "tags": (meta.get("tags") or row.get("tags") or "").strip(),
            "usage_note": (meta.get("usage_note") or row.get("usage_note") or "").strip(),
            "source_url": (meta.get("url") or row.get("source_url") or "").strip(),
            "source": (meta.get("source") or "artvee").strip(),
            "downloaded_at": (meta.get("downloaded_at") or "").strip(),
            "image_path": path_for(img_rel, mode, base_url),
            "thumb_256": "",
            "thumb_512": "",
            "metadata_path": path_for(meta_rel, mode, base_url) if meta_rel else "",
        }

        # Generate thumbs
        for size in THUMB_SIZES:
            dst = (THUMBS_256_DIR if size == 256 else THUMBS_512_DIR) / (stem + ".jpg")
            status = make_thumb(img_path, dst, size)
            counters[status][size] += 1
            if status == "created":
                # thumb paths are always relative (../thumbs/...)
                record[f"thumb_{size}"] = f"../thumbs/{size}/{stem}.jpg"

        # If thumbs already existed, they are still reachable
        if not record["thumb_256"]:
            t256 = (THUMBS_256_DIR / (stem + ".jpg"))
            if t256.exists():
                record["thumb_256"] = f"../thumbs/256/{stem}.jpg"
        if not record["thumb_512"]:
            t512 = (THUMBS_512_DIR / (stem + ".jpg"))
            if t512.exists():
                record["thumb_512"] = f"../thumbs/512/{stem}.jpg"

        artworks.append(record)

    # Write outputs
    ARTWORKS_JSON.write_text(
        json.dumps(artworks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Stats
    category_counts = Counter(a["category"] for a in artworks if a["category"])
    artist_counts = Counter(a["artist"] for a in artworks if a["artist"])
    timestamps = [a["downloaded_at"] for a in artworks if a["downloaded_at"]]
    timestamps.sort()
    last_update = timestamps[-1] if timestamps else ""

    stats = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "base_url": base_url or "",
        "counts": {
            "artworks": len(artworks),
            "categories": len(category_counts),
            "artists": len(artist_counts),
            "thumb_256_total": counters["created"][256] + counters["skipped"][256] + counters["error"][256],
            "thumb_512_total": counters["created"][512] + counters["skipped"][512] + counters["error"][512],
        },
        "thumb_results": {
            "created": dict(counters["created"]),
            "skipped": dict(counters["skipped"]),
            "errors": dict(counters["error"]),
        },
        "last_downloaded_at": last_update,
        "categories": dict(category_counts.most_common()),
        "top_artists": dict(artist_counts.most_common(15)),
    }
    STATS_JSON.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"[✓] wrote {ARTWORKS_JSON.relative_to(BASE_DIR)} "
        f"({len(artworks)} records)"
    )
    print(
        f"[✓] wrote {STATS_JSON.relative_to(BASE_DIR)} "
        f"(thumbs: 256 +{counters['created'][256]} skipped {counters['skipped'][256]}, "
        f"512 +{counters['created'][512]} skipped {counters['skipped'][512]})"
    )
    if any(counters["error"].values()):
        print(
            f"[!] thumb errors: "
            + ", ".join(f"{sz}={n}" for sz, n in counters["error"].items() if n),
            file=sys.stderr,
        )
    return 0


def main():
    p = argparse.ArgumentParser(description="Artvee Gallery Builder")
    p.add_argument("--mode", choices=["local", "public"], default="local",
                   help="local: relative paths (../images/...) ; public: --base-url prefixed")
    p.add_argument("--base-url", default=None, help="Required when --mode=public, e.g. https://cdn.example.com/artvee")
    p.add_argument("--limit", type=int, default=None, help="Process only the first N records (for testing)")
    p.add_argument("--dry-run", action="store_true", help="Reserved; current builder is non-destructive so this is a no-op")
    args = p.parse_args()

    if args.mode == "public" and not args.base_url:
        p.error("--base-url is required when --mode=public")

    t0 = time.time()
    rc = build(args.mode, args.base_url, args.limit)
    print(f"[*] done in {time.time() - t0:.1f}s")
    return rc


if __name__ == "__main__":
    sys.exit(main())
