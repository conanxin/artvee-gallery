#!/usr/bin/env python3
"""Artvee Gallery Visual QA Analyzer (P5D).

Analyzes image/thumb/metadata quality across:
- Full web/data/artworks.json (default)
- --sample N
- --public-candidate PATH (publish demo subset)
- --digest-candidate PATH (5-pick daily digest)

Checks per record:
- Path existence (image_path, metadata_path, thumb_256, thumb_512)
- File sizes (image, thumb_256, thumb_512)
- Dimensions / aspect ratio (Pillow)
- Image mode (Pillow)
- Average brightness (Pillow)
- Color entropy (Pillow)
- Near-monochrome / blank / black / white risk (Pillow)
- Average perceptual hash (Pillow) for near-dup detection
- Metadata fields: source_url, category, artist, title
- Output risk_level (none/low/medium/high) + suggested_action

Pillow is optional; if unavailable, falls back to file size, path,
extension, and metadata-only checks. The script never modifies
source images, never copies, never embeds base64, never logs local
absolute paths in contact sheet output.

Output:
- --out PATH         : JSON report (default: stdout)
- --contact-sheet PATH : static HTML with relative thumb paths

Safety:
- Read-only on source tree
- No download / network calls
- No git operations
- contact sheet uses repo-relative paths (not absolute)
- The 4 unknown-source_url records (timeout losers) are flagged
  but not deleted
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web" / "data" / "artworks.json"
GALLERY_STATS = ROOT / "web" / "data" / "gallery_stats.json"
DIGESTS_JSON = ROOT / "web" / "data" / "digests.json"

# File-type allowlists
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
META_EXT = {".json"}

# Image-quality thresholds
TINY_IMAGE_BYTES = 5_000       # < 5KB image is suspect
TINY_THUMB_256_BYTES = 1_000   # < 1KB 256-thumb is suspect
TINY_THUMB_512_BYTES = 3_000   # < 3KB 512-thumb is suspect
EXTREME_ASPECT_RATIO = 4.0     # > 4:1 (very long banner)
NEAR_MONOCHROME_ENTROPY = 2.0  # color entropy < 2 bits = nearly mono
BRIGHT_BLANK = 0.95            # avg brightness > 0.95 = likely white/blank
DARK_BLANK = 0.05              # avg brightness < 0.05 = likely black/blank


def _strip(rel: str) -> str:
    """Strip leading ./ and ../ from a path string."""
    s = str(rel).replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    while s.startswith("../"):
        s = s[3:]
    return s.lstrip("/")


def _resolve_repo_path(rel: str) -> Path:
    """Resolve a web-data-relative path to an absolute path in repo.

    If rel is already an absolute path (candidate mode), return as-is.
    Otherwise, strip leading ./ and ../ and resolve relative to ROOT.
    """
    if not rel:
        return None  # type: ignore[return-value]
    if Path(rel).is_absolute():
        return Path(rel)
    return (ROOT / _strip(rel)).resolve()


def _strip_abs_path(p: str) -> str:
    """Convert an absolute path to a repo-relative path; defensively."""
    s = str(p)
    if s.startswith(str(ROOT)):
        s = s[len(str(ROOT)):].lstrip("/")
    return s


def _pillow_available() -> bool:
    try:
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


# ---- Image analysis (Pillow) ----------------------------------------------

def _analyze_image_pillow(path: Path) -> dict[str, Any]:
    """Open image and return visual metrics; never raises to caller."""
    from PIL import Image, ImageStat
    result: dict[str, Any] = {
        "opened": False,
        "width": None,
        "height": None,
        "mode": None,
        "avg_brightness": None,
        "color_entropy": None,
        "ahash": None,
        "issues": [],
    }
    if not path.exists():
        result["issues"].append("file_missing")
        return result
    try:
        with Image.open(path) as im:
            im.load()
            result["opened"] = True
            result["width"], result["height"] = im.size
            result["mode"] = im.mode
            # Convert to RGB for analysis
            try:
                rgb = im.convert("RGB")
            except Exception:
                result["issues"].append("rgb_convert_failed")
                return result
            # Average brightness
            try:
                stat = ImageStat.Stat(rgb)
                result["avg_brightness"] = sum(stat.mean) / (3 * 255.0)
            except Exception:
                result["issues"].append("stat_failed")
            # Color entropy: shannon entropy of 64-bin histogram
            try:
                hist = rgb.histogram()
                # Sum 3 channels
                total = 0
                bins: list[int] = []
                for ch in range(3):
                    channel = hist[ch * 256:(ch + 1) * 256]
                    total += sum(channel)
                    bins.extend(channel)
                if total > 0:
                    entropy = 0.0
                    for c in bins:
                        if c <= 0:
                            continue
                        p = c / total
                        entropy -= p * math.log2(p)
                    result["color_entropy"] = round(entropy, 3)
            except Exception:
                result["issues"].append("entropy_failed")
            # Perceptual aHash (8x8, 64 bits)
            try:
                small = rgb.resize((8, 8), Image.Resampling.LANCZOS)
                gray = small.convert("L")
                pixels = list(gray.getdata())
                avg = sum(pixels) / len(pixels)
                bits = "".join("1" if p > avg else "0" for p in pixels)
                # Convert to hex string (16 hex chars = 64 bits)
                result["ahash"] = hex(int(bits, 2))[2:].rjust(16, "0")
            except Exception:
                result["issues"].append("ahash_failed")
    except Exception as e:
        result["issues"].append(f"open_failed: {type(e).__name__}")
    return result


def _analyze_image_fallback(path: Path) -> dict[str, Any]:
    """Fallback when Pillow unavailable: size and extension only."""
    result: dict[str, Any] = {
        "opened": False,
        "width": None,
        "height": None,
        "mode": None,
        "avg_brightness": None,
        "color_entropy": None,
        "ahash": None,
        "issues": [],
    }
    if not path.exists():
        result["issues"].append("file_missing")
        return result
    result["opened"] = True
    # Try to read dimensions via stdlib (no Pillow)
    try:
        from PIL import Image  # noqa
    except Exception:
        pass
    return result


# ---- Risk classification --------------------------------------------------

def _classify_risk(
    record: dict[str, Any],
    image_meta: dict[str, Any],
    image_size: int | None,
    thumb_256_size: int | None,
    thumb_512_size: int | None,
    is_candidate: bool = False,
) -> dict[str, Any]:
    """Return risk_level, issues, visual_notes, suggested_action."""
    issues: list[str] = []
    visual_notes: list[str] = []
    image_path_exists = "image_path_missing" not in (image_meta.get("issues") or [])
    thumb_256_exists = thumb_256_size is not None and thumb_256_size > 0
    thumb_512_exists = thumb_512_size is not None and thumb_512_size > 0
    image_exists = image_size is not None and image_size > 0

    # 1. File-existence
    if not record.get("image_path"):
        issues.append("image_path_missing")
    # metadata_path is intentionally absent from public candidates
    # (P3E safety guard: no metadata/ shipped). Don't flag in candidate.
    if not record.get("metadata_path") and not is_candidate:
        issues.append("metadata_path_missing")
    if not record.get("thumb_256"):
        issues.append("thumb_256_missing")
    if not record.get("thumb_512"):
        issues.append("thumb_512_missing")
    if record.get("image_path") and not image_exists:
        issues.append("image_file_missing")
    if record.get("thumb_256") and not thumb_256_exists:
        issues.append("thumb_256_file_missing")
    if record.get("thumb_512") and not thumb_512_exists:
        issues.append("thumb_512_file_missing")

    # 2. Metadata fields
    if not record.get("source_url"):
        issues.append("source_url_missing")
    if not record.get("category"):
        issues.append("category_missing")
    if not record.get("artist"):
        issues.append("artist_missing")
    if not record.get("title"):
        issues.append("title_missing")

    # 3. File sizes
    if image_exists and image_size is not None and image_size < TINY_IMAGE_BYTES:
        issues.append("tiny_image_file")
    if thumb_256_exists and thumb_256_size is not None and thumb_256_size < TINY_THUMB_256_BYTES:
        issues.append("tiny_thumb_256")
    if thumb_512_exists and thumb_512_size is not None and thumb_512_size < TINY_THUMB_512_BYTES:
        issues.append("tiny_thumb_512")

    # 4. Pillow-derived checks
    if image_meta.get("opened") is False and image_exists:
        if "open_failed" in " ".join(image_meta.get("issues") or []):
            issues.append("corrupt_or_unreadable_image")
    if image_meta.get("avg_brightness") is not None:
        b = image_meta["avg_brightness"]
        if b > BRIGHT_BLANK:
            issues.append("blank_or_white_risk")
            visual_notes.append(f"avg_brightness={b:.3f} (high)")
        elif b < DARK_BLANK:
            issues.append("blank_or_black_risk")
            visual_notes.append(f"avg_brightness={b:.3f} (low)")
    if image_meta.get("color_entropy") is not None:
        e = image_meta["color_entropy"]
        if e < NEAR_MONOCHROME_ENTROPY:
            issues.append("near_monochrome")
            visual_notes.append(f"color_entropy={e:.3f} (low)")

    # 5. Dimensions / aspect ratio
    w, h = image_meta.get("width"), image_meta.get("height")
    if w and h and w > 0 and h > 0:
        ratio = max(w / h, h / w)
        if ratio > EXTREME_ASPECT_RATIO:
            issues.append("extreme_aspect_ratio")
            visual_notes.append(f"aspect={w}x{h} (ratio={ratio:.2f})")
    elif w is not None and h is not None:
        issues.append("zero_or_unknown_dimensions")

    # 6. Risk level
    high_markers = {
        "image_file_missing", "thumb_256_file_missing", "thumb_512_file_missing",
        "corrupt_or_unreadable_image", "blank_or_white_risk", "blank_or_black_risk",
    }
    medium_markers = {
        "tiny_image_file", "tiny_thumb_256", "tiny_thumb_512",
        "near_monochrome", "extreme_aspect_ratio", "source_url_missing",
    }
    low_markers = {
        "category_missing", "artist_missing", "title_missing",
        "image_path_missing", "metadata_path_missing",
        "thumb_256_missing", "thumb_512_missing",
        "zero_or_unknown_dimensions",
    }
    if issues and all(i in high_markers for i in issues):
        risk = "high"
    elif any(i in high_markers for i in issues):
        risk = "high"
    elif any(i in medium_markers for i in issues):
        risk = "medium"
    elif any(i in low_markers for i in issues):
        risk = "low"
    else:
        risk = "none"

    # 7. Suggested action
    if "corrupt_or_unreadable_image" in issues or any(
        i in issues for i in (
            "image_file_missing", "blank_or_white_risk",
            "blank_or_black_risk",
        )
    ):
        action = "exclude_from_public_demo"
    elif "near_monochrome" in issues or "extreme_aspect_ratio" in issues:
        action = "review"
    elif "tiny_image_file" in issues or "tiny_thumb_256" in issues or "tiny_thumb_512" in issues:
        action = "review"
    elif risk == "high":
        action = "exclude_from_public_demo"
    elif risk == "medium":
        action = "review"
    elif risk == "low":
        action = "keep"
    else:
        action = "keep"

    # Digest-specific: digest builds only from "none" or "low" risk
    if risk in ("high", "medium"):
        # Medium may or may not be excluded from digest depending on visual_notes
        pass

    return {
        "risk_level": risk,
        "issues": issues,
        "visual_notes": visual_notes,
        "suggested_action": action,
    }


# ---- Per-record analysis --------------------------------------------------

def _analyze_record(rec: dict[str, Any], use_pillow: bool) -> dict[str, Any]:
    """Analyze one artwork record end-to-end.

    is_candidate=True: candidate mode (public demo / digest). The
    candidate does not ship original images or metadata/; only
    thumbs. So we:
      - tolerate empty metadata_path
      - expect image_path to be the 512 thumb (no separate image file)
    """
    is_candidate = bool(rec.get("is_candidate"))
    image_path_str = rec.get("image_path", "")
    image_path = _resolve_repo_path(image_path_str) if image_path_str else None
    thumb_256_str = rec.get("thumb_256", "")
    thumb_512_str = rec.get("thumb_512", "")
    thumb_256_path = _resolve_repo_path(thumb_256_str) if thumb_256_str else None
    thumb_512_path = _resolve_repo_path(thumb_512_str) if thumb_512_str else None

    image_size = image_path.stat().st_size if image_path and image_path.exists() else None
    thumb_256_size = thumb_256_path.stat().st_size if thumb_256_path and thumb_256_path.exists() else None
    thumb_512_size = thumb_512_path.stat().st_size if thumb_512_path and thumb_512_path.exists() else None

    if use_pillow and image_path:
        image_meta = _analyze_image_pillow(image_path)
    elif image_path:
        image_meta = _analyze_image_fallback(image_path)
    else:
        image_meta = {"opened": False, "issues": ["path_missing"], "width": None, "height": None, "avg_brightness": None, "color_entropy": None, "ahash": None}

    risk = _classify_risk(rec, image_meta, image_size, thumb_256_size, thumb_512_size, is_candidate=is_candidate)

    # Preserve any extra fields from the source record (digest-specific
    # metadata like use_case, prompt_seed, visual_notes_md)
    extra_keys = set(rec.keys()) - {
        "id", "title", "artist", "category", "source_url",
        "image_path", "metadata_path", "thumb_256", "thumb_512",
        "is_candidate",
    }
    result = {
        "id": rec.get("id", "<no-id>"),
        "title": rec.get("title", ""),
        "artist": rec.get("artist", ""),
        "category": rec.get("category", ""),
        "source_url": rec.get("source_url", ""),
        "image_size_bytes": image_size,
        "thumb_256_size_bytes": thumb_256_size,
        "thumb_512_size_bytes": thumb_512_size,
        "image_width": image_meta.get("width"),
        "image_height": image_meta.get("height"),
        "image_mode": image_meta.get("mode"),
        "avg_brightness": image_meta.get("avg_brightness"),
        "color_entropy": image_meta.get("color_entropy"),
        "ahash": image_meta.get("ahash"),
        "image_meta_issues": image_meta.get("issues") or [],
        **risk,
    }
    # Merge in extras (e.g., use_case, prompt_seed)
    for k in extra_keys:
        if k not in result:
            result[k] = rec.get(k)
    return result


# ---- Summary statistics ---------------------------------------------------

def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    risk_counts = Counter(r["risk_level"] for r in records)
    cat_counts = Counter(r["category"] or "<missing>" for r in records)
    artist_counts = Counter(r["artist"] or "<missing>" for r in records)
    issue_counts = Counter()
    for r in records:
        for i in r.get("issues") or []:
            issue_counts[i] += 1
    action_counts = Counter(r["suggested_action"] for r in records)

    # Aspect ratio distribution (use existing width/height)
    ratios = []
    for r in records:
        w, h = r.get("image_width"), r.get("image_height")
        if w and h and w > 0 and h > 0:
            ratios.append(max(w / h, h / w))
    aspect_buckets = {
        "1.0-1.5": sum(1 for x in ratios if 1.0 <= x < 1.5),
        "1.5-2.0": sum(1 for x in ratios if 1.5 <= x < 2.0),
        "2.0-3.0": sum(1 for x in ratios if 2.0 <= x < 3.0),
        "3.0-4.0": sum(1 for x in ratios if 3.0 <= x < 4.0),
        "4.0+":    sum(1 for x in ratios if 4.0 <= x),
    }

    return {
        "total_records": total,
        "checked_records": total,
        "category_counts": dict(cat_counts.most_common()),
        "artist_top10": dict(artist_counts.most_common(10)),
        "risk_counts": dict(risk_counts),
        "issue_counts": dict(issue_counts.most_common()),
        "action_counts": dict(action_counts),
        "aspect_ratio_buckets": aspect_buckets,
        "public_demo_exclusion_candidates": action_counts.get("exclude_from_public_demo", 0),
        "digest_exclusion_candidates": sum(
            1 for r in records
            if r["risk_level"] in ("high",) or "near_monochrome" in (r.get("issues") or [])
        ),
    }


# ---- Near-duplicate detection (aHash) -------------------------------------

def _near_duplicate_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group records by aHash; report groups with >1 record."""
    by_hash: dict[str, list[str]] = defaultdict(list)
    for r in records:
        h = r.get("ahash")
        if h:
            by_hash[h].append(r["id"])
    return [
        {"ahash": h, "ids": ids}
        for h, ids in sorted(by_hash.items(), key=lambda kv: -len(kv[1]))
        if len(ids) > 1
    ]


