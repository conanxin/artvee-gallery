#!/usr/bin/env python3
"""
P6C: Near-duplicate cluster review workflow.

Requirements:
- Do NOT download from Artvee.
- Do NOT run refill, nightly batch, or retry retired URLs.
- Do NOT push to GitHub Pages.
- Do NOT delete, move, or modify images / manifest / index / web data.
- Do NOT commit runtime outputs to git.
- MAY create review scripts, docs, and samples.
- MAY generate runtime near-dup JSON / Markdown / contact sheet.

Usage:
    python3 scripts/review_near_duplicate_clusters.py
    python3 scripts/review_near_duplicate_clusters.py --threshold 6
    python3 scripts/review_near_duplicate_clusters.py --out-json reports/runtime/p6c-near-dup-clusters.json
    python3 scripts/review_near_duplicate_clusters.py --out-md reports/runtime/p6c-near-dup-clusters.md
    python3 scripts/review_near_duplicate_clusters.py --contact-sheet reports/runtime/p6c-near-dup-contact-sheet.html
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
ARTWORKS_JSON = REPO_ROOT / "web" / "data" / "artworks.json"
P5D_VQA_JSON = REPO_ROOT / "reports" / "runtime" / "p5d-visual-qa-full.json"
THUMB_512_DIR = REPO_ROOT / "thumbs" / "512"

DEFAULT_THRESHOLD = 6


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: failed to load {path}: {e}", file=sys.stderr)
        return None


def _hamming_distance(hex_a: str, hex_b: str) -> int:
    """Hamming distance between two hex strings (aHash)."""
    try:
        int_a = int(hex_a, 16)
        int_b = int(hex_b, 16)
    except ValueError:
        return 9999
    x = int_a ^ int_b
    return bin(x).count("1")


def _compute_ahash(image_path: Path) -> str | None:
    """Compute average hash using Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return None
    if not image_path.exists():
        return None
    try:
        with Image.open(image_path) as img:
            img = img.convert("L")
            img = img.resize((8, 8), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = "".join("1" if p >= avg else "0" for p in pixels)
            return hex(int(bits, 2))[2:].rjust(16, "0")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_artworks() -> list[dict[str, Any]]:
    data = _load_json(ARTWORKS_JSON)
    if data is None:
        print(f"Error: cannot read {ARTWORKS_JSON}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, list):
        print("Error: artworks.json is not a list", file=sys.stderr)
        sys.exit(1)
    return data


def load_ahashes_from_p5d(artworks: list[dict[str, Any]]) -> dict[str, str]:
    """Return mapping id -> ahash from P5D visual QA JSON if available."""
    data = _load_json(P5D_VQA_JSON)
    if data is None:
        return {}
    records = data.get("records", [])
    ahashes = {}
    for rec in records:
        rec_id = rec.get("id")
        ahash = rec.get("ahash")
        if rec_id and ahash:
            ahashes[rec_id] = ahash
    return ahashes


def compute_missing_ahashes(
    artworks: list[dict[str, Any]], ahashes: dict[str, str]
) -> dict[str, str]:
    """Compute aHash for any artwork missing it."""
    missing_count = 0
    computed_count = 0
    for aw in artworks:
        rec_id = aw["id"]
        if rec_id in ahashes:
            continue
        missing_count += 1
        thumb_name = Path(aw.get("thumb_512", "")).name
        if not thumb_name:
            continue
        thumb_path = THUMB_512_DIR / thumb_name
        ahash = _compute_ahash(thumb_path)
        if ahash:
            ahashes[rec_id] = ahash
            computed_count += 1
    if missing_count:
        print(f"  aHash: {missing_count} missing, {computed_count} computed from thumbs/512")
    return ahashes


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------
def build_clusters(
    artworks: list[dict[str, Any]],
    ahashes: dict[str, str],
    threshold: int,
) -> list[dict[str, Any]]:
    """Build near-duplicate clusters using greedy agglomerative grouping."""
    ids_with_hash = [aw["id"] for aw in artworks if aw["id"] in ahashes]
    id_to_aw = {aw["id"]: aw for aw in artworks}

    # Build adjacency: which ids are within threshold?
    adjacency: dict[str, set[str]] = {i: set() for i in ids_with_hash}
    for i in range(len(ids_with_hash)):
        for j in range(i + 1, len(ids_with_hash)):
            id_a = ids_with_hash[i]
            id_b = ids_with_hash[j]
            dist = _hamming_distance(ahashes[id_a], ahashes[id_b])
            if dist <= threshold:
                adjacency[id_a].add(id_b)
                adjacency[id_b].add(id_a)

    # Connected components (clusters)
    visited = set()
    clusters = []
    for start in ids_with_hash:
        if start in visited:
            continue
        # BFS/DFS to find connected component
        stack = [start]
        comp = set()
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            comp.add(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    stack.append(neighbor)
        if len(comp) > 1:
            clusters.append(sorted(comp))

    return clusters


# ---------------------------------------------------------------------------
# Cluster analysis & classification
# ---------------------------------------------------------------------------
def classify_cluster(aw_map: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    """Analyze a cluster and return classification + recommended policy."""
    records = []
    for rec_id in ids:
        aw = aw_map.get(rec_id, {})
        records.append({
            "id": rec_id,
            "title": aw.get("title", ""),
            "artist": aw.get("artist", ""),
            "category": aw.get("category", ""),
            "source_url": aw.get("source_url", ""),
            "thumb_512": aw.get("thumb_512", ""),
        })

    # Count artists and categories
    artists = Counter(r["artist"] for r in records if r["artist"])
    categories = Counter(r["category"] for r in records if r["category"])
    source_urls = Counter(r["source_url"] for r in records if r["source_url"])

    size = len(ids)
    unique_artists = len(artists)
    unique_source_urls = len(source_urls)
    max_artist_count = max(artists.values()) if artists else 0

    # Check collision legacy: all different source_urls AND different ids AND same title (loosely normalized)
    collision_legacy = False
    if unique_source_urls == size and size > 1:
        titles = [r.get("title", "") for r in records]
        import re
        def norm_title(t):
            t = t.lower()
            t = re.sub(r'\s*\([^)]*\)', '', t)  # remove parentheticals
            t = re.sub(r'[_\.,\-]', ' ', t)   # replace punct with spaces
            t = re.sub(r'\s+', ' ', t).strip()
            return t[:35]
        norm_titles = [norm_title(t) for t in titles if t]
        if len(set(norm_titles)) == 1:
            collision_legacy = True
        # Also: if all ids end with 8-char hex suffix (P4B collision pattern)
        hex_suffix = all(re.search(r'_[a-f0-9]{8}$', r.get("id", "")) for r in records)
        if hex_suffix and len(set(norm_titles)) == 1:
            collision_legacy = True

    # Determine type_guess
    if collision_legacy:
        type_guess = "collision_legacy"
    elif unique_artists == 1 and max_artist_count == size:
        type_guess = "artist_cluster"
    elif unique_source_urls == 1 and size > 1:
        type_guess = "possible_duplicate"
    elif unique_artists == 1 and size > 1:
        type_guess = "true_series"
    else:
        type_guess = "mixed"

    # Determine recommended policy (conservative, no deletion)
    if type_guess == "collision_legacy":
        recommended_policy = "keep_all"
    elif unique_source_urls == 1 and size > 1:
        recommended_policy = "review"
    elif type_guess == "artist_cluster":
        recommended_policy = "keep_all"
    elif type_guess == "true_series":
        recommended_policy = "keep_all"
    else:
        recommended_policy = "keep_all"

    # Per-record suggested_action
    for r in records:
        if type_guess == "collision_legacy":
            r["suggested_action"] = "keep"
        elif recommended_policy == "review":
            r["suggested_action"] = "review"
        else:
            r["suggested_action"] = "keep"

    # Digest policy annotation
    if type_guess == "artist_cluster":
        recommended_policy = "keep_all"
        for r in records:
            r["digest_policy"] = "limit_one_per_digest"
    elif type_guess == "collision_legacy":
        for r in records:
            r["digest_policy"] = "limit_one_per_digest"
    elif type_guess == "true_series":
        for r in records:
            r["digest_policy"] = "limit_one_per_digest"
    else:
        for r in records:
            r["digest_policy"] = "review_before_digest"

    # Add aHash and distance_to_anchor
    # Anchor = first record in cluster
    anchor_id = ids[0]
    anchor_hash = None
    for aw in aw_map.values():
        if aw.get("id") == anchor_id:
            # We need ahash map, but this function doesn't have it. We'll patch later.
            pass

    return {
        "cluster_id": f"cluster-{len(ids):03d}-{ids[0][:20]}",
        "size": size,
        "type_guess": type_guess,
        "artist_counts": dict(artists),
        "category_counts": dict(categories),
        "records": records,
        "recommended_policy": recommended_policy,
        "collision_legacy": collision_legacy,
    }


def enrich_cluster_with_hashes(
    cluster: dict[str, Any], ahashes: dict[str, str]
) -> dict[str, Any]:
    """Add aHash and distance_to_anchor to each record."""
    records = cluster["records"]
    if not records:
        return cluster
    anchor_id = records[0]["id"]
    anchor_hash = ahashes.get(anchor_id)
    for r in records:
        rec_id = r["id"]
        r["hash"] = ahashes.get(rec_id, "")
        if anchor_hash and r["hash"]:
            r["distance_to_anchor"] = _hamming_distance(anchor_hash, r["hash"])
        else:
            r["distance_to_anchor"] = None
    return cluster


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------
def build_json_output(clusters: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "phase": "P6C",
        "workflow": "near_duplicate_cluster_review",
        "policy_version": "1.0",
        "policy_note": "Conservative: no automatic deletion, exclusion, or movement.",
        "total_clusters": len(clusters),
        "clusters": clusters,
    }


def build_md_output(clusters: list[dict[str, Any]]) -> str:
    lines = []
    lines.append("# P6C Near-Duplicate Cluster Review\n")
    lines.append(f"**Phase:** P6C  ")
    lines.append(f"**Total clusters:** {len(clusters)}  ")
    lines.append(f"**Policy:** Conservative (no automatic deletion, exclusion, or movement)\n")
    lines.append("---\n")

    for i, c in enumerate(clusters, 1):
        lines.append(f"## Cluster {i}: `{c['cluster_id']}`\n")
        lines.append(f"- **Size:** {c['size']}")
        lines.append(f"- **Type guess:** {c['type_guess']}")
        lines.append(f"- **Collision legacy:** {c['collision_legacy']}")
        lines.append(f"- **Recommended policy:** {c['recommended_policy']}\n")

        if c["artist_counts"]:
            lines.append("**Artists:**")
            for artist, count in c["artist_counts"].items():
                lines.append(f"  - {artist}: {count}")
            lines.append("")

        if c["category_counts"]:
            lines.append("**Categories:**")
            for cat, count in c["category_counts"].items():
                lines.append(f"  - {cat}: {count}")
            lines.append("")

        lines.append("| # | ID | Title | Artist | Distance | Action |")
        lines.append("|---|---|---|---|---|---|")
        for idx, r in enumerate(c["records"], 1):
            title = (r.get("title") or "")[:40]
            artist = (r.get("artist") or "")[:30]
            dist = r.get("distance_to_anchor")
            dist_str = str(dist) if dist is not None else "N/A"
            action = r.get("suggested_action", "")
            lines.append(f"| {idx} | `{r['id'][:30]}...` | {title} | {artist} | {dist_str} | {action} |")
        lines.append("")
        lines.append("---\n")

    lines.append("## Review Rules Applied\n")
    lines.append("- **Rule A:** Same artist + similar visual = `keep_all`, `limit_one_per_digest`\n")
    lines.append("- **Rule B:** Different source_url + different stable_id = `keep_all`\n")
    lines.append("- **Rule C:** Same source_url or same image_path = `review` (strict integrity should prevent this)\n")
    lines.append("- **Rule D:** P4B collision legacy with all unique IDs/URLs/paths = `keep_all`, do not treat as data error\n")
    lines.append("\n*Generated by scripts/review_near_duplicate_clusters.py (P6C)*\n")
    return "\n".join(lines)


def build_contact_sheet(clusters: list[dict[str, Any]]) -> str:
    """Generate a static HTML contact sheet without copying images or embedding base64."""
    # Relative path from reports/runtime/ to thumbs/512/
    THUMB_REL = "../../thumbs/512/"

    rows = []
    for i, c in enumerate(clusters, 1):
        rows.append(f'<div class="cluster">')
        rows.append(f'<h2>Cluster {i}: {c["cluster_id"]} <span class="type">{c["type_guess"]}</span></h2>')
        rows.append(f'<p class="meta">Size: {c["size"]} | Policy: <strong>{c["recommended_policy"]}</strong> | Collision legacy: {c["collision_legacy"]}</p>')
        rows.append('<div class="grid">')
        for r in c["records"]:
            thumb_name = Path(r.get("thumb_512", "")).name
            thumb_src = THUMB_REL + thumb_name if thumb_name else ""
            title = r.get("title", "")
            artist = r.get("artist", "")
            category = r.get("category", "")
            source_url = r.get("source_url", "")
            rec_id = r.get("id", "")
            dist = r.get("distance_to_anchor")
            dist_str = f"dist={dist}" if dist is not None else ""
            action = r.get("suggested_action", "")
            rows.append(f"""
            <div class="card">
                <img src="{thumb_src}" alt="{title}" loading="lazy">
                <div class="info">
                    <div class="title" title="{title}">{title[:50]}{'...' if len(title) > 50 else ''}</div>
                    <div class="artist">{artist}</div>
                    <div class="category">{category}</div>
                    <div class="id">ID: {rec_id[:30]}...</div>
                    <div class="distance">{dist_str}</div>
                    <div class="action">Action: {action}</div>
                    <div class="source"><a href="{source_url}" target="_blank">Source</a></div>
                </div>
            </div>
            """)
        rows.append("</div></div>")

    body = "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>P6C Near-Duplicate Contact Sheet</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 24px; background: #f5f5f5; }}
h1 {{ margin-bottom: 8px; }}
.subtitle {{ color: #666; margin-bottom: 24px; }}
.cluster {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.cluster h2 {{ margin-top: 0; font-size: 1.1rem; }}
.cluster .type {{ font-weight: normal; color: #888; font-size: 0.9rem; }}
.cluster .meta {{ color: #555; font-size: 0.9rem; margin-bottom: 12px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; background: #fafafa; }}
.card img {{ width: 100%; height: 180px; object-fit: cover; display: block; }}
.card .info {{ padding: 10px; font-size: 0.82rem; }}
.card .title {{ font-weight: 600; margin-bottom: 4px; }}
.card .artist {{ color: #444; }}
.card .category {{ color: #888; font-size: 0.75rem; margin-bottom: 4px; }}
.card .id {{ color: #999; font-size: 0.75rem; word-break: break-all; }}
.card .distance {{ color: #c60; font-size: 0.75rem; font-weight: 600; }}
.card .action {{ color: #060; font-size: 0.75rem; font-weight: 600; }}
.card .source {{ margin-top: 6px; }}
.card .source a {{ color: #0066cc; font-size: 0.75rem; }}
.footer {{ color: #999; font-size: 0.8rem; margin-top: 32px; }}
</style>
</head>
<body>
<h1>P6C Near-Duplicate Contact Sheet</h1>
<div class="subtitle">Conservative review: no automatic deletion, exclusion, or movement. Serve from repo root (paths are relative).</div>
{body}
<div class="footer">Generated by scripts/review_near_duplicate_clusters.py (P6C) | Do not commit to git.</div>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="P6C Near-duplicate cluster review")
    parser.add_argument("--threshold", type=int, default=0, help="Hamming distance threshold (default: 0 = exact aHash match)")
    parser.add_argument("--out-json", type=str, default="reports/runtime/p6c-near-dup-clusters.json", help="JSON output path")
    parser.add_argument("--out-md", type=str, default="reports/runtime/p6c-near-dup-clusters.md", help="Markdown output path")
    parser.add_argument("--contact-sheet", type=str, default="reports/runtime/p6c-near-dup-contact-sheet.html", help="HTML contact sheet path")
    args = parser.parse_args()

    print("P6C: Near-Duplicate Cluster Review")
    print("=" * 40)
    print(f"  Threshold: {args.threshold} (0 = exact aHash match)")

    # 1. Load artworks
    artworks = load_artworks()
    print(f"  Artworks: {len(artworks)}")

    # 2. Load aHashes
    ahashes = load_ahashes_from_p5d(artworks)
    print(f"  aHashes from P5D: {len(ahashes)}")

    if not ahashes:
        print("  P5D visual QA not available. Computing aHashes from thumbs/512...")
        ahashes = compute_missing_ahashes(artworks, ahashes)
    else:
        # Fill any missing ones (e.g., new records since P5D)
        ahashes = compute_missing_ahashes(artworks, ahashes)

    if len(ahashes) < len(artworks) * 0.5:
        print(f"  ERROR: Only {len(ahashes)}/{len(artworks)} aHashes available. Skipping.")
        sys.exit(0)

    # 3. Build clusters
    clusters = build_clusters(artworks, ahashes, args.threshold)
    print(f"  Near-duplicate clusters (threshold={args.threshold}): {len(clusters)}")

    # 4. Classify clusters
    aw_map = {aw["id"]: aw for aw in artworks}
    enriched = []
    for ids in clusters:
        c = classify_cluster(aw_map, ids)
        c = enrich_cluster_with_hashes(c, ahashes)
        enriched.append(c)

    # Sort by size descending
    enriched.sort(key=lambda x: (-x["size"], x["cluster_id"]))
    # Renumber cluster_ids
    for i, c in enumerate(enriched, 1):
        c["cluster_id"] = f"cluster-{i:03d}"

    # 5. Write JSON
    json_path = REPO_ROOT / args.out_json
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_out = build_json_output(enriched)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_out, f, indent=2, ensure_ascii=False)
    print(f"  Wrote JSON: {json_path}")

    # 6. Write Markdown
    md_path = REPO_ROOT / args.out_md
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_out = build_md_output(enriched)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_out)
    print(f"  Wrote MD:   {md_path}")

    # 7. Write Contact Sheet
    html_path = REPO_ROOT / args.contact_sheet
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_out = build_contact_sheet(enriched)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"  Wrote HTML: {html_path}")

    print("=" * 40)
    print("Done. No source data modified. Review outputs are runtime-only.")


if __name__ == "__main__":
    main()
