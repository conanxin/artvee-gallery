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
from datetime import datetime, date, timedelta
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
def select_recent(candidates: list[dict], select: int, max_per_artist: int = 1) -> list[dict]:
    """Sort by downloaded_at desc; ties broken by id for stability.

    P5E: when --max-per-artist is set, the cap is enforced even for
    the recent strategy (otherwise the digest would degenerate to
    "5 newest, possibly all by the same artist"). If the cap rejects
    a candidate, we fall through to the next-newest.
    """
    def _artist_key(a: dict) -> str:
        art = (a.get("artist") or "").strip()
        return art or "Anonymous"

    sorted_cands = sorted(
        candidates,
        key=lambda a: (a.get("downloaded_at") or "", a.get("id") or ""),
        reverse=True,
    )
    picked: list[dict] = []
    artist_counts: Counter = Counter()
    for c in sorted_cands:
        ak = _artist_key(c)
        if max_per_artist and artist_counts[ak] >= max_per_artist:
            continue
        picked.append(c)
        artist_counts[ak] += 1
        if len(picked) >= select:
            break
    return picked


def select_diverse(candidates: list[dict], select: int, max_per_artist: int = 1) -> list[dict]:
    """Round-robin by category, prefer newer within each cat, avoid artist repeat.

    P5E: --max-per-artist defaults to 1 (strict cap within a single
    digest). When a category's queue runs dry, we re-queue the
    over-cap item and continue; the cap is enforced across the whole
    run, not just consecutive picks. Anonymous artists are normalized
    to the literal string "Anonymous" so the cap is enforced across
    them as well.
    """
    def _artist_key(a: dict) -> str:
        art = (a.get("artist") or "").strip()
        return art or "Anonymous"

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
    artist_counts: Counter = Counter()
    last_artist = None
    cap_relaxed = 0
    max_relax = select * 4
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
                and _artist_key(queues[cat][0]) == last_artist
            ):
                chosen_idx = 1
            item = queues[cat][chosen_idx]
            del queues[cat][chosen_idx]
            ak = _artist_key(item)
            if max_per_artist and artist_counts[ak] >= max_per_artist:
                cap_relaxed += 1
                if cap_relaxed <= max_relax:
                    # re-queue at the end; we'll try other categories first
                    queues[cat].append(item)
                    continue
                # else: emergency pick
            picked.append(item)
            artist_counts[ak] += 1
            last_artist = ak
            progress = True
            if len(picked) >= select:
                break
        if not progress:
            break
    return picked




# ---------- P6F: history + near-dup aware filtering ----------

def load_history(history_file: Path) -> dict:
    """Load digest history from a runtime JSON file.

    Returns {"version":1, "updated_at":..., "window_days":30, "entries":[...]}
    or a fresh skeleton if the file does not exist or is malformed.
    """
    if not history_file.exists():
        return {"version": 1, "updated_at": "", "window_days": 30, "entries": []}
    try:
        with history_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"version": 1, "updated_at": "", "window_days": 30, "entries": []}
    if not isinstance(data, dict):
        data = {"version": 1, "updated_at": "", "window_days": 30, "entries": []}
    data.setdefault("version", 1)
    data.setdefault("updated_at", "")
    data.setdefault("window_days", 30)
    data.setdefault("entries", [])
    if not isinstance(data["entries"], list):
        data["entries"] = []
    return data


def save_history(history_file: Path, data: dict, window_days: int) -> None:
    """Write digest history atomically (no git track)."""
    data["version"] = 1
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    data["window_days"] = window_days
    history_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = history_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(history_file)


def load_near_dup_clusters(clusters_path: Path) -> dict[str, str]:
    """Return artwork_id -> cluster_id mapping from P6C review JSON.

    If the file does not exist, return an empty dict (no near-dup awareness).
    """
    if not clusters_path.exists():
        return {}
    try:
        with clusters_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    mapping: dict[str, str] = {}
    for cluster in data.get("clusters", []):
        cid = cluster.get("cluster_id", "")
        for rec in cluster.get("records", []):
            rid = rec.get("id")
            if rid and cid:
                mapping[rid] = cid
    return mapping


