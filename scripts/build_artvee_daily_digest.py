#!/usr/bin/env python3
"""
Artvee Gallery · Daily Inspiration Digest (P3B)
================================================
Reads P1 outputs (web/data/*.json, logs/nightly_summary.csv) and emits a
self-contained daily digest:

  digests/
  ├── artvee-digest-YYYY-MM-DD.md     (Markdown)
  └── artvee-digest-YYYY-MM-DD.html   (static HTML, mirrors Gallery style)
  web/data/digests.json               (rolling index; updated idempotently)

Design principles (P3B):
  - Deterministic / local-only: no external AI, no online calls.
  - Pillow is optional: if available, extract dominant palette from 256-thumb;
    otherwise fall back to category/title/artist heuristics.
  - Failure-isolated: digest build never crashes the calling pipeline.
    Returns exit 0 on empty inputs, 2 on missing source, 3 on bad strategy.
  - Public-safe by construction: every output path is relative and contains no
    '/home/', '~/' or 'hermes-agent' substring. No base64, no embedded blobs.

Selection strategies:
  - recent: top-N newest by downloaded_at (ties broken by id).
  - diverse: round-robin by category, then by downloaded_at desc within cat,
    skipping consecutive duplicates of the same artist when possible.

Visual notes (when Pillow present):
  - orientation (landscape/portrait/square) from w/h ratio
  - dominant palette: 5 quantized colors via k-means (k=5)
  - category-aware use-case hints
  - title-aware prompt seed: "<category> vintage artvee illustration, <theme>"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, deque
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DATA = BASE_DIR / "web" / "data"
SRC_THUMBS_256 = BASE_DIR / "thumbs" / "256"
LOGS_DIR = BASE_DIR / "logs"
WEB_STYLE_CSS = BASE_DIR / "web" / "style.css"  # reuse for HTML consistency

DEFAULT_OUT = BASE_DIR / "digests"
INDEX_FILE = SRC_DATA / "digests.json"

# --- exit codes ---
EXIT_OK = 0
EXIT_SOURCE_MISSING = 2
EXIT_BAD_STRATEGY = 3
EXIT_INTERNAL = 4


# ---------- optional Pillow ----------
try:
    from PIL import Image  # type: ignore
    HAS_PIL = True
except Exception:  # noqa: BLE001
    Image = None  # type: ignore
    HAS_PIL = False


# ---------- IO ----------
def load_json(path: Path):
    if not path.exists():
        print(f"ERROR: source not found: {path}", file=sys.stderr)
        sys.exit(EXIT_SOURCE_MISSING)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------- date parsing ----------
def parse_date_arg(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # tolerate trailing Z
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


# ---------- selection strategies ----------
def select_recent(candidates: list[dict], select: int) -> list[dict]:
    return sorted(
        candidates,
        key=lambda a: (a.get("downloaded_at") or "", a.get("id") or ""),
        reverse=True,
    )[:select]


def select_diverse(candidates: list[dict], select: int) -> list[dict]:
    """Round-robin by category, prefer newer within each cat, avoid artist repeat when possible."""
    by_cat: dict[str, list[dict]] = {}
    for a in candidates:
        cat = a.get("category") or "uncategorized"
        by_cat.setdefault(cat, []).append(a)
    for cat in by_cat:
        by_cat[cat].sort(
            key=lambda a: (a.get("downloaded_at") or "", a.get("id") or ""),
            reverse=True,
        )

    queues = {cat: deque(items) for cat, items in by_cat.items()}
    order = sorted(queues.keys())
    picked: list[dict] = []
    last_artist = None
    while queues and len(picked) < select:
        progress = False
        for cat in order:
            if not queues[cat]:
                continue
            # try to pick first item; if same artist as last, look one ahead
            chosen_idx = 0
            if (
                last_artist is not None
                and len(queues[cat]) > 1
                and (queues[cat][0].get("artist") or "") == last_artist
            ):
                chosen_idx = 1
            item = queues[cat][chosen_idx]
            del queues[cat][chosen_idx]
            picked.append(item)
            last_artist = item.get("artist") or None
            progress = True
            if len(picked) >= select:
                break
        if not progress:
            break
    return picked


STRATEGIES = {
    "recent": select_recent,
    "diverse": select_diverse,
}


# ---------- visual analysis ----------
CATEGORY_HINTS = {
    "japanese-prints": {
        "orientation_hint": "横向/竖向混合，留白多",
        "use_cases": ["海报背景", "书籍封面", "视频分镜参考", "动画参考帧"],
        "seed_prefix": "ukiyo-e inspired vintage art print",
    },
    "botanical-charts": {
        "orientation_hint": "竖向为主，构图对称",
        "use_cases": ["信息图装饰", "植物图鉴", "科普插图", "笔记本封面"],
        "seed_prefix": "vintage botanical illustration engraving",
    },
    "book-illustrations": {
        "orientation_hint": "根据故事页而定，多为横向叙事",
        "use_cases": ["书籍插图", "童话配图", "故事封面", "明信片"],
        "seed_prefix": "classic book illustration watercolor",
    },
    "posters-design": {
        "orientation_hint": "竖向海报，构图紧凑",
        "use_cases": ["海报设计参考", "活动宣传", "展览主视觉", "壁纸"],
        "seed_prefix": "art nouveau vintage poster illustration",
    },
}


def _safe_thumb_path(record: dict, base_url: str) -> Path:
    """Return the absolute path to the 256-thumb for visual analysis."""
    rel = record.get("thumb_256") or record.get("thumb_512") or ""
    name = Path(rel).name
    if not name:
        return SRC_THUMBS_256  # sentinel
    return SRC_THUMBS_256 / name


def analyze_visual(record: dict) -> dict:
    """Return {orientation, palette, visual_notes, prompt_seed, use_cases}."""
    cat = record.get("category") or ""
    hint = CATEGORY_HINTS.get(cat, {})
    orientation = "未知"
    palette: list[str] = []
    visual_notes: list[str] = []

    # --- Pillow analysis ---
    if HAS_PIL:
        thumb = _safe_thumb_path(record, ".")
        if thumb.exists():
            try:
                with Image.open(thumb) as im:  # noqa: F821
                    w, h = im.size
                    if w > h * 1.15:
                        orientation = "横向构图"
                    elif h > w * 1.15:
                        orientation = "纵向构图"
                    else:
                        orientation = "方形构图"
                    # small thumbnail for palette extraction
                    im_small = im.convert("RGB").resize((64, 64))
                    # simple quantized palette: bucket into 5 most common colors
                    palette = _quantize_palette(im_small, k=5)
            except Exception as e:  # noqa: BLE001
                visual_notes.append(f"视觉分析失败（{type(e).__name__}），已 fallback")
                orientation = hint.get("orientation_hint", "未知")
        else:
            visual_notes.append("缩略图不存在，跳过像素分析")
            orientation = hint.get("orientation_hint", "未知")
    else:
        orientation = hint.get("orientation_hint", "未知")
        visual_notes.append("Pillow 不可用，使用 category 规则分析")

    # --- always-on composition / use cases from category ---
    if orientation:
        visual_notes.append(f"构图：{orientation}")
    if palette:
        visual_notes.append("dominant palette: " + ", ".join(palette))
    use_cases = hint.get("use_cases", ["灵感参考"])

    # --- prompt seed ---
    seed_prefix = hint.get("seed_prefix", "vintage artvee illustration")
    title = (record.get("title") or "").strip()
    if title:
        # collapse whitespace
        title_short = " ".join(title.split())[:60]
        prompt_seed = f"{seed_prefix}, {title_short}, public domain print"
    else:
        prompt_seed = f"{seed_prefix}, public domain art print"

    return {
        "orientation": orientation,
        "palette": palette,
        "visual_notes": visual_notes,
        "use_cases": use_cases,
        "prompt_seed": prompt_seed,
    }


def _quantize_palette(im, k: int = 5) -> list[str]:
    """Tiny k-means-ish: bucket pixels to a fixed grid then pick most common.

    Uses raw bytes via tobytes() to avoid Pillow's deprecated getdata().
    Quantize to 4 bits per channel (4096 buckets) → fast histogram.
    """
    raw = im.tobytes()  # sequence of bytes: R,G,B,R,G,B,...
    buckets: Counter = Counter()
    # unpack triplets without forcing a list (tobytes returns bytes)
    for i in range(0, len(raw) - 2, 3):
        r = raw[i]
        g = raw[i + 1]
        b = raw[i + 2]
        rb = (r >> 4) << 4
        gb = (g >> 4) << 4
        bb = (b >> 4) << 4
        buckets[(rb, gb, bb)] += 1
    top = buckets.most_common(k)
    return [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in top]


# ---------- candidate filter ----------
def filter_candidates_by_date(
    artworks: list[dict], target: date
) -> tuple[list[dict], str]:
    """Filter artworks whose downloaded_at falls on target date.

    Returns (filtered_list, fallback_reason_or_empty).
    """
    matched: list[dict] = []
    for a in artworks:
        dt = parse_iso(a.get("downloaded_at"))
        if dt and dt.date() == target:
            matched.append(a)
    if matched:
        return matched, ""

    # fallback: no exact-date match. Take the newest candidate_limit as a
    # proxy for "today's worth of work" so the digest still has content.
    sorted_all = sorted(
        artworks,
        key=lambda a: (a.get("downloaded_at") or "", a.get("id") or ""),
        reverse=True,
    )
    return sorted_all, (
        f"no artworks matched {target.isoformat()}; "
        f"fallback to newest-by-downloaded_at (count={len(sorted_all)})"
    )


# ---------- output builders ----------
def _safe_rel(p: str | Path) -> str:
    """Convert any potentially-absolute path to a safe relative string.

    We never want to leak /home/, ~/, or hermes-agent. The exported data and
    thumbnails always live under the project tree; we use forward slashes.
    """
    s = str(p).replace("\\", "/")
    # Belt-and-suspenders: redact any local-absolute path fragments.
    for needle in ("/home/", "~/", "hermes-agent"):
        if needle in s:
            # This is a bug somewhere upstream; replace with sentinel.
            s = s.replace(needle, "<redacted>")
    return s


def build_markdown(
    digest_date: date,
    selected: list[dict],
    analyses: list[dict],
    candidate_pool_size: int,
    fallback_reason: str,
    strategy: str,
    thumbs_subdir: str = "../thumbs/512",
) -> str:
    today = digest_date.isoformat()
    cats = sorted({a.get("category") for a in selected if a.get("category")})
    artists = sorted({a.get("artist") for a in selected if a.get("artist")})

    lines: list[str] = []
    lines.append(f"# Artvee Daily Digest — {today}")
    lines.append("")
    lines.append("## 1. 今日概览")
    lines.append(f"- 候选范围：{candidate_pool_size} 张")
    lines.append(f"- 精选数量：{len(selected)} 张")
    lines.append(f"- 涉及分类：{', '.join(cats) if cats else '—'}")
    lines.append(f"- 涉及艺术家：{', '.join(artists) if artists else '—'}")
    lines.append(f"- 选择策略：`{strategy}`")
    if fallback_reason:
        lines.append(f"- 备注：{fallback_reason}")
    lines.append("")
    lines.append("## 2. 今日精选")
    lines.append("")

    for idx, (rec, ana) in enumerate(zip(selected, analyses), 1):
        title = rec.get("title") or rec.get("id") or "Untitled"
        artist = rec.get("artist") or "未知"
        cat = rec.get("category") or "—"
        src = rec.get("source_url") or "—"
        # Use 512 thumb for richer preview
        thumb_rel = rec.get("thumb_512") or rec.get("thumb_256") or ""
        thumb_filename = Path(thumb_rel).name if thumb_rel else ""
        thumb_md = f"{thumbs_subdir}/{thumb_filename}" if thumb_filename else ""

        lines.append(f"### {idx}. {title} — {artist}")
        if thumb_md:
            lines.append(f"![preview]({thumb_md})")
        lines.append(f"- 分类：{cat}")
        lines.append(f"- 来源：{src}")
        for note in ana["visual_notes"]:
            lines.append(f"- 视觉：{note}")
        lines.append(f"- 用途：{', '.join(ana['use_cases'])}")
        lines.append(f"- Prompt seed：`{ana['prompt_seed']}`")
        lines.append("")

    lines.append("## 3. 今日风格总结")
    # synthesize summary from the analyses
    orient_counter = Counter(a["orientation"] for a in analyses)
    palette_counter = Counter()
    for a in analyses:
        for c in a["palette"]:
            palette_counter[c] += 1
    lines.append(
        f"- 构图分布：{', '.join(f'{k}({v})' for k, v in orient_counter.most_common()) or '—'}"
    )
    top_palette = [c for c, _ in palette_counter.most_common(8)]
    lines.append(
        f"- 主色（top across picks）：{', '.join(top_palette) if top_palette else '—'}"
    )
    cat_counter = Counter(a.get("category") for a in selected)
    lines.append(
        f"- 类别分布：{', '.join(f'{k}({v})' for k, v in cat_counter.most_common()) or '—'}"
    )
    lines.append("")

    lines.append("## 4. 可用于哪些项目")
    use_cases: Counter = Counter()
    for a in analyses:
        for u in a["use_cases"]:
            use_cases[u] += 1
    for uc, cnt in use_cases.most_common():
        lines.append(f"- {uc}（命中 {cnt} 张）")
    lines.append("")

    lines.append("## 5. 数据来源与边界")
    lines.append("- 数据源：`web/data/artworks.json`（P1 builder 输出）")
    lines.append("- 缩略图：`thumbs/512/`（P1 builder 生成，本地路径相对 `digests/`）")
    lines.append("- 边界：未触发下载；未发布公网；未调用在线模型；本 digest 完全 deterministic。")
    lines.append("- Prompt seed 仅作创作起步提示，请结合实际需要二次修改。")
    lines.append("")

    return "\n".join(lines)


def build_html(
    digest_date: date,
    selected: list[dict],
    analyses: list[dict],
    candidate_pool_size: int,
    fallback_reason: str,
    strategy: str,
    css_relpath: str = "../web/style.css",
    thumbs_subdir: str = "../thumbs/512",
) -> str:
    today = digest_date.isoformat()
    cats = sorted({a.get("category") for a in selected if a.get("category")})
    artists = sorted({a.get("artist") for a in selected if a.get("artist")})

    cards: list[str] = []
    for idx, (rec, ana) in enumerate(zip(selected, analyses), 1):
        title = rec.get("title") or rec.get("id") or "Untitled"
        artist = rec.get("artist") or "未知"
        cat = rec.get("category") or "—"
        src = rec.get("source_url") or "#"
        thumb_rel = rec.get("thumb_512") or rec.get("thumb_256") or ""
        thumb_filename = Path(thumb_rel).name if thumb_rel else ""
        thumb_src = f"{thumbs_subdir}/{thumb_filename}" if thumb_filename else ""
        palette_html = (
            "".join(
                f'<span class="swatch" style="background:{c}" title="{c}"></span>'
                for c in ana["palette"]
            )
            if ana["palette"]
            else "<em>Pillow 未启用 / 缩略图缺失</em>"
        )
        notes_html = "".join(f"<li>{n}</li>" for n in ana["visual_notes"])
        uses_html = "".join(f"<li>{u}</li>" for u in ana["use_cases"])
        # Escape title for HTML
        title_html = (
            title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        artist_html = (
            artist.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        cat_html = (
            cat.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

        cards.append(f"""
