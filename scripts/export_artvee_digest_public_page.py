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
SRC_WEB = BASE_DIR / "web"
DEFAULT_OUT = BASE_DIR / "dist" / "artvee-gallery-digest-public"

# Public page metadata (fixed per release; safe to publish).
PROJECT_NAME = "Artvee Daily Digest"
GALLERY_DEMO_URL = "https://conanxin.github.io/projects/artvee-gallery-demo/"
REPO_URL = "https://github.com/conanxin/artvee-gallery"
RELEASE_TAG = "v0.1.0-alpha"

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


def find_latest_date(entries: list[dict]) -> str:
    """Return the date string of the latest entry."""
    if not entries:
        print("ERROR: digests.json is empty", file=sys.stderr)
        sys.exit(2)
    return max(e.get("date", "") for e in entries)


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
) -> str:
    base = base_url.rstrip("/") if base_url else "."
    cats = ", ".join(entry.get("categories", [])) or "—"
    artists = ", ".join(entry.get("artists", [])) or "—"
    return INDEX_TEMPLATE.format(
        title=escape(PROJECT_NAME),
        base=base,
        date=escape(date),
        count=entry.get("selected_count", 0),
        cats=escape(cats),
        artists=escape(artists),
        strategy=escape(entry.get("strategy", "")),
        gallery_url=GALLERY_DEMO_URL,
        repo_url=REPO_URL,
        release_tag=RELEASE_TAG,
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
    print(f"[plan] date       = {chosen_date}")
    print(f"[plan] out_dir    = {out_dir}")
    print(f"[plan] base_url   = {base_url}")
    print(f"[plan] thumbs ref = {len(referenced)} unique file(s) under 512/")

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

    # 5f. Render and write index.html
    index_html = render_index(base_url, chosen_date, entry)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    # 6. Post-export leak check on every text file we wrote
    text_files = [
        out_dir / "index.html",
        out_dir / "digest.html",
        out_dir / "digest.md",
        out_dir / "style.css",
        out_dir / "data" / "digests.json",
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
