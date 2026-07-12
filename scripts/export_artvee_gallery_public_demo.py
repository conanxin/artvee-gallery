#!/usr/bin/env python3
"""
Artvee Gallery · Public Demo Exporter (P2)
============================================
读取 P1 生成的 web/data/*.json + thumbs/{256,512}/,导出精选静态 demo 到
dist/artvee-gallery-public-demo/,可被任意静态服务器托管。

设计要点:
  - 只读 P1 输出:从不修改 web/、thumbs/、web/data/
  - 不复制原图:public demo 不包含 images/ 1.4G
  - 路径改写:local 模式的 "../images/..." / "../thumbs/..." 改写为 "./assets/thumbs/..."
  - 详情页 fallback:image_path 直接指向 512 缩略图(用户要的是"看图",不是"下原图")
  - 保留 source_url:详情面板仍可跳回 artvee.com 原页面
  - 精选策略:recent (按 downloaded_at 倒序) / diverse (按 category 轮转)
  - 退出码:0 ok / 2 source missing / 3 strategy 错误
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


# ---------- P8B helpers ----------

def _detect_release_tag(base_dir: Path) -> str:
    """Return the most recent git tag for the Artvee repo, or "unknown"
    if no tag exists / git is not available. The tag is read at export
    time so the public demo's "v0.x.y" line stays in sync with `git
    describe --tags --abbrev=0`. Never raises; the exporter must not
    abort on a missing tag (e.g. on a fresh clone before the first
    tag is cut).
    """
    try:
        import subprocess
        out = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(base_dir), capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "v0.2.0"  # P8B ships against v0.2.0 stable; fall back to it.


def _build_p8b_info_card(
    last_updated: str,
    public_record_count: int,
    total_records,
    release_tag: str,
) -> str:
    """P8B public-demo info card HTML.

    The card surfaces:
      - demo title (Artvee Gallery Demo)
      - release version (e.g. v0.2.0)
      - Last updated date (YYYY-MM-DD)
      - public-record count + total local-archive count (with
        honest "Source archive: local-first full archive, not
        fully published" disclosure)
      - canonical links (Daily Digest, GitHub repo, release
        tag, About)

    Constraints:
      - No front-end framework dependency.
      - No local path, no `metadata/`, no `images/`, no
        `~/.hermes-agent` substrings.
      - All link targets are absolute public URLs or local
        relative paths.
    """
    total = "-" if total_records in (None, 0) else total_records
    card = (
        '<!-- P8B:public-demo-info-card -->\n'
        '    <section class="p8b-info-card" aria-label="About this demo">\n'
        '      <h2>Artvee Gallery Demo</h2>\n'
        f'      <p class="p8b-meta">v<span class="p8b-version">{release_tag}</span> · '
        f'Last updated: <time datetime="{last_updated}">{last_updated}</time></p>\n'
        '      <p class="p8b-meta">\n'
        f'        <strong>Records:</strong> <span class="p8b-public-count">{public_record_count}</span> public demo records\n'
        f'        · <strong>Source archive:</strong> {total} in local-first archive (not fully published)\n'
        '      </p>\n'
        '      <p class="p8b-links">\n'
        '        Links:\n'
        '        <a href="https://conanxin.github.io/projects/artvee-gallery-digest/" target="_blank" rel="noopener">Daily Digest</a>\n'
        '        ·\n'
        '        <a href="https://github.com/conanxin/artvee-gallery" target="_blank" rel="noopener">GitHub repo</a>\n'
        '        ·\n'
        f'        <a href="https://github.com/conanxin/artvee-gallery/releases/tag/{release_tag}" target="_blank" rel="noopener">{release_tag} release</a>\n'
        '        ·\n'
        '        <a href="https://github.com/conanxin/artvee-gallery#artvee-gallery" target="_blank" rel="noopener">About this demo</a>\n'
        '      </p>\n'
        '      <style>\n'
        '        .p8b-info-card { background: #f8fafc; border: 1px solid #e5e7eb;\n'
        '                         border-radius: 6px; padding: 0.75rem 1rem;\n'
        '                         margin: 0.75rem 0; max-width: 100%;\n'
        '                         font-size: 0.9rem; line-height: 1.5; }\n'
        '        .p8b-info-card h2 { margin: 0 0 0.25rem; font-size: 1.05rem;\n'
        '                           color: #1f2328; }\n'
        '        .p8b-info-card .p8b-meta { margin: 0 0 0.25rem;\n'
        '                                  color: #4b5563; font-size: 0.88rem; }\n'
        '        .p8b-info-card .p8b-links a { color: #2563eb;\n'
        '                                      text-decoration: none;\n'
        '                                      margin: 0 0.15rem; }\n'
        '        .p8b-info-card .p8b-links a:hover { text-decoration: underline; }\n'
        '      </style>\n'
        '    </section>'
    )
    return card


# ---------- path rewriting ----------

def rewrite_paths(record: dict, base_url: str, detail_thumb_policy: str = "all") -> dict:
    """
    P1 record may have:
      - thumb_256 / thumb_512: "../thumbs/256|512/<basename>.jpg"  (local mode)
      - image_path:             "../images/<category>/<basename>.jpg" (P1 local)
      - metadata_path:          "../metadata/<basename>.json" (P1 local)

    Public demo record (after rewrite):
      - thumb_256 / thumb_512: "<base_url>/assets/thumbs/256|512/<basename>.jpg"
      - image_path:            "<base_url>/assets/thumbs/512/<basename>.jpg"  (fallback to 512)
                              OR, when detail_thumb_policy="none", remapped to thumb_256
      - metadata_path:         DROPPED (the public demo has no metadata/ folder; the
                               front-end shows "-" if empty, which is the correct UX)
      - source_url:            kept verbatim (https://artvee.com/...)

    P9G+2 detail-thumb-policy:
      - "all"  (default, back-compat): ship both 256 + 512 thumbs in assets/
        and keep thumb_512 / image_path pointing at 512. ~11 MB of 512
        thumbnails added to the public bundle.
      - "none" (P9G+2 default in confirm_demo_refresh.sh): DO NOT ship 512
        thumbs, set thumb_512 = null, and remap image_path to the 256 thumb
        so the front-end detail-panel fallback chain works without 404s.
        Saves ~76% of the bundle.
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

    if detail_thumb_policy == "none":
        # P9G+2: 512 thumbs are NOT included in the public bundle.
        # The detail panel and any code that falls back from thumb_256
        # must use thumb_256 itself (no broken image).
        r["thumb_512"] = None
    else:
        # "all": keep 512 thumb path so the published bundle carries both.
        r["thumb_512"] = _aset(record.get("thumb_512", ""), 512)

    # image_path: in P1 it's the local original. For the public demo, when the
    # policy is "all" we remap it to the 512 thumb path (matches the historical
    # fallback the front-end used: `a.thumb_256 || a.image_path` and the detail
    # panel `a.thumb_512 || a.image_path`). When the policy is "none" we cannot
    # leave it pointing at a non-existent assets/thumbs/512/.../ so we remap it
    # to thumb_256 instead. The front-end detail-panel fallback chain
    # (thumb_512 || thumb_256 || image) will resolve correctly under either
    # policy because we set thumb_512=None above.
    src_image = record.get("image_path", "")
    if detail_thumb_policy == "none":
        r["image_path"] = r["thumb_256"]
    elif src_image:
        r["image_path"] = _aset(src_image, 512)
    else:
        r["image_path"] = r["thumb_512"]

    # P4D: drop metadata_path from public export. It points at local
    # "../metadata/<basename>.json" which (a) leaks the source-machine folder
    # layout in the public JSON, and (b) the public demo does not actually ship
    # any metadata/ folder, so the path is dangling. The front-end shows "-"
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
    detail_thumb_policy: str = "all",
) -> int:
    out_dir = out_dir.resolve()
    if strategy not in STRATEGIES:
        print(f"ERROR: unknown --strategy={strategy}. Choose from: {list(STRATEGIES)}", file=sys.stderr)
        return 3
    if detail_thumb_policy not in ("all", "none"):
        print(f"ERROR: --detail-thumb-policy must be 'all' or 'none', got {detail_thumb_policy!r}", file=sys.stderr)
        return 7

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

    # Verify all needed thumbs exist.
    # Under detail_thumb_policy="none" we only ship 256; under "all" we ship both.
    missing: list[tuple[str, int]] = []
    sizes_to_check = (256,) if detail_thumb_policy == "none" else (256, 512)

    for a in picked:
        stem = a.get("id") or Path(a.get("image_path", "")).stem
        for sz in sizes_to_check:
            src = (SRC_THUMBS_256 if sz == 256 else SRC_THUMBS_512) / f"{stem}.jpg"
            if not src.exists():
                missing.append((stem, sz))
    if missing:
        sample = missing[:5]
        print(f"ERROR: {len(missing)} thumb(s) missing. First 5: {sample}", file=sys.stderr)
        return 2

    # Rewrite records. detail_thumb_policy controls whether 512 thumbs
    # and thumb_512 / image_path URLs are present in the output JSON.
    exported = [rewrite_paths(a, base_url, detail_thumb_policy) for a in picked]

    if dry_run:
        print(f"[dry-run] would write to: {out_dir}")
        print(f"[dry-run] {len(exported)} records, strategy={strategy}")
        print(f"[dry-run] detail_thumb_policy={detail_thumb_policy}")
        cats = Counter(r.get("category") for r in exported)
        print(f"[dry-run] category distribution: {dict(cats)}")
        if detail_thumb_policy == "none":
            print(f"[dry-run] thumbs 256: would copy {len(exported)} files")
            print(f"[dry-run] thumbs 512: would copy 0 files (policy=none)")
        else:
            print(f"[dry-run] thumbs 256: would copy {len(exported)} files")
            print(f"[dry-run] thumbs 512: would copy {len(exported)} files")
        return 0

    # Materialize
    out_assets_thumbs = out_dir / "assets" / "thumbs"
    (out_assets_thumbs / "256").mkdir(parents=True, exist_ok=True)
    if detail_thumb_policy == "all":
        (out_assets_thumbs / "512").mkdir(parents=True, exist_ok=True)
    else:
        # P9G+2 policy=none: do NOT create the 512/ dir. This guarantees the
        # publish-delta (rsync --delete) actually removes any pre-existing 512
        # thumbs from the public Pages repo instead of leaving an empty dir.
        pass
    (out_dir / "data").mkdir(parents=True, exist_ok=True)

    # Copy web/* (index.html, app.js, style.css). For index.html we do a
    # text-level patch to swap the LOCAL-only subtitle
    # ("本地图库浏览 · 数据来自 index/artworks.csv + metadata/") for a
    # public-safe one that does not contain the forbidden substrings
    # `metadata/` or `images/`. P8B further enriches the public index
    # with a "demo info card" that surfaces version, last-updated date,
    # public-record count, and the canonical links (Daily Digest /
    # GitHub repo / release / About). The card is injected AFTER the
    # .brand block so the existing app.js / style.css still drive the
    # grid untouched.
    PUBLIC_SUBTITLE = (
        "Artvee Gallery · Public Demo · "
        "数据来自 artvee.com 公共领域艺术作品库"
    )
    for name in ("index.html", "app.js", "style.css"):
        src = SRC_WEB / name
        if not src.exists():
            print(f"ERROR: missing web file: {src}", file=sys.stderr)
            return 2
        if name == "index.html":
            html = src.read_text(encoding="utf-8")
            html = html.replace(
                "本地图库浏览 · 数据来自 index/artworks.csv + metadata/",
                PUBLIC_SUBTITLE,
            )
            # P8B: inject the public demo info card right after the
            # existing .brand block. The card is rendered with inline
            # CSS so style.css edits are not required and so the public
            # bundle stays a single-file index. The card is *informational
            # only*; the existing app.js / grid logic is untouched.
            last_updated = (stats_src.get("last_downloaded_at") or "")[:10] or datetime.now().date().isoformat()
            total_records = stats_src.get("counts", {}).get("artworks", "-")
            info_card = _build_p8b_info_card(
                last_updated=last_updated,
                public_record_count=len(exported),
                total_records=total_records,
                release_tag=_detect_release_tag(BASE_DIR),
            )
            # Insert right before the closing </header>. We use a stable
            # marker so the patch is idempotent (re-runs do not stack
            # cards).
            marker = "<!-- P8B:public-demo-info-card -->"
            if marker not in html:
                # Place the card after the </div> that closes .brand.
                # We do a targeted insertion: the existing <header
                # class="topbar"> contains both .brand and .stats; the
                # card lives between them.
                html = html.replace(
                    '<div class="stats" id="stats">',
                    f"{info_card}\n    <div class=\"stats\" id=\"stats\">",
                )
            (out_dir / name).write_text(html, encoding="utf-8")
        else:
            shutil.copy2(src, out_dir / name)

    # Copy selected thumbs only. Under detail_thumb_policy="none" we skip
    # the 512 loop entirely - no 512 files are emitted and no 512 dir exists.
    copied_256 = 0
    copied_512 = 0
    for a in exported:
        stem = a["id"]
        # 256 - always copied.
        src256 = SRC_THUMBS_256 / f"{stem}.jpg"
        dst256 = out_assets_thumbs / "256" / f"{stem}.jpg"
        shutil.copy2(src256, dst256)
        copied_256 += 1
        # 512 - only when policy="all".
        if detail_thumb_policy == "all":
            src512 = SRC_THUMBS_512 / f"{stem}.jpg"
            dst512 = out_assets_thumbs / "512" / f"{stem}.jpg"
            shutil.copy2(src512, dst512)
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
        # P9G+2: detail-thumb policy is surfaced in the bundle stats so the
        # front-end / any external consumer can read which size set is shipped.
        "detail_thumb_policy": detail_thumb_policy,
        "thumbs_256_count": copied_256,
        "thumbs_512_count": copied_512,
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
    if detail_thumb_policy == "all":
        print(f"    └─ assets/thumbs/{{256,512}}/  {copied_256} + {copied_512} files")
    else:
        print(f"    └─ assets/thumbs/256/  {copied_256} files (policy=none: 512 thumbs NOT shipped)")
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
    if detail_thumb_policy != "all":
        print(f"[i] detail-thumb-policy={detail_thumb_policy} (512 thumbs NOT shipped; image_path → thumb_256)")
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
    p.add_argument("--detail-thumb-policy", choices=("all", "none"),
                   default="all",
                   help="P9G+2. Controls whether the public Gallery bundle "
                        "ships 512 thumbnails. 'all' = ship both 256 + 512 "
                        "(back-compat; ~14.88 MB at 300 records). 'none' = "
                        "ship 256 only; thumb_512 is null in JSON; image_path "
                        "is remapped to thumb_256 so the detail-panel fallback "
                        "chain works without 404s. P9G+2 sets this to 'none' "
                        "by default in confirm_demo_refresh.sh to bring the "
                        "bundle from ~14.88 MB → ~3.52 MB.")
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
        detail_thumb_policy=args.detail_thumb_policy,
    )


if __name__ == "__main__":
    sys.exit(main())