<article class="digest-card">
  <div class="digest-card__media">
    {f'<img src="{thumb_src}" alt="{title_html}" loading="lazy" />' if thumb_src else '<div class="placeholder">无缩略图</div>'}
  </div>
  <div class="digest-card__body">
    <h3 class="digest-card__title">{idx}. {title_html}</h3>
    <p class="digest-card__artist">{artist_html}</p>
    <p class="digest-card__meta">分类：{cat_html}</p>
    <p class="digest-card__meta">来源：<a href="{src}" target="_blank" rel="noopener">artvee.com 原页 ↗</a></p>
    <details>
      <summary>视觉</summary>
      <ul class="notes">{notes_html}</ul>
      <div class="palette">{palette_html}</div>
    </details>
    <details>
      <summary>用途</summary>
      <ul class="uses">{uses_html}</ul>
    </details>
    <details>
      <summary>Prompt seed</summary>
      <pre class="prompt">{ana["prompt_seed"]}</pre>
    </details>
  </div>
</article>""")

    orient_counter = Counter(a["orientation"] for a in analyses)
    cat_counter = Counter(a.get("category") for a in selected)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Artvee Daily Digest — {today}</title>
<link rel="stylesheet" href="{css_relpath}">
<style>
  body.digest {{ max-width: 980px; margin: 2rem auto; padding: 0 1rem; }}
  .digest-header {{ padding-bottom: 1rem; border-bottom: 1px solid #e5e7eb; margin-bottom: 1.5rem; }}
  .digest-stats {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 0.5rem; color: #555; font-size: 0.92rem; }}
  .digest-stats span {{ background: #f3f4f6; padding: 0.25rem 0.6rem; border-radius: 999px; }}
  .digest-card {{ display: grid; grid-template-columns: 220px 1fr; gap: 1.25rem; padding: 1rem 0; border-bottom: 1px solid #f3f4f6; }}
  .digest-card__media img {{ width: 100%; height: auto; border-radius: 4px; display: block; }}
  .digest-card__media .placeholder {{ background: #f3f4f6; aspect-ratio: 1/1; display: grid; place-items: center; color: #999; }}
  .digest-card__title {{ margin: 0 0 0.25rem; font-size: 1.05rem; }}
  .digest-card__artist {{ margin: 0 0 0.5rem; color: #555; font-size: 0.92rem; }}
  .digest-card__meta {{ margin: 0.15rem 0; font-size: 0.85rem; color: #666; }}
  .digest-card details {{ margin-top: 0.5rem; }}
  .digest-card summary {{ cursor: pointer; font-size: 0.85rem; color: #2563eb; }}
  .digest-card ul.notes, .digest-card ul.uses {{ margin: 0.5rem 0 0.5rem 1.2rem; padding: 0; font-size: 0.88rem; }}
  .palette {{ display: flex; gap: 0.35rem; margin-top: 0.5rem; }}
  .swatch {{ width: 28px; height: 28px; border-radius: 4px; border: 1px solid #e5e7eb; display: inline-block; }}
  pre.prompt {{ background: #f9fafb; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.82rem; overflow-x: auto; }}
  .digest-summary {{ background: #f9fafb; padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem; }}
</style>
</head>
<body class="digest">
  <header class="digest-header">
    <h1>Artvee Daily Digest — {today}</h1>
    <div class="digest-stats">
      <span>精选：{len(selected)}</span>
      <span>候选：{candidate_pool_size}</span>
      <span>策略：{strategy}</span>
      <span>分类：{len(cats)}</span>
      <span>艺术家：{len(artists)}</span>
    </div>
    {f'<p style="color:#a16207;font-size:0.85rem;">⚠️ {fallback_reason}</p>' if fallback_reason else ''}
  </header>

  <section class="digest-summary">
    <strong>风格总结：</strong>
    构图 {', '.join(f'{k}({v})' for k, v in orient_counter.most_common()) or '—'} ·
    类别 {', '.join(f'{k}({v})' for k, v in cat_counter.most_common()) or '—'}
  </section>

  {''.join(cards)}

  <footer style="margin-top:2rem;color:#888;font-size:0.8rem;">
    <p>数据源：web/data/artworks.json (P1 builder)。未触发下载；未发布公网；deterministic 本地生成。</p>
  </footer>
</body>
</html>
"""
    return html