# ---- Contact sheet HTML ---------------------------------------------------

def _write_contact_sheet(records: list[dict[str, Any]], out_path: Path) -> None:
    """Write a static HTML contact sheet with relative paths."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in records:
        # Use the 256-thumb for the contact sheet (smaller load)
        thumb_rel = _strip(r.get("thumb_256") or r.get("image_path") or "")
        # Defensive: never include abs path
        if thumb_rel.startswith("/"):
            thumb_rel = thumb_rel.lstrip("/")
        risk_class = r["risk_level"]
        risk_color = {
            "none": "#0a8a3a",
            "low": "#7a9a14",
            "medium": "#b08000",
            "high": "#b03020",
        }.get(risk_class, "#666")
        action_color = {
            "keep": "#0a8a3a",
            "review": "#b08000",
            "exclude_from_public_demo": "#b03020",
            "exclude_from_digest": "#b03020",
        }.get(r["suggested_action"], "#666")
        issues = "<br>".join(r.get("issues") or []) or "—"
        notes = "<br>".join(r.get("visual_notes") or []) or "—"
        rows.append(
            f'<tr>'
            f'<td><a href="{thumb_rel}" target="_blank">'
            f'<img src="{thumb_rel}" loading="lazy" width="128" height="128" '
            f'style="object-fit:cover;border:1px solid #ccc;border-radius:2px;" '
            f'alt=""></a></td>'
            f'<td><b>{_html(r.get("title", ""))}</b><br>'
            f'<span style="color:#666">{_html(r.get("artist", ""))}</span><br>'
            f'<span style="color:#888">{_html(r.get("category", ""))}</span></td>'
            f'<td><span style="color:#888">{_html(_strip(r.get("source_url", "")))}</span></td>'
            f'<td><span style="color:{risk_color};font-weight:bold">{risk_class.upper()}</span></td>'
            f'<td><span style="color:#444">{issues}</span></td>'
            f'<td><span style="color:#666">{notes}</span></td>'
            f'<td><span style="color:{action_color}">{_html(r.get("suggested_action", ""))}</span></td>'
            f'</tr>'
        )

    counts = Counter(r["risk_level"] for r in records)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Artvee Gallery · P5D Visual QA Contact Sheet</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; margin: 24px; color: #222; }}
h1 {{ font-size: 20px; margin: 0 0 8px 0; }}
.summary {{ color: #555; margin-bottom: 16px; }}
.summary b {{ color: #000; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid #e2e2e2; text-align: left; vertical-align: top; font-size: 13px; }}
th {{ background: #f4f4f4; font-weight: 600; }}
tr:hover {{ background: #fafafa; }}
</style>
</head>
<body>
<h1>Artvee Gallery · P5D Visual QA Contact Sheet</h1>
<div class="summary">
Generated: {_html(datetime.now().isoformat(timespec="seconds"))} ·
Total: <b>{len(records)}</b> ·
none: <b>{counts.get("none", 0)}</b> ·
low: <b>{counts.get("low", 0)}</b> ·
medium: <b>{counts.get("medium", 0)}</b> ·
high: <b>{counts.get("high", 0)}</b>
</div>
<table>
<thead><tr>
<th>Thumb</th><th>Title / Artist / Cat</th><th>Source URL</th>
<th>Risk</th><th>Issues</th><th>Visual notes</th><th>Action</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def _html(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---- Candidate parsing (public demo / digest) ----------------------------

def _load_public_demo_records(candidate_path: Path) -> list[dict[str, Any]]:
    """Load public-demo candidate from dist/refresh-candidates/.../gallery/.

    Expected layout (per P3E safety guards, no metadata/ shipped):
        gallery/index.html
        gallery/data/artworks.json
        gallery/assets/thumbs/256/<id>.jpg
        gallery/assets/thumbs/512/<id>.jpg   (also used as image_path in JSON)
    Note: in candidate JSON, image_path == thumb_512 path (original
    images are not shipped; the 512 thumb serves as the image).
    """
    records: list[dict[str, Any]] = []
    web_json = candidate_path / "data" / "artworks.json"
    if not web_json.exists():
        web_json = candidate_path / "artworks.json"
    if not web_json.exists():
        print(f"WARN: no artworks.json in {candidate_path}", file=sys.stderr)
        return records
    data = json.loads(web_json.read_text(encoding="utf-8"))
    for a in data:
        image_path_str = a.get("image_path", "")
        thumb_256_str = a.get("thumb_256", "")
        thumb_512_str = a.get("thumb_512", "")
        # In candidate mode, all three point to thumbs (no original
        # images shipped). Resolve all as absolute paths.
        rec = {
            "id": a.get("id", ""),
            "title": a.get("title", ""),
            "artist": a.get("artist", ""),
            "category": a.get("category", ""),
            "source_url": a.get("source_url", ""),
            # In candidate mode, no metadata/ shipped; mark explicitly
            "metadata_path": "",
            "image_path": str((candidate_path / image_path_str).resolve()) if image_path_str else "",
            "thumb_256": str((candidate_path / thumb_256_str).resolve()) if thumb_256_str else "",
            "thumb_512": str((candidate_path / thumb_512_str).resolve()) if thumb_512_str else "",
            "is_candidate": True,
        }
        records.append(rec)
    return records


def _load_digest_records(candidate_path: Path) -> list[dict[str, Any]]:
    """Load digest candidate from dist/refresh-candidates/.../digest/.

    digests.json is a list of digest entries (one per date) with
    markdown_path / html_path pointers. To get the actual picks,
    parse digest.html <img> tags (preferred, has alt= as title)
    and digest.md (for category / source_url / artist / prompt).
    """
    records: list[dict[str, Any]] = []
    # 1. Parse digest.html for image references (preferred)
    html = candidate_path / "digest.html"
    md = candidate_path / "digest.md"
    img_meta: list[dict[str, str]] = []  # [{src, alt}]
    if html.exists():
        text = html.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>', text):
            src, alt = m.group(1), m.group(2)
            img_meta.append({"src": src, "alt": alt})
        # also try alt before src
        if not img_meta:
            for m in re.finditer(r'<img[^>]+alt="([^"]*)"[^>]+src="([^"]+)"[^>]*>', text):
                alt, src = m.group(1), m.group(2)
                img_meta.append({"src": src, "alt": alt})
    if not img_meta and md.exists():
        # fallback: parse md image syntax ![alt](./path)
        text = md.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', text):
            alt, src = m.group(1), m.group(2)
            img_meta.append({"src": src, "alt": alt})

    # 2. Parse digest.md for category / artist / source_url per pick
    md_blocks: list[dict[str, str]] = []
    if md.exists():
        text = md.read_text(encoding="utf-8", errors="replace")
        # split by ### N. headers
        blocks = re.split(r'\n###\s+\d+\.\s+', text)
        # first block is header info, skip
        for block in blocks[1:]:
            entry: dict[str, str] = {"id": "", "title": "", "artist": "",
                                     "category": "", "source_url": ""}
            # First line is "Title — Artist"
            head = block.split("\n", 1)[0].strip()
            if "—" in head:
                title, artist = head.split("—", 1)
                entry["title"] = title.strip()
                entry["artist"] = artist.strip()
            else:
                entry["title"] = head
            # category
            m = re.search(r'分类：(\S+)', block)
            if m:
                entry["category"] = m.group(1)
            # source_url
            m = re.search(r'来源：(\S+)', block)
            if m:
                entry["source_url"] = m.group(1)
            # use case
            m = re.search(r'用途：(.+)', block)
            if m:
                entry["use_case"] = m.group(1).strip()
            # prompt seed
            m = re.search(r'Prompt seed：\s*`?([^`\n]+)`?', block)
            if m:
                entry["prompt_seed"] = m.group(1).strip()
            # visual notes
            visuals = re.findall(r'视觉：(.+)', block)
            if visuals:
                entry["visual_notes"] = visuals
            md_blocks.append(entry)

    # 3. Combine: zip img_meta with md_blocks
    for i, img in enumerate(img_meta):
        src = img["src"]
        alt = img["alt"]
        # Resolve path
        abs_img_path = str((candidate_path / src).resolve())
        # Find matching md block
        block = md_blocks[i] if i < len(md_blocks) else {}
        # Use src basename as id
        file_stem = Path(src).stem
        rec = {
            "id": file_stem,
            "title": block.get("title", alt),
            "artist": block.get("artist", ""),
            "category": block.get("category", ""),
            "source_url": block.get("source_url", ""),
            "use_case": block.get("use_case", ""),
            "prompt_seed": block.get("prompt_seed", ""),
            "visual_notes_md": block.get("visual_notes", []),
            "image_path": abs_img_path,
            "thumb_256": abs_img_path,
            "thumb_512": abs_img_path,
            "metadata_path": "",  # candidates don't ship metadata/
            "is_candidate": True,
        }
        records.append(rec)
    return records


# ---- Main -----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Artvee Visual QA")
    ap.add_argument("--sample", type=int, default=0,
                    help="Sample N records from web/data (0 = all)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Write JSON result to this path (relative to repo root)")
    ap.add_argument("--contact-sheet", type=Path, default=None,
                    help="Write HTML contact sheet to this path")
    ap.add_argument("--public-candidate", type=Path, default=None,
                    help="Analyze the public demo candidate (gallery subdir)")
    ap.add_argument("--digest-candidate", type=Path, default=None,
                    help="Analyze the digest candidate (digest subdir)")
    ap.add_argument("--seed", type=int, default=20260612,
                    help="Random seed for --sample")
    args = ap.parse_args()

    use_pillow = _pillow_available()
    print(f"[*] Pillow available: {use_pillow}")

    # Load records based on mode
    if args.public_candidate:
        candidate_root = (ROOT / args.public_candidate).resolve()
        records_input = _load_public_demo_records(candidate_root)
        mode = f"public-candidate:{args.public_candidate}"
    elif args.digest_candidate:
        candidate_root = (ROOT / args.digest_candidate).resolve()
        records_input = _load_digest_records(candidate_root)
        mode = f"digest-candidate:{args.digest_candidate}"
    else:
        web = json.loads(WEB_DATA.read_text(encoding="utf-8"))
        records_input = web
        mode = "full-web-data"

    if args.sample > 0 and len(records_input) > args.sample:
        rng = random.Random(args.seed)
        records_input = rng.sample(records_input, args.sample)
        mode = f"{mode} (sample={args.sample})"

    print(f"[*] Mode: {mode}")
    print(f"[*] Records to analyze: {len(records_input)}")

    analyzed = []
    for rec in records_input:
        try:
            analyzed.append(_analyze_record(rec, use_pillow))
        except Exception as e:
            print(f"WARN: failed on {rec.get('id', '?')}: {e}", file=sys.stderr)

    summary = _summary(analyzed)
    summary["near_duplicate_groups"] = _near_duplicate_groups(analyzed)
    summary["mode"] = mode
    summary["ts"] = datetime.now().isoformat(timespec="seconds")
    summary["pillow_available"] = use_pillow
    summary["record_count"] = len(analyzed)

    result = {
        "summary": summary,
        "records": analyzed,
    }

    # Write JSON
    if args.out:
        out = (ROOT / args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[*] JSON written: {out.relative_to(ROOT)}")

    # Write contact sheet
    if args.contact_sheet:
        cs = (ROOT / args.contact_sheet).resolve()
        _write_contact_sheet(analyzed, cs)
        print(f"[*] Contact sheet: {cs.relative_to(ROOT)}")

    # Stdout summary
    s = summary
    print("\n=== Summary ===")
    print(f"  total:               {s['total_records']}")
    print(f"  risk none:           {s['risk_counts'].get('none', 0)}")
    print(f"  risk low:            {s['risk_counts'].get('low', 0)}")
    print(f"  risk medium:         {s['risk_counts'].get('medium', 0)}")
    print(f"  risk high:           {s['risk_counts'].get('high', 0)}")
    print(f"  issues top:          {dict(list(s['issue_counts'].items())[:8])}")
    print(f"  actions:             {s['action_counts']}")
    print(f"  near-dup groups:     {len(s['near_duplicate_groups'])}")
    print(f"  public_demo_exclude: {s['public_demo_exclusion_candidates']}")
    print(f"  digest_exclude:      {s['digest_exclusion_candidates']}")
    print(f"  aspect buckets:      {s['aspect_ratio_buckets']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