def _history_filtered_pool(
    candidates: list[dict],
    history_data: dict,
    near_dup_mapping: dict[str, str],
    window_days: int,
    target_date: date,
    select: int,
) -> tuple[list[dict], str]:
    """Filter candidates against recent digest history + near-dup clusters.

    Rules (applied in order, each relaxing only when the previous would leave
    too few candidates):
    1. Remove artwork ids that appeared in the last `window_days` days.
    2. Remove artworks whose artist appeared in the last `window_days` days.
    3. Remove artworks whose near-dup cluster appeared in the last
       `window_days` days (only if a cluster mapping exists).
    4. If the filtered pool has fewer than `select` items, the rule that
       caused the shortage is relaxed and the next-smaller rule is tried.
       If *all* rules are exhausted and the pool still < select, we record
       a fallback reason and return the largest-possible filtered pool.

    Returns (filtered_candidates, fallback_reason).
    """
    entries = history_data.get("entries", [])
    if not entries or window_days <= 0:
        return candidates, ""

    cutoff = target_date - timedelta(days=window_days)
    # Gather all seen sets in the window
    seen_ids: set[str] = set()
    seen_artists: set[str] = set()
    seen_clusters: set[str] = set()
    for entry in entries:
        entry_date_str = entry.get("date", "")
        if not entry_date_str:
            continue
        try:
            entry_date = date.fromisoformat(entry_date_str)
        except Exception:
            continue
        if entry_date < cutoff or entry_date > target_date:
            continue
        for pick in entry.get("picks", []):
            seen_ids.add(pick.get("id", ""))
            seen_artists.add(pick.get("artist", ""))
            if pick.get("near_dup_cluster_id"):
                seen_clusters.add(pick.get("near_dup_cluster_id"))

    # Remove empty strings
    seen_ids.discard("")
    seen_artists.discard("")
    seen_clusters.discard("")

    def apply_filter(cands: list[dict], rule_level: int) -> list[dict]:
        """rule_level: 0=none, 1=id, 2=artist, 3=cluster."""
        result: list[dict] = []
        for c in cands:
            rid = c.get("id", "")
            artist = (c.get("artist") or "").strip() or "Anonymous"
            cluster = near_dup_mapping.get(rid, "")
            if rule_level >= 1 and rid in seen_ids:
                continue
            if rule_level >= 2 and artist in seen_artists:
                continue
            if rule_level >= 3 and cluster and cluster in seen_clusters:
                continue
            result.append(c)
        return result

    # Try increasingly strict rules, but relax if we drop below `select`
    for level in range(0, 4):
        filtered = apply_filter(candidates, level)
        if len(filtered) >= select:
            reasons = {
                1: "filter=history-id (avoid repeat artwork within {d} days)",
                2: "filter=history-id+artist (avoid repeat artist within {d} days)",
                3: "filter=history-id+artist+cluster (avoid repeat near-dup cluster within {d} days)",
            }
            if level == 0:
                return filtered, ""
            return filtered, reasons.get(level, "").format(d=window_days)

    # All rules exhausted; return the strictest filtered pool with fallback note
    filtered = apply_filter(candidates, 3)
    if not filtered:
        # absolute fallback: return id-filtered, then artist-filtered, then all
        filtered = apply_filter(candidates, 2)
        if not filtered:
            filtered = apply_filter(candidates, 1)
            if not filtered:
                filtered = candidates
    return filtered, (
        f"history-filter fallback: after {window_days}-day id+artist+cluster dedup, "
        f"only {len(filtered)} candidates remain (need {select}); "
        "returning relaxed pool"
    )

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