# ---------- index ----------
def update_index(
    digest_date: date,
    selected: list[dict],
    md_path: Path,
    html_path: Path,
    strategy: str,
    index_path: Path,
) -> None:
    """Append-or-replace digest entry in web/data/digests.json.

    Path values are relative to the *gallery web root* (where digests.json
    lives), i.e. from web/data/digests.json up to digests/ is ../../digests/.
    """
    cats = sorted({a.get("category") for a in selected if a.get("category")})
    artists = sorted({a.get("artist") for a in selected if a.get("artist")})

    # gallery web root = BASE_DIR
    # digests.json lives at BASE_DIR/web/data/digests.json
    # md/html live at BASE_DIR/digests/...
    try:
        rel_md = md_path.relative_to(BASE_DIR).as_posix()
        rel_html = html_path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        rel_md = _safe_rel(md_path)
        rel_html = _safe_rel(html_path)

    entry = {
        "date": digest_date.isoformat(),
        "title": f"Artvee Daily Digest — {digest_date.isoformat()}",
        "markdown_path": rel_md,
        "html_path": rel_html,
        "selected_count": len(selected),
        "categories": cats,
        "artists": artists,
        "strategy": strategy,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except Exception:  # noqa: BLE001
            data = []
    else:
        data = []

    # de-dupe by date: replace existing entry of same date
    data = [e for e in data if e.get("date") != entry["date"]]
    data.append(entry)
    # keep newest first
    data.sort(key=lambda e: e.get("date", ""), reverse=True)
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------- main ----------
def main() -> int:
    p = argparse.ArgumentParser(description="Artvee Daily Inspiration Digest")
    p.add_argument("--date", default=None,
                   help="Target date YYYY-MM-DD (default: today)")
    p.add_argument("--select", type=int, default=5,
                   help="How many artworks to feature (default: 5)")
    p.add_argument("--candidate-limit", type=int, default=20,
                   help="Candidate pool size before selection (default: 20)")
    p.add_argument("--strategy", choices=list(STRATEGIES.keys()), default="diverse",
                   help="Selection strategy (default: diverse)")
    p.add_argument("--mode", choices=("local", "public"), default="local",
                   help="Mode hint for log/footer only; output is local-only by default")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT,
                   help=f"Output directory (default: {DEFAULT_OUT})")
    p.add_argument("--base-url", default=".",
                   help="Base URL prefix (reserved for future public deploy)")
    p.add_argument("--dry-run", action="store_true",
                   help="Plan-only: print selection and exit before writing")
    args = p.parse_args()

    if args.strategy not in STRATEGIES:
        print(
            f"ERROR: unknown --strategy={args.strategy}. Choose from: {list(STRATEGIES)}",
            file=sys.stderr,
        )
        return EXIT_BAD_STRATEGY

    digest_date = parse_date_arg(args.date) if args.date else date.today()

    artworks = load_json(SRC_DATA / "artworks.json")
    if not artworks:
        print("ERROR: web/data/artworks.json is empty", file=sys.stderr)
        return EXIT_SOURCE_MISSING

    # candidates = top-N newest; if no exact-date match, fallback to newest-N
    pool, fallback_reason = filter_candidates_by_date(artworks, digest_date)
    candidates = pool[: args.candidate_limit]

    selector = STRATEGIES[args.strategy]
    selected = selector(candidates, args.select)
    if not selected:
        print("ERROR: nothing selected (empty source?)", file=sys.stderr)
        return EXIT_SOURCE_MISSING

    if args.dry_run:
        print(f"[dry-run] date={digest_date.isoformat()} strategy={args.strategy}")
        print(f"[dry-run] candidate pool size={len(candidates)} (fallback={bool(fallback_reason)})")
        if fallback_reason:
            print(f"[dry-run] {fallback_reason}")
        print(f"[dry-run] selected={len(selected)}:")
        for a in selected:
            print(f"  - {a.get('id')} | {a.get('category')} | {a.get('artist')}")
        return EXIT_OK

    analyses = [analyze_visual(a) for a in selected]

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / f"artvee-digest-{digest_date.isoformat()}.md"
    html_path = out_dir / f"artvee-digest-{digest_date.isoformat()}.html"

    md_text = build_markdown(
        digest_date=digest_date,
        selected=selected,
        analyses=analyses,
        candidate_pool_size=len(candidates),
        fallback_reason=fallback_reason,
        strategy=args.strategy,
    )
    html_text = build_html(
        digest_date=digest_date,
        selected=selected,
        analyses=analyses,
        candidate_pool_size=len(candidates),
        fallback_reason=fallback_reason,
        strategy=args.strategy,
    )

    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")

    update_index(
        digest_date=digest_date,
        selected=selected,
        md_path=md_path,
        html_path=html_path,
        strategy=args.strategy,
        index_path=INDEX_FILE,
    )

    print(f"[✓] digest generated: {md_path.name} + {html_path.name}")
    print(f"    selected={len(selected)} strategy={args.strategy} "
          f"candidates={len(candidates)}")
    print(f"    Pillow={'on' if HAS_PIL else 'off (heuristic only)'}")
    print(f"    index updated: {INDEX_FILE}")
    if fallback_reason:
        print(f"    [note] {fallback_reason}")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"FATAL: digest build crashed: {type(e).__name__}: {e}", file=sys.stderr)
        # Never crash the calling pipeline.
        sys.exit(EXIT_OK)