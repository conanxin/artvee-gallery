#!/usr/bin/env python3
"""
Artvee Candidate Adder
将候选 URL 去重后追加到 manifest.csv，并同步更新 seen_candidates.csv。
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST = BASE_DIR / "inbox" / "manifest.csv"
INDEX_CSV = BASE_DIR / "index" / "artworks.csv"
SEEN_CSV = BASE_DIR / "index" / "seen_candidates.csv"


def normalize_url(url):
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") + "/" if parsed.path else "/"
    return f"{parsed.scheme}://{netloc}{path}"


def extract_slug(url):
    m = re.search(r'/dl/([^/]+)/', url)
    return m.group(1) if m else ""


def load_seen():
    seen = {}
    if not SEEN_CSV.exists():
        return seen
    with open(SEEN_CSV, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            norm = row.get("normalized_url", "").strip()
            if norm:
                seen[norm] = row
    return seen


def save_seen(seen):
    fieldnames = ["source_url", "normalized_url", "slug", "first_seen_at", "last_seen_at", "status"]
    with open(SEEN_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in seen.values():
            writer.writerow(row)


def load_manifest_urls():
    urls = set()
    if not MANIFEST.exists():
        return urls
    with open(MANIFEST, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            url = row.get("url", "").strip()
            if url:
                urls.add(normalize_url(url))
    return urls


def load_manifest_records():
    records = []
    if not MANIFEST.exists():
        return records
    with open(MANIFEST, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            records.append(row)
    return records


def save_manifest(records):
    fieldnames = ["url", "category", "download_variant", "tags", "usage_note", "status", "last_error"]
    with open(MANIFEST, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def load_index_urls():
    urls = set()
    if not INDEX_CSV.exists():
        return urls
    with open(INDEX_CSV, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            url = row.get("source_url", "").strip()
            if url:
                urls.add(normalize_url(url))
    return urls


def read_input_file(path):
    """读取候选文件：支持 CSV（有 url 列）或纯 URL 列表。"""
    candidates = []
    p = Path(path)
    if not p.exists():
        return candidates
    text = p.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    if not lines:
        return candidates
    # 尝试 CSV
    if "," in lines[0] and "url" in lines[0].lower():
        reader = csv.DictReader(lines)
        for row in reader:
            url = row.get("url", "").strip()
            cat = row.get("category", "").strip()
            tags = row.get("tags", "").strip()
            usage = row.get("usage_note", "").strip()
            if url:
                candidates.append({"url": url, "category": cat, "tags": tags, "usage_note": usage})
    else:
        # 纯 URL 列表
        for line in lines:
            url = line.strip()
            if url and not url.startswith("#"):
                candidates.append({"url": url, "category": "", "tags": "", "usage_note": ""})
    return candidates


def read_seed_sources():
    """读取 inbox/candidate_sources.csv 中 enabled=true 的种子源。"""
    sources = []
    src_path = BASE_DIR / "inbox" / "candidate_sources.csv"
    if not src_path.exists():
        return sources
    with open(src_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("enabled", "").strip().lower() == "true":
                sources.append({
                    "category": row.get("category", "").strip(),
                    "seed_url": row.get("seed_url", "").strip(),
                    "tags": row.get("tags", "").strip(),
                    "usage_note": row.get("usage_note", "").strip(),
                })
    return sources


def main():
    parser = argparse.ArgumentParser(description="Add new Artvee candidates to manifest")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be added")
    parser.add_argument("--input-file", type=str, help="Path to candidate file (CSV or plain URLs)")
    parser.add_argument("--limit", type=int, default=1000, help="Max candidates to add")
    args = parser.parse_args()

    now = datetime.now().isoformat()
    seen = load_seen()
    manifest_urls = load_manifest_urls()
    index_urls = load_index_urls()

    # 收集候选
    if args.input_file:
        raw_candidates = read_input_file(args.input_file)[:args.limit]
    else:
        # 没有 input-file 时，可以从 seed sources 读取（但本阶段不真正抓取页面，所以只输出提示）
        seeds = read_seed_sources()
        print(f"No --input-file provided. Found {len(seeds)} enabled seed sources.")
        print("Note: real auto-scraping from seeds is not implemented yet.")
        print("Use --input-file <path> to add candidates from a prepared list.")
        return

    new_records = []
    added_count = 0

    for cand in raw_candidates:
        url = cand["url"]
        norm = normalize_url(url)

        if norm in seen or norm in manifest_urls or norm in index_urls:
            print(f"SKIP (already seen): {url}")
            continue

        if added_count >= args.limit:
            print(f"LIMIT reached ({args.limit})")
            break

        slug = extract_slug(url)
        seen[norm] = {
            "source_url": url,
            "normalized_url": norm,
            "slug": slug,
            "first_seen_at": now,
            "last_seen_at": now,
            "status": "pending",
        }

        new_records.append({
            "url": url,
            "category": cand.get("category", ""),
            "download_variant": "standard",
            "tags": cand.get("tags", ""),
            "usage_note": cand.get("usage_note", ""),
            "status": "pending",
            "last_error": "",
        })
        added_count += 1
        print(f"NEW: {url}")

    print(f"\nCandidates evaluated: {len(raw_candidates)}")
    print(f"Candidates to add: {len(new_records)}")

    if not args.dry_run and new_records:
        manifest_records = load_manifest_records()
        manifest_records.extend(new_records)
        save_manifest(manifest_records)
        save_seen(seen)
        print("manifest.csv and seen_candidates.csv updated.")
    elif args.dry_run:
        print("DRY-RUN: no files modified.")
    else:
        print("No new candidates to add.")


if __name__ == "__main__":
    main()