# ---------- P5E: prompt-field non-empty validator ----------
def _ensure_prompt_fields(analysis: dict, fallback_id: str) -> tuple[dict, bool]:
    """Defensive: guarantee prompt_seed + use_cases are non-empty.

    P5E curation contract: every digest pick must surface a usable
    prompt_seed and a non-empty use_cases list. The deterministic
    analyzer already produces both, but this validator backfills any
    empty fields with category-aware defaults so downstream
    consumers (HTML, public page) never render a blank prompt.
    Returns (analysis, did_backfill).
    """
    did = False
    if not analysis.get("prompt_seed") or not str(analysis["prompt_seed"]).strip():
        analysis["prompt_seed"] = (
            f"vintage art print, {fallback_id}, public domain"
        )
        did = True
    if not analysis.get("use_cases"):
        analysis["use_cases"] = ["灵感参考", "设计素材", "印刷品参考"]
        did = True
    elif isinstance(analysis["use_cases"], list) and len(analysis["use_cases"]) == 0:
        analysis["use_cases"] = ["灵感参考", "设计素材", "印刷品参考"]
        did = True
    return analysis, did


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
    analyses: list[dict],
    md_path: Path,
    html_path: Path,
    strategy: str,
    index_path: Path,
    near_dup_mapping: dict[str, str] = None,
) -> None:
    """Append-or-replace digest entry in web/data/digests.json.

    Path values are relative to the *gallery web root* (where digests.json
    lives), i.e. from web/data/digests.json up to digests/ is ../../digests/.
    """
    cats = sorted({a.get("category") for a in selected if a.get("category")})
    artists = sorted({a.get("artist") for a in selected if a.get("artist")})
    near_dup_mapping = near_dup_mapping or {}

    # gallery web root = BASE_DIR
    # digests.json lives at BASE_DIR/web/data/digests.json
    # md/html live at BASE_DIR/digests/...
    try:
        rel_md = md_path.relative_to(BASE_DIR).as_posix()
        rel_html = html_path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        rel_md = _safe_rel(md_path)
        rel_html = _safe_rel(html_path)

    picks = []
    for rec in selected:
        picks.append({
            "id": rec.get("id", ""),
            "artist": rec.get("artist", ""),
            "category": rec.get("category", ""),
            "near_dup_cluster_id": near_dup_mapping.get(rec.get("id", ""), None),
        })

    entry = {
        "date": digest_date.isoformat(),
        "title": f"Artvee Daily Digest — {digest_date.isoformat()}",
        "markdown_path": rel_md,
        "html_path": rel_html,
        "selected_count": len(selected),
        "categories": cats,
        "artists": artists,
        "strategy": strategy,
        "picks": picks,
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
    p.add_argument("--max-per-artist", type=int, default=1,
                   help="P5E curation filter. Maximum picks per artist within "
                        "one digest. Default 1 (strict). Set 0 to disable.")
    p.add_argument("--allow-repeat-artist", action="store_true",
                   help="P5E. If set, equivalent to --max-per-artist 0 "
                        "(no cap). Default behaviour is max 1 per artist.")
    p.add_argument("--history-days", type=int, default=30,
                   help="P6F. How many days back to look for history dedup. "
                        "Default 30. Set 0 to disable history filtering.")
    p.add_argument("--history-file", type=Path,
                   default=BASE_DIR / "reports" / "runtime" / "digest-history.json",
                   help="P6F. Runtime digest history JSON path. NOT tracked in git.")
    p.add_argument("--ignore-history", action="store_true",
                   help="P6F. Skip history dedup (equivalent to --history-days 0).")
    p.add_argument("--near-dup-clusters", type=Path,
                   default=BASE_DIR / "reports" / "runtime" / "p6c-near-dup-clusters.json",
                   help="P6F. Near-dup cluster JSON from review_near_duplicate_clusters.py. "
                        "If missing, near-dup awareness is skipped.")
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
    # P5E: --allow-repeat-artist short-circuits to no cap
    max_per_artist = 0 if args.allow_repeat_artist else args.max_per_artist

    # P6F: history window + near-dup awareness
    window_days = 0 if args.ignore_history else args.history_days
    history_data = load_history(args.history_file)
    near_dup_mapping = load_near_dup_clusters(args.near_dup_clusters)

    # P6F: history + near-dup cluster filtering before selection
    filtered_candidates, history_fallback = _history_filtered_pool(
        candidates, history_data, near_dup_mapping, window_days, digest_date, args.select
    )
    if filtered_candidates is not candidates:
        candidates = filtered_candidates
        if history_fallback:
            fallback_reason = fallback_reason + ("; " if fallback_reason else "") + history_fallback

    selected = selector(candidates, args.select, max_per_artist=max_per_artist)
    if not selected:
        print("ERROR: nothing selected (empty source?)", file=sys.stderr)
        return EXIT_SOURCE_MISSING

    if args.dry_run:
        print(f"[dry-run] date={digest_date.isoformat()} strategy={args.strategy}")
        print(f"[dry-run] max-per-artist={max_per_artist} (0=no cap)")
        print(f"[dry-run] history_window={window_days} days, near_dup_clusters={len(near_dup_mapping)}")
        print(f"[dry-run] candidate pool size={len(candidates)} (fallback={bool(fallback_reason)})")
        if fallback_reason:
            print(f"[dry-run] {fallback_reason}")
        print(f"[dry-run] selected={len(selected)}:")
        for a in selected:
            print(f"  - {a.get('id')} | {a.get('category')} | {a.get('artist')}")
        artists = [a.get('artist') or 'Anonymous' for a in selected]
        from collections import Counter as _C
        artist_counts = _C(artists)
        repeats = {k: v for k, v in artist_counts.items() if v > 1}
        if repeats:
            print(f"[dry-run] WARN: artist repeats: {repeats}")
        else:
            print(f"[dry-run] artist diversity OK (all unique)")
        return EXIT_OK

    analyses = [analyze_visual(a) for a in selected]
    # P5E: defensive non-empty check on prompt fields. The analyzer
    # already populates both, but this backfills any empty field
    # deterministically (no external AI) so the digest never ships
    # a blank prompt_seed or use_cases list.
    p5e_backfilled = 0
    for a, ana in zip(selected, analyses):
        ana, did = _ensure_prompt_fields(ana, a.get("id", "unknown"))
        if did:
            p5e_backfilled += 1

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
        analyses=analyses,
        md_path=md_path,
        html_path=html_path,
        strategy=args.strategy,
        index_path=INDEX_FILE,
        near_dup_mapping=near_dup_mapping,
    )

    # P6F: save history entry (runtime only, not tracked)
    if not args.dry_run:
        history_picks = []
        for rec in selected:
            history_picks.append({
                "id": rec.get("id", ""),
                "artist": rec.get("artist", ""),
                "category": rec.get("category", ""),
                "near_dup_cluster_id": near_dup_mapping.get(rec.get("id", ""), None),
            })
        history_entry = {
            "date": digest_date.isoformat(),
            "digest_path": _safe_rel(md_path),
            "picks": history_picks,
        }
        # Idempotent: replace existing entry for same date
        history_data["entries"] = [e for e in history_data.get("entries", []) if e.get("date") != history_entry["date"]]
        history_data["entries"].append(history_entry)
        # Keep newest first, safety cap at max(window_days*2, 60)
        history_data["entries"].sort(key=lambda e: e.get("date", ""), reverse=True)
        max_entries = max(window_days * 2, 60)
        history_data["entries"] = history_data["entries"][:max_entries]
        save_history(args.history_file, history_data, window_days)

    print(f"[✓] digest generated: {md_path.name} + {html_path.name}")
    print(f"    selected={len(selected)} strategy={args.strategy} "
          f"candidates={len(candidates)}")
    print(f"    Pillow={'on' if HAS_PIL else 'off (heuristic only)'}")
    print(f"    index updated: {INDEX_FILE}")
    print(f"    P5E: max_per_artist={max_per_artist}, "
          f"prompt-field backfills={p5e_backfilled}")
    print(f"    P6F: history_window={window_days} days, "
          f"near_dup_clusters_loaded={len(near_dup_mapping)} mappings, "
          f"history_entries={len(history_data.get('entries', []))}")
    # P5E: enforce artist cap. Print distribution so failures are
    # visible in the log (the same info goes into the markdown footer
    # via the candidate_pool_size line; this is a CLI echo).
    from collections import Counter as _C2
    _arts = [a.get('artist') or 'Anonymous' for a in selected]
    _arts_c = _C2(_arts)
    _repeats = {k: v for k, v in _arts_c.items() if v > 1}
    if _repeats:
        print(f"    P5E: WARN artist repeats: {_repeats}")
    else:
        print(f"    P5E: artist diversity OK (all unique)")
    if fallback_reason:
        print(f"    [note] {fallback_reason}")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        print(f"FATAL: digest build crashed: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        # Never crash the calling pipeline.
        sys.exit(EXIT_OK)