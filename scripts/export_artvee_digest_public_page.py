#!/usr/bin/env python3
"""
Artvee Daily Digest · Public Page Exporter (P3E)
==================================================

Reads the latest daily digest and produces a lightweight, self-contained
public page that can be hosted on any static server (e.g. GitHub Pages).

Inputs (read-only, never modified)
----------------------------------
- ``digests/artvee-digest-YYYY-MM-DD.md``   (Markdown)
- ``digests/artvee-digest-YYYY-MM-DD.html`` (styled HTML)
- ``web/data/digests.json``                  (rolling index)
- ``thumbs/512/``                            (only the thumbnails referenced
  by the chosen digest are copied; ``images/`` and ``metadata/`` are NOT
  read or copied)

Output
------
::

    <out-dir>/
    ├── index.html       (lightweight landing page)
    ├── digest.html      (rewritten copy of the daily digest)
    ├── digest.md        (rewritten copy of the daily digest markdown)
    ├── style.css        (copy of ``web/style.css``)
    ├── data/
    │   └── digests.json (only the chosen date's entry)
    └── assets/
        └── thumbs/
            └── 512/
                └── <referenced thumbs only>

Path rewriting
--------------
The source digest's image references look like::

    ../thumbs/512/Utagawa_Kuniyoshi_…_standard.jpg      (Markdown)
    <img src="../thumbs/512/…">                          (HTML)

Both are rewritten to ``./assets/thumbs/512/<filename>`` (or whatever
``--base-url`` resolves to). The original ``../web/style.css`` link in
the digest HTML is rewritten to ``./style.css``.

A final leak check runs after the rewrite; if any of the forbidden
substrings (``/home/``, ``~/``, ``hermes-agent``, ``metadata/``,
``images/``) is still present in any text output, the script exits
non-zero (4) and the operator is expected to investigate.

Exit codes
----------
- ``0`` ok
- ``2`` source missing
- ``3`` bad argument
- ``4`` post-export leak check failed
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIGESTS_DIR = BASE_DIR / "digests"
SRC_DATA = BASE_DIR / "web" / "data"
SRC_THUMBS_512 = BASE_DIR / "thumbs" / "512"
SRC_THUMBS_256 = BASE_DIR / "thumbs" / "256"
SRC_WEB = BASE_DIR / "web"
DEFAULT_OUT = BASE_DIR / "dist" / "artvee-gallery-digest-public"

# Public page metadata (fixed per release; safe to publish).
PROJECT_NAME = "Artvee Daily Digest"
GALLERY_DEMO_URL = "https://conanxin.github.io/projects/artvee-gallery-demo/"
REPO_URL = "https://github.com/conanxin/artvee-gallery"
# P8B: release tag is read from `git describe --tags --abbrev=0` at
# export time. The previous P3E hard-coded "v0.1.0-alpha" which has
# long been superseded; the new value tracks whatever the Artvee
# repo's latest tag is.
DEFAULT_RELEASE_TAG = "v0.2.0"

# Path-rewrite regex. We match the local relative path shape used by the
# digest builder; the rewritten target always points under assets/thumbs/512.
# The ``../`` prefix is required to avoid matching inline body text that
# happens to mention the directory (e.g. ``缩略图：`thumbs/512/`...``).
RE_THUMB_REL = re.compile(
    r"""
    \.\./thumbs/512/              # required prefix
    (?P<basename>[^\s"'<>)\]]+)   # filename
    """,
    re.VERBOSE,
)
RE_STYLE_REL = re.compile(r"""\.\./web/style\.css""")
RE_STYLE_HREF = re.compile(r"""href=["']\.\./web/style\.css["']""")

# Forbidden substrings (post-export).
FORBIDDEN_SUBSTRINGS = ("/home/", "~/", "hermes-agent", "metadata/", "images/")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path):
    if not path.exists():
        print(f"ERROR: source not found: {path}", file=sys.stderr)
        sys.exit(2)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def slug_to_thumb256_basename(pick_id: str) -> str:
    """Convert a pick `id` to the 256-thumbnail basename used by the
    public bundle (i.e. ``assets/thumbs/256/<id>.jpg``). The 256
    variant is intentionally smaller than 512 — the archive page
    can show many cards and we want a thumbnail, not a hero image.

    The pick's `id` already contains the safe filename component
    used by the gallery pipeline; the 256 thumbnail mirrors it
    under the ``thumbs/256/`` directory (P2-era convention).
    """
    if not pick_id:
        return ""
    # pick_id is already file-system safe (lowercase + hex suffix)
    return f"{pick_id}.jpg"


def summarize_history(history: dict) -> dict:
    """Compute the P8C archive summary block.

    Returns a dict with:
        - ``total_days``        — number of entries
        - ``total_picks``       — sum of picks across all entries
        - ``unique_artists``    — distinct artist strings
        - ``top_categories``    — top-5 categories by total pick count
        - ``available_range``   — {first_date, latest_date} (or None)

    The summary is computed from the public-safe history dict
    (the digest builder's redacted ``digest_path`` has already
    been stripped by the caller in P8B).
    """
    entries = history.get("entries", []) or []
    total_picks = 0
    artists: set[str] = set()
    cat_counts: dict[str, int] = {}
    for e in entries:
        for p in (e.get("picks") or []):
            total_picks += 1
            art = (p.get("artist") or "").strip()
            if art:
                artists.add(art)
            cat = (p.get("category") or "").strip()
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
    top_cats = sorted(
        ({"category": c, "count": n} for c, n in cat_counts.items()),
        key=lambda x: (-x["count"], x["category"]),
    )[:5]
    dates = sorted(e.get("date", "") for e in entries if e.get("date"))
    return {
        "total_days": len(entries),
        "total_picks": total_picks,
        "unique_artists": len(artists),
        "top_categories": top_cats,
        "available_range": {
            "first_date": dates[0] if dates else None,
            "latest_date": dates[-1] if dates else None,
        },
    }


def find_latest_date(entries: list[dict]) -> str:
    """Return the date string of the latest entry."""
    if not entries:
        print("ERROR: digests.json is empty", file=sys.stderr)
        sys.exit(2)
    return max(e.get("date", "") for e in entries)


def detect_release_tag(base_dir: Path) -> str:
    """Return the most recent git tag for the Artvee repo, falling
    back to `DEFAULT_RELEASE_TAG` if git is unavailable or no tag
    exists. Never raises. P8B moved the previous hard-coded
    `v0.1.0-alpha` to a runtime detection so the public digest
    page always shows the current release line.
    """
    try:
        out = subprocess.run(  # noqa: S603 — local git only
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(base_dir), capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return DEFAULT_RELEASE_TAG


def load_digest_history(base_dir: Path) -> dict | None:
    """Load the rolling 30-day digest history (P6F).

    Returns the parsed JSON dict, or `None` if the file does not
    exist. The file lives at
    `<base>/reports/runtime/digest-history.json` and is generated
    by the daily digest builder. The public archive uses this
    data — never the live `digests/` folder — so the archive
    shows *what was actually picked each day*, not just the
    latest digest's picks.
    """
    candidates = [
        base_dir / "reports" / "runtime" / "digest-history.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                print(f"WARN: digest-history.json present but unreadable: {e}",
                      file=sys.stderr)
                return None
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Export the latest (or a specified) Artvee daily digest as a "
            "self-contained public page."
        )
    )
    p.add_argument(
        "--date",
        default=None,
        help="Digest date in YYYY-MM-DD. Default: latest entry in "
             "web/data/digests.json.",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT,
        help="Output directory (default: dist/artvee-gallery-digest-public).",
    )
    p.add_argument(
        "--base-url",
        default=".",
        help="Base URL prefix for rewritten paths (default: '.').",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the export but do not write any files.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Path rewriting
# ---------------------------------------------------------------------------

def rewrite_thumb_refs(text: str, base_url: str) -> str:
    """Rewrite ``../thumbs/512/<basename>`` and ``thumbs/512/<basename>``
    references to ``<base_url>/assets/thumbs/512/<basename>``."""
    base = base_url.rstrip("/") if base_url else "."

    def _repl(m: re.Match) -> str:
        return f"{base}/assets/thumbs/512/{m.group('basename')}"

    return RE_THUMB_REL.sub(_repl, text)


def rewrite_style_link_html(text: str, base_url: str) -> str:
    """Rewrite the digest HTML's relative style.css link to the local
    style.css under the export directory."""
    base = base_url.rstrip("/") if base_url else "."
    return RE_STYLE_HREF.sub(f'href="{base}/style.css"', text)


def rewrite_style_link_md(text: str, base_url: str) -> str:
    base = base_url.rstrip("/") if base_url else "."
    return RE_STYLE_REL.sub(f"{base}/style.css", text)


# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{base}/style.css">
<style>
  body.digest-index {{
    max-width: 880px; margin: 3rem auto; padding: 0 1rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                 sans-serif;
    color: #1f2328;
  }}
  h1 {{ margin: 0 0 0.25rem; font-size: 1.6rem; }}
  p.lead {{ color: #555; margin: 0 0 1.25rem; }}
  .meta {{ background: #f3f4f6; padding: 0.75rem 1rem; border-radius: 6px;
          margin-bottom: 1.25rem; font-size: 0.95rem; }}
  .meta span {{ display: inline-block; margin-right: 1rem; }}
  ul.links {{ list-style: none; padding: 0; margin: 0; }}
  ul.links li {{ padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; }}
  ul.links a {{ color: #2563eb; text-decoration: none; }}
  ul.links a:hover {{ text-decoration: underline; }}
  footer {{ margin-top: 2rem; color: #888; font-size: 0.85rem; }}
  code {{ background: #f3f4f6; padding: 0.1rem 0.4rem; border-radius: 3px;
         font-size: 0.9em; }}
</style>
</head>
<body class="digest-index">
<h1>{title}</h1>
<p class="lead">A lightweight daily inspiration page generated from a
local Artvee Gallery workflow. Source data is public-domain (artvee.com).</p>

<div class="meta">
  <span><strong>Latest digest:</strong> {date}</span>
  <span><strong>Selected count:</strong> {count}</span>
  <span><strong>Categories:</strong> {cats}</span>
  <span><strong>Artists:</strong> {artists}</span>
  <span><strong>Strategy:</strong> {strategy}</span>
</div>

<ul class="links">
  <li>📄 <a href="{base}/digest.html">View HTML version of the latest digest</a></li>
  <li>📝 <a href="{base}/digest.md">View Markdown source of the latest digest</a></li>
  <li>🖼️ <a href="{base}/data/digests.json" target="_blank" rel="noopener">Digest index (data/digests.json)</a></li>
  <li>🎨 <a href="{gallery_url}" target="_blank" rel="noopener">Browse the public Artvee Gallery demo</a> (curated thumbnail subset)</li>
  <li>📦 <a href="{repo_url}" target="_blank" rel="noopener">Open-source repository</a> ({release_tag})</li>
</ul>

<footer>
  Public-domain source: <a href="https://artvee.com/" target="_blank" rel="noopener">artvee.com</a>.
  This bundle contains only thumbnails (no full original assets, no per-artwork
  metadata, no local paths).
</footer>
</body>
</html>
"""


def render_index(
    base_url: str,
    date: str,
    entry: dict,
    history: dict | None = None,
    release_tag: str = DEFAULT_RELEASE_TAG,
) -> str:
    base = base_url.rstrip("/") if base_url else "."
    cats = ", ".join(entry.get("categories", [])) or "—"
    artists = ", ".join(entry.get("artists", [])) or "—"
    history_block = ""
    if history is not None:
        entries = history.get("entries", [])
        # P8B: surface the archive section as a "see also" block,
        # not as the primary CTA. The latest digest is still the
        # main content.
        history_block = (
            '  <p class="lead">A lightweight daily inspiration page generated from a\n'
            '    local Artvee Gallery workflow. Source data is public-domain (artvee.com).\n'
            '    Each day selects 1–5 works with artist diversity and near-duplicate awareness.</p>\n'
            '  <div class="meta">\n'
            f'    <span><strong>Latest digest:</strong> {date}</span>\n'
            f'    <span><strong>Selected count:</strong> {entry.get("selected_count", 0)}</span>\n'
            f'    <span><strong>Categories:</strong> {escape(cats)}</span>\n'
            f'    <span><strong>Artists:</strong> {escape(artists)}</span>\n'
            f'    <span><strong>Strategy:</strong> {escape(entry.get("strategy", ""))}</span>\n'
            f'    <span><strong>Release:</strong> {escape(release_tag)}</span>\n'
            f'    <span><strong>30-day entries:</strong> {len(entries)}</span>\n'
            '  </div>\n'
        )
    else:
        history_block = (
            '  <p class="lead">A lightweight daily inspiration page generated from a\n'
            '    local Artvee Gallery workflow. Source data is public-domain (artvee.com).</p>\n'
            '  <div class="meta">\n'
            f'    <span><strong>Latest digest:</strong> {date}</span>\n'
            f'    <span><strong>Selected count:</strong> {entry.get("selected_count", 0)}</span>\n'
            f'    <span><strong>Categories:</strong> {escape(cats)}</span>\n'
            f'    <span><strong>Artists:</strong> {escape(artists)}</span>\n'
            f'    <span><strong>Strategy:</strong> {escape(entry.get("strategy", ""))}</span>\n'
            f'    <span><strong>Release:</strong> {escape(release_tag)}</span>\n'
            '  </div>\n'
        )
    archive_link = ""
    if history is not None:
        archive_link = (
            f'  <li>📚 <a href="{base}/archive.html">Browse the 30-day digest archive</a> '
            f'(<span class="p8b-archive-count">{len(history.get("entries", []))}</span> days)</li>\n'
        )
    return (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{escape(PROJECT_NAME)}</title>\n'
        f'<link rel="stylesheet" href="{base}/style.css">\n'
        '<style>\n'
        '  body.digest-index {\n'
        '    max-width: 880px; margin: 3rem auto; padding: 0 1rem;\n'
        '    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",\n'
        '                 "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",\n'
        '                 sans-serif;\n'
        '    color: #1f2328;\n'
        '  }\n'
        '  h1 { margin: 0 0 0.25rem; font-size: 1.6rem; }\n'
        '  p.lead { color: #555; margin: 0 0 1.25rem; }\n'
        '  .meta { background: #f3f4f6; padding: 0.75rem 1rem; border-radius: 6px;\n'
        '          margin-bottom: 1.25rem; font-size: 0.95rem; }\n'
        '  .meta span { display: inline-block; margin-right: 1rem; }\n'
        '  ul.links { list-style: none; padding: 0; margin: 0; }\n'
        '  ul.links li { padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; }\n'
        '  ul.links a { color: #2563eb; text-decoration: none; }\n'
        '  ul.links a:hover { text-decoration: underline; }\n'
        '  footer { margin-top: 2rem; color: #888; font-size: 0.85rem; }\n'
        '  code { background: #f3f4f6; padding: 0.1rem 0.4rem; border-radius: 3px;\n'
        '         font-size: 0.9em; }\n'
        '</style>\n'
        '</head>\n'
        '<body class="digest-index">\n'
        f'<h1>{escape(PROJECT_NAME)}</h1>\n'
        f'{history_block}\n'
        '<ul class="links">\n'
        f'  <li>📄 <a href="{base}/digest.html">View HTML version of the latest digest</a></li>\n'
        f'  <li>📝 <a href="{base}/digest.md">View Markdown source of the latest digest</a></li>\n'
        f'  <li>🖼️ <a href="{base}/data/digests.json" target="_blank" rel="noopener">Digest index (data/digests.json)</a></li>\n'
        f'{archive_link}'
        f'  <li>🎨 <a href="{GALLERY_DEMO_URL}" target="_blank" rel="noopener">Browse the public Artvee Gallery demo</a> (curated thumbnail subset)</li>\n'
        f'  <li>📦 <a href="{REPO_URL}" target="_blank" rel="noopener">Open-source repository</a> ({escape(release_tag)})</li>\n'
        '</ul>\n'
        '\n'
        '<footer>\n'
        '  Public-domain source: <a href="https://artvee.com/" target="_blank" rel="noopener">artvee.com</a>.\n'
        '  This bundle contains only thumbnails (no full original assets, no per-artwork\n'
        '  metadata, no local paths).\n'
        '</footer>\n'
        '</body>\n'
        '</html>\n'
    )


# ---------------------------------------------------------------------------
# Archive page (P8B)
# ---------------------------------------------------------------------------

ARCHIVE_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Archive</title>
<link rel="stylesheet" href="{base}/style.css">
<style>
  body.archive-index {{
    max-width: 1100px; margin: 2rem auto; padding: 0 1rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                 sans-serif;
    color: #1f2328;
  }}
  h1 {{ margin: 0 0 0.5rem; font-size: 1.6rem; }}
  p.lead {{ color: #555; margin: 0 0 1rem; }}
  nav.top-nav {{ background: #f3f4f6; padding: 0.6rem 0.9rem;
                border-radius: 6px; margin-bottom: 1rem;
                font-size: 0.95rem; }}
  nav.top-nav a {{ color: #2563eb; text-decoration: none;
                  margin-right: 0.9rem; }}
  nav.top-nav a:hover {{ text-decoration: underline; }}
  nav.top-nav .sep {{ color: #c0c4cc; margin-right: 0.9rem; }}
  .meta {{ background: #f3f4f6; padding: 0.6rem 0.9rem; border-radius: 6px;
          margin-bottom: 1rem; font-size: 0.9rem; }}
  .meta span {{ display: inline-block; margin-right: 1rem; }}
  .empty {{ background: #fffbeb; border: 1px solid #fde68a;
            padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 1rem; }}
  .summary {{ display: flex; flex-wrap: wrap; gap: 1rem;
             margin: 0 0 1.25rem; font-size: 0.9rem;
             color: #555; }}
  .summary .chip {{ background: #eef2ff; color: #3730a3;
                    padding: 0.2rem 0.55rem; border-radius: 999px; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: 0.5rem;
              align-items: center; margin: 0 0 1rem;
              padding: 0.6rem 0.9rem; background: #fff;
              border: 1px solid #e5e7eb; border-radius: 6px; }}
  .filters label {{ font-size: 0.85rem; color: #555; }}
  .filters input, .filters select {{
    padding: 0.3rem 0.5rem; border: 1px solid #d1d5db;
    border-radius: 4px; font-size: 0.9rem; }}
  .filters input[type="text"] {{ min-width: 200px; }}
  .filters .clear-btn {{ background: #f3f4f6; border: 1px solid #d1d5db;
                         padding: 0.3rem 0.6rem; border-radius: 4px;
                         font-size: 0.85rem; cursor: pointer; }}
  .filters .jump-latest {{ background: #2563eb; color: #fff;
                           border: 0; padding: 0.3rem 0.6rem;
                           border-radius: 4px; font-size: 0.85rem;
                           cursor: pointer; margin-left: auto; }}
  .day-card {{ background: #fff; border: 1px solid #e5e7eb;
               border-radius: 8px; padding: 1rem; margin-bottom: 1.25rem; }}
  .day-card h2 {{ margin: 0 0 0.5rem; font-size: 1.15rem;
                  display: flex; flex-wrap: wrap; gap: 0.5rem;
                  align-items: baseline; }}
  .day-card h2 code {{ background: #f3f4f6; padding: 0.15rem 0.5rem;
                       border-radius: 4px; font-size: 0.95rem; }}
  .day-card .day-meta {{ font-size: 0.85rem; color: #555; margin-bottom: 0.75rem; }}
  .day-card .day-meta .chip {{ background: #eef2ff; color: #3730a3;
                               padding: 0.1rem 0.5rem; border-radius: 999px;
                               margin-right: 0.3rem; font-size: 0.78rem; }}
  .day-card .day-meta .cat-chip {{ background: #fef3c7; color: #92400e; }}
  .day-card .day-meta .nd-chip {{ background: #fee2e2; color: #991b1b; }}
  .pick-grid {{ display: grid;
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                gap: 0.75rem; }}
  .pick {{ background: #f9fafb; border-radius: 6px; overflow: hidden; }}
  .pick img {{ display: block; width: 100%; height: 160px;
                object-fit: cover; background: #f3f4f6; }}
  .pick .pick-meta {{ padding: 0.4rem 0.55rem; font-size: 0.78rem; }}
  .pick .pick-meta .artist {{ font-weight: 600; color: #1f2328;
                              white-space: nowrap; overflow: hidden;
                              text-overflow: ellipsis; }}
  .pick .pick-meta .category {{ color: #6b7280; font-size: 0.72rem; }}
  .pick .pick-meta .nd {{ color: #991b1b; font-size: 0.7rem; }}
  .day-card.hidden {{ display: none; }}
  .pick.hidden {{ display: none; }}
  .no-results {{ text-align: center; color: #6b7280;
                  padding: 2rem; font-size: 0.95rem; }}
  .footer {{ margin-top: 1.5rem; color: #888; font-size: 0.85rem; }}
  .footer a {{ color: #2563eb; text-decoration: none; }}
  .footer a:hover {{ text-decoration: underline; }}
</style>
</head>
<body class="archive-index">
<nav class="top-nav" aria-label="Archive navigation">
  <a href="{base}/index.html">📄 Latest Digest</a>
  <a href="{gallery_url}" target="_blank" rel="noopener">🎨 Gallery Demo</a>
  <a href="{repo_url}" target="_blank" rel="noopener">📦 GitHub</a>
  <a href="{release_url}" target="_blank" rel="noopener">🏷️ {release_tag}</a>
  <span class="sep">·</span>
  <a href="{base}/archive.html">Archive</a>
  <a href="{base}/data/digests.json" target="_blank" rel="noopener">data/digests.json</a>
  <a href="{base}/data/digest-history.json" target="_blank" rel="noopener">data/digest-history.json</a>
</nav>

<h1>{title} · 30-day Archive</h1>
<p class="lead">Every day's picks, surfaced as browsable cards.
Filter by artist or category, or search by title fragment. The
history is regenerated daily from the local-first Artvee Gallery
pipeline; this page is read-only.</p>

<div class="meta">
  <span><strong>Window:</strong> {window_days} days</span>
  <span><strong>Entries available:</strong> <span class="p8b-archive-count">{entry_count}</span></span>
  <span><strong>Release:</strong> {release_tag}</span>
</div>

{availability_note}

<div class="summary" id="summary" aria-label="Archive summary">
  {summary_chips}
</div>

<div class="filters" id="filters" aria-label="Archive filters">
  <label for="filter-artist">Artist:</label>
  <select id="filter-artist" data-filter="artist">
    <option value="">All</option>
  </select>
  <label for="filter-category">Category:</label>
  <select id="filter-category" data-filter="category">
    <option value="">All</option>
  </select>
  <label for="filter-search">Search:</label>
  <input type="text" id="filter-search" data-filter="search"
         placeholder="title / artist fragment">
  <button class="clear-btn" id="filter-clear" type="button">Clear</button>
  <button class="jump-latest" id="jump-latest" type="button">↑ Jump to latest</button>
</div>

<div id="day-cards">
{cards}
</div>

<p class="no-results hidden" id="no-results">
  No archive entries match the current filters.
</p>

<p class="footer">
  📚 <a href="{base}/index.html">Back to the latest digest</a> ·
  🖼️ <a href="{base}/data/digests.json" target="_blank" rel="noopener">data/digests.json</a> ·
  📦 <a href="{repo_url}" target="_blank" rel="noopener">Open-source repository</a>
</p>

<script src="{base}/archive.js" defer></script>
</body>
</html>
"""


ARCHIVE_JS = """/* Artvee Daily Digest · Archive page filter / navigation
 *
 * Public-safe, no framework, no external dependencies.
 * Provides:
 *   - artist / category / search filters over .day-card elements
 *   - dynamic population of artist + category <select> options
 *   - "Clear" button to reset filters
 *   - "Jump to latest" button to scroll to the newest day card
 *   - hidden state when no cards match (shows #no-results notice)
 *
 * The page is fully readable with JS disabled — every card and
 * meta chip is server-rendered. JS only adds interactivity.
 */
(function () {
  "use strict";

  function uniq(values) {
    var seen = {};
    var out = [];
    for (var i = 0; i < values.length; i++) {
      var v = values[i];
      if (!v || seen[v]) continue;
      seen[v] = true;
      out.push(v);
    }
    out.sort();
    return out;
  }

  function $(id) { return document.getElementById(id); }

  function applyFilters() {
    var artist = ($("filter-artist") || {}).value || "";
    var category = ($("filter-category") || {}).value || "";
    var search = (($("filter-search") || {}).value || "").toLowerCase();

    var cards = document.querySelectorAll(".day-card");
    var visibleCount = 0;
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var cardArtist = card.getAttribute("data-artists") || "";
      var cardCategory = card.getAttribute("data-categories") || "";
      var cardSearch = card.getAttribute("data-search") || "";
      var match = true;
      if (artist && (" " + cardArtist + " ").indexOf(" " + artist + " ") === -1) {
        match = false;
      }
      if (match && category && (" " + cardCategory + " ").indexOf(" " + category + " ") === -1) {
        match = false;
      }
      if (match && search) {
        var terms = search.split(/\\s+/).filter(function (t) { return t.length > 0; });
        for (var k = 0; k < terms.length; k++) {
          if (cardSearch.indexOf(terms[k]) === -1) { match = false; break; }
        }
      }
      if (match) { card.classList.remove("hidden"); visibleCount++; }
      else       { card.classList.add("hidden"); }
    }

    var noResults = $("no-results");
    if (noResults) {
      if (visibleCount === 0) noResults.classList.remove("hidden");
      else                    noResults.classList.add("hidden");
    }
  }

  function populateSelect(selectId, values) {
    var sel = $(selectId);
    if (!sel) return;
    var first = sel.firstElementChild;
    while (sel.children.length > 1) sel.removeChild(sel.lastChild);
    for (var i = 0; i < values.length; i++) {
      var opt = document.createElement("option");
      opt.value = values[i];
      opt.textContent = values[i];
      sel.appendChild(opt);
    }
  }

  function init() {
    var cards = document.querySelectorAll(".day-card");
    var artists = [];
    var categories = [];
    for (var i = 0; i < cards.length; i++) {
      var a = (cards[i].getAttribute("data-artists") || "").split("|");
      var c = (cards[i].getAttribute("data-categories") || "").split("|");
      for (var j = 0; j < a.length; j++) if (a[j]) artists.push(a[j]);
      for (var k = 0; k < c.length; k++) if (c[k]) categories.push(c[k]);
    }
    populateSelect("filter-artist", uniq(artists));
    populateSelect("filter-category", uniq(categories));

    var ids = ["filter-artist", "filter-category", "filter-search"];
    for (var m = 0; m < ids.length; m++) {
      var el = $(ids[m]);
      if (!el) continue;
      var ev = (el.tagName === "INPUT") ? "input" : "change";
      el.addEventListener(ev, applyFilters);
    }
    var clearBtn = $("filter-clear");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        var sa = $("filter-artist"); if (sa) sa.value = "";
        var sc = $("filter-category"); if (sc) sc.value = "";
        var ss = $("filter-search"); if (ss) ss.value = "";
        applyFilters();
      });
    }
    var jump = $("jump-latest");
    if (jump) {
      jump.addEventListener("click", function () {
        var first = document.querySelector(".day-card:not(.hidden)");
        if (first) first.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    applyFilters();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
"""


def render_archive(base_url: str, history: dict, release_tag: str) -> str:
    """Render the P8C archive page from a 30-day history dict.

    P8C upgrade: instead of a text-only table (P8B), the page is
    a stack of ``.day-card`` elements — one per day — with a small
    grid of pick thumbnails under each. A top nav row provides
    quick links to the latest digest, the gallery demo, the
    GitHub repo, and the current release tag.

    The thumbnails referenced in cards are the public 256
    variants (re-used under ``assets/thumbs/256/`` from the
    digest bundle). Missing thumbnails fall back to a
    transparent SVG placeholder — the page must not 404 on a
    single missing image.

    The page is fully readable with JS disabled; the
    companion ``archive.js`` (also emitted by the export)
    adds interactivity (artist / category / search filters,
    jump-to-latest).
    """
    base = base_url.rstrip("/") if base_url else "."
    entries = history.get("entries", []) or []
    window_days = history.get("window_days", 30)
    summary = summarize_history(history)
    release_url = (
        f"{REPO_URL}/releases/tag/{release_tag}"
        if release_tag and release_tag != DEFAULT_RELEASE_TAG
        else REPO_URL
    )

    # Day cards (newest first; the rolling history is appended
    # chronologically, so reverse for display).
    cards: list[str] = []
    for e in reversed(entries):
        date = e.get("date", "")
        strategy = e.get("strategy", "diverse")
        picks = e.get("picks", []) or []
        # Build data-* for client-side filtering.
        artist_set: list[str] = []
        cat_set: list[str] = []
        search_parts: list[str] = [date, strategy]
        for p in picks:
            art = (p.get("artist") or "").strip()
            cat = (p.get("category") or "").strip()
            if art and art not in artist_set:
                artist_set.append(art)
            if cat and cat not in cat_set:
                cat_set.append(cat)
            # pick id is the public-safe slug; usable as a search fragment.
            search_parts.append(p.get("id", ""))
        data_artists = "|".join(artist_set)
        data_cats = "|".join(cat_set)
        data_search = " ".join(search_parts).lower()

        cat_chips = "".join(
            f'<span class="chip cat-chip">{escape(c)}</span>'
            for c in cat_set
        ) or '<span class="chip" style="background:#f3f4f6;color:#888">no category</span>'

        # near-dup cluster ids
        nd_ids: list[str] = []
        for p in picks:
            nd = p.get("near_dup_cluster_id")
            if nd and nd not in nd_ids:
                nd_ids.append(nd)
        nd_chip = ""
        if nd_ids:
            nd_label = ", ".join(f"cluster #{n}" for n in nd_ids)
            nd_chip = f'<span class="chip nd-chip">{escape(nd_label)}</span>'

        # Pick thumbnails
        pick_html: list[str] = []
        for p in picks:
            pid = p.get("id", "")
            art = p.get("artist", "")
            cat = p.get("category", "")
            nd = p.get("near_dup_cluster_id")
            thumb256 = f"{base}/assets/thumbs/256/{slug_to_thumb256_basename(pid)}"
            nd_text = (
                f'<div class="nd">cluster #{escape(str(nd))}</div>' if nd else ""
            )
            pick_html.append(
                f'<div class="pick">'
                f'<img src="{thumb256}" alt="{escape(art)}" loading="lazy" '
                f'onerror="this.style.visibility=\'hidden\'">'
                f'<div class="pick-meta">'
                f'<div class="artist" title="{escape(art)}">{escape(art)}</div>'
                f'<div class="category">{escape(cat)}</div>'
                f'{nd_text}'
                f'</div>'
                f'</div>'
            )
        pick_grid = (
            '<div class="pick-grid">' + "".join(pick_html) + '</div>'
            if pick_html
            else '<p style="color:#888">No picks on this day.</p>'
        )

        # Latest-day marker (newest = first after reverse)
        latest_attr = ' id="latest-day"' if e is entries[-1] else ""

        cards.append(
            f'<section class="day-card"{latest_attr} '
            f'data-artists="{escape(data_artists, quote=True)}" '
            f'data-categories="{escape(data_cats, quote=True)}" '
            f'data-search="{escape(data_search, quote=True)}">\n'
            f'  <h2><code>{escape(date)}</code>'
            f'<span style="font-size:0.85rem;color:#888">{len(picks)} pick{"s" if len(picks) != 1 else ""}</span></h2>\n'
            f'  <div class="day-meta">\n'
            f'    <span class="chip">{escape(strategy)}</span>\n'
            f'    {cat_chips}\n'
            f'    {nd_chip}\n'
            f'  </div>\n'
            f'  {pick_grid}\n'
            f'</section>'
        )

    cards_html = "\n".join(cards) if cards else (
        '<p class="empty"><strong>No archive entries yet.</strong></p>'
    )

    # Summary chips
    range_str = "—"
    rng = summary.get("available_range") or {}
    if rng.get("first_date") and rng.get("latest_date"):
        if rng["first_date"] == rng["latest_date"]:
            range_str = rng["first_date"]
        else:
            range_str = f'{rng["first_date"]} → {rng["latest_date"]}'
    top_cats = summary.get("top_categories") or []
    top_cats_html = "".join(
        f'<span class="chip">{escape(c["category"])} '
        f'· {c["count"]}</span>'
        for c in top_cats
    )
    summary_chips = (
        f'<span class="chip"><strong>Total days:</strong> '
        f'{summary["total_days"]}</span>'
        f'<span class="chip"><strong>Total picks:</strong> '
        f'{summary["total_picks"]}</span>'
        f'<span class="chip"><strong>Unique artists:</strong> '
        f'{summary["unique_artists"]}</span>'
        f'<span class="chip"><strong>Available range:</strong> '
        f'{escape(range_str)}</span>'
        f'<span class="chip"><strong>Top categories:</strong></span>'
        f'{top_cats_html}'
    )

    # Availability note (P8B "honest" behavior preserved).
    if not entries:
        availability_note = (
            '<div class="empty">\n'
            '  <strong>History entries currently available: 0.</strong>\n'
            '  The archive is generated from the daily digest builder\'s\n'
            '  30-day rolling history. Run the daily builder (or wait for\n'
            '  the next cron run) and re-export to populate this page.\n'
            '</div>'
        )
    elif len(entries) < window_days:
        availability_note = (
            f'<div class="empty">\n'
            f'  <strong>History entries currently available: {len(entries)}</strong>\n'
            f'  (out of a {window_days}-day window). The archive will\n'
            f'  fill up as more daily digests run.\n'
            f'</div>'
        )
    else:
        availability_note = ""

    return ARCHIVE_INDEX_TEMPLATE.format(
        title=escape(PROJECT_NAME),
        base=base,
        release_tag=escape(release_tag),
        release_url=escape(release_url),
        repo_url=REPO_URL,
        gallery_url=GALLERY_DEMO_URL,
        window_days=window_days,
        entry_count=len(entries),
        availability_note=availability_note,
        summary_chips=summary_chips,
        cards=cards_html,
    )


# ---------------------------------------------------------------------------
# Post-export leak check
# ---------------------------------------------------------------------------

def leak_check(files: list[Path]) -> list[tuple[Path, str]]:
    """Return a list of (file, needle) tuples where forbidden substrings
    appear in the exported text. Empty list means clean."""
    bad: list[tuple[Path, str]] = []
    for f in files:
        if not f.is_file():
            continue
        # Only scan text-ish files.
        if f.suffix.lower() not in (
            ".html", ".css", ".js", ".md", ".json", ".txt",
        ):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in text:
                bad.append((f, needle))
    return bad


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    base_url = args.base_url
    release_tag = detect_release_tag(BASE_DIR)

    # 1. Determine which digest to export
    digests_index = load_json(SRC_DATA / "digests.json")
    if args.date:
        chosen_date = args.date
    else:
        chosen_date = find_latest_date(digests_index)

    entry = next(
        (e for e in digests_index if e.get("date") == chosen_date),
        None,
    )
    if entry is None:
        print(
            f"ERROR: no digest entry for date={chosen_date!r} in "
            f"{SRC_DATA / 'digests.json'}",
            file=sys.stderr,
        )
        return 2

    md_src = DIGESTS_DIR / f"artvee-digest-{chosen_date}.md"
    html_src = DIGESTS_DIR / f"artvee-digest-{chosen_date}.html"
    if not md_src.exists():
        print(f"ERROR: source markdown missing: {md_src}", file=sys.stderr)
        return 2
    if not html_src.exists():
        print(f"ERROR: source HTML missing: {html_src}", file=sys.stderr)
        return 2

    # 1b. P8B: load 30-day digest history. Used by both the archive
    # page and the index page's archive link. Falls back to None
    # if the file is missing (the public bundle still works; the
    # archive link is simply not shown).
    history = load_digest_history(BASE_DIR)
    history_entries_count = len(history.get("entries", [])) if history else 0

    # 2. Find which 512 thumbs are referenced
    md_text = md_src.read_text(encoding="utf-8")
    html_text = html_src.read_text(encoding="utf-8")

    referenced: set[str] = set()
    for src in (md_text, html_text):
        for m in RE_THUMB_REL.finditer(src):
            referenced.add(m.group("basename"))

    if not referenced:
        print(
            f"ERROR: digest {chosen_date} references no 512 thumbs",
            file=sys.stderr,
        )
        return 2

    # 3. Verify all referenced thumbs exist
    missing: list[str] = []
    for stem in referenced:
        if not (SRC_THUMBS_512 / stem).exists():
            missing.append(stem)
    if missing:
        print(
            f"ERROR: {len(missing)} referenced 512 thumb(s) missing. "
            f"First 5: {missing[:5]}",
            file=sys.stderr,
        )
        return 2

    # 4. Plan
    print(f"[plan] date         = {chosen_date}")
    print(f"[plan] out_dir      = {out_dir}")
    print(f"[plan] base_url     = {base_url}")
    print(f"[plan] release_tag  = {release_tag}")
    print(f"[plan] thumbs ref   = {len(referenced)} unique file(s) under 512/")
    print(f"[plan] history      = {history_entries_count} entries (P8B archive)")

    if args.dry_run:
        print("[dry-run] no files written.")
        return 0

    # 5. Materialize
    if out_dir.exists():
        # Clean only the assets/data dirs; keep the dir itself (may have
        # unrelated user files). For repeatability, also clear the existing
        # contents of the subdirs we own.
        for sub in ("assets", "data"):
            p = out_dir / sub
            if p.exists():
                shutil.rmtree(p)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data").mkdir(parents=True, exist_ok=True)
    (out_dir / "assets" / "thumbs" / "512").mkdir(parents=True, exist_ok=True)
    (out_dir / "assets" / "thumbs" / "256").mkdir(parents=True, exist_ok=True)

    # 5a. Copy referenced 512 thumbs
    for stem in referenced:
        shutil.copy2(SRC_THUMBS_512 / stem, out_dir / "assets" / "thumbs" / "512" / stem)

    # 5b. Copy style.css
    style_src = SRC_WEB / "style.css"
    if not style_src.exists():
        print(f"ERROR: missing style.css source: {style_src}", file=sys.stderr)
        return 2
    shutil.copy2(style_src, out_dir / "style.css")

    # 5c. Rewrite and write digest.md
    md_out = rewrite_thumb_refs(md_text, base_url)
    md_out = rewrite_style_link_md(md_out, base_url)
    (out_dir / "digest.md").write_text(md_out, encoding="utf-8")

    # 5d. Rewrite and write digest.html
    html_out = rewrite_thumb_refs(html_text, base_url)
    html_out = rewrite_style_link_html(html_out, base_url)
    (out_dir / "digest.html").write_text(html_out, encoding="utf-8")

    # 5e. Write data/digests.json (only the chosen entry)
    single_entry = [e for e in digests_index if e.get("date") == chosen_date]
    (out_dir / "data" / "digests.json").write_text(
        json.dumps(single_entry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 5a2. P8C: copy archive-referenced 256 thumbnails.
    # Each pick referenced in the history needs its 256 thumb under
    # `assets/thumbs/256/`. Missing 256 thumbs are NOT fatal — the
    # card image just falls back to visibility:hidden onerror — but
    # we log the gap so operators can see which picks are
    # archive-invisible.
    archive_referenced: set[str] = set()
    if history is not None:
        for e in (history.get("entries") or []):
            for p in (e.get("picks") or []):
                pid = p.get("id", "")
                stem = slug_to_thumb256_basename(pid)
                if stem:
                    archive_referenced.add(stem)
    archive_missing: list[str] = []
    for stem in archive_referenced:
        src = SRC_THUMBS_256 / stem
        if src.exists():
            shutil.copy2(src, out_dir / "assets" / "thumbs" / "256" / stem)
        else:
            archive_missing.append(stem)

    # 5f. P8B + P8C: write data/digest-history.json (redacted 30-day
    # history exposed publicly). Strip the `digest_path` field from
    # each entry because it leaks local-absolute paths even after
    # the digest builder's redaction. P8C adds a top-level
    # `generated_at`, `available_range`, and `summary` block so
    # downstream consumers don't have to recompute them.
    if history is not None:
        clean_entries = [
            {k: v for k, v in e.items() if k != "digest_path"}
            for e in history.get("entries", [])
        ]
        summary = summarize_history(history)
        clean_history = {
            "version": history.get("version", 1),
            "updated_at": history.get("updated_at", ""),
            "generated_at": history.get("updated_at", ""),
            "window_days": history.get("window_days", 30),
            "history_entries": len(clean_entries),
            "available_range": summary.get("available_range"),
            "summary": {
                "total_days": summary["total_days"],
                "total_picks": summary["total_picks"],
                "unique_artists": summary["unique_artists"],
                "top_categories": summary["top_categories"],
            },
            "entries": clean_entries,
        }
        (out_dir / "data" / "digest-history.json").write_text(
            json.dumps(clean_history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 5g. Render and write index.html
    index_html = render_index(
        base_url, chosen_date, entry,
        history=history, release_tag=release_tag,
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    # 5h. P8C: write archive.html (digest cards + filters) and
    # archive.js (vanilla client-side filter / navigation logic).
    if history is not None:
        archive_html = render_archive(base_url, history, release_tag)
        (out_dir / "archive.html").write_text(archive_html, encoding="utf-8")
        (out_dir / "archive.js").write_text(ARCHIVE_JS, encoding="utf-8")

    # 6. Post-export leak check on every text file we wrote
    text_files = [
        out_dir / "index.html",
        out_dir / "digest.html",
        out_dir / "digest.md",
        out_dir / "style.css",
        out_dir / "data" / "digests.json",
    ]
    if history is not None:
        text_files += [
            out_dir / "archive.html",
            out_dir / "archive.js",
            out_dir / "data" / "digest-history.json",
        ]
    bad = leak_check(text_files)
    if bad:
        print("ERROR: post-export leak check FAILED", file=sys.stderr)
        for f, needle in bad:
            print(f"  - {f} contains {needle!r}", file=sys.stderr)
        return 4

    # 7. Summary
    written_files = sorted(
        p.relative_to(out_dir) for p in out_dir.rglob("*") if p.is_file()
    )
    print(f"[ok] wrote: {out_dir}/")
    for p in written_files:
        print(f"    {p}")
    print(f"[ok] {len(referenced)} 512-thumbnail(s) copied")
    print(f"[ok] digest date = {chosen_date}")
    print(f"[ok] base-url = {base_url!r}")
    print(f"[ok] no leaks detected")
    if history is not None:
        print(f"[ok] archive entries = {history_entries_count} (window = {history.get('window_days', 30)}d)")
        print(f"[ok] archive 256-thumbs copied = {len(archive_referenced) - len(archive_missing)} / {len(archive_referenced)}")
        if archive_missing:
            print(f"[warn] archive 256-thumbs missing: {len(archive_missing)} (cards will hide image)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
