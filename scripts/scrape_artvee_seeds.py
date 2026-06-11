#!/usr/bin/env python3
"""
Artvee Seed Scraper
从 candidate_sources.csv 中读取 enabled 种子源，抓取作品详情页 URL。
"""

import argparse
import csv
import re
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATE_SOURCES = BASE_DIR / "inbox" / "candidate_sources.csv"
SEEN_CSV = BASE_DIR / "index" / "seen_candidates.csv"
MANIFEST_CSV = BASE_DIR / "inbox" / "manifest.csv"
INDEX_CSV = BASE_DIR / "index" / "artworks.csv"
LOGS_DIR = BASE_DIR / "logs"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def normalize_url(url):
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") + "/" if parsed.path else "/"
    return f"{parsed.scheme}://{netloc}{path}"


def load_enabled_seeds():
    seeds = []
    with open(CANDIDATE_SOURCES, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("enabled", "").strip().lower() == "true":
                seeds.append(row)
    return seeds


def load_normalized_urls_from_csv(path, column_name):
    urls = set()
    if not path.exists():
        return urls
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return urls
        for row in reader:
            val = row.get(column_name, "").strip()
            if val:
                urls.add(normalize_url(val))
    return urls


def build_paged_url(seed_url, page):
    """Artvee 搜索分页格式: /page/N/?s=xxx"""
    parsed = urlparse(seed_url)
    query_params = parse_qs(parsed.query)
    # 去掉可能的 paged 参数
    query_params.pop("paged", None)
    new_query = urlencode(query_params, doseq=True)
    if page == 1:
        path = parsed.path
    else:
        path = f"/page/{page}{parsed.path}"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", new_query, ""))


def fetch_dl_urls(seed_url, pages):
    all_urls = []
    errors = []
    for page in range(1, pages + 1):
        url = build_paged_url(seed_url, page)
        try:
            r = requests.get(url, headers=headers, timeout=20)
            # 第 2 页及以后返回 404 视为正常翻页结束
            if page >= 2 and r.status_code == 404:
                break
            r.raise_for_status()
            found = re.findall(r'https://artvee\.com/dl/[^/"<>\s]+/', r.text)
            page_urls = []
            for u in found:
                if u == "https://artvee.com/dl/":
                    continue
                norm = normalize_url(u)
                # 确保是 /dl/<slug>/ 格式，且不是搜索页、分类页等
                if re.match(r'https://artvee\.com/dl/[^/]+/$', norm):
                    page_urls.append(norm)
            all_urls.extend(page_urls)
        except Exception as e:
            errors.append((url, str(e)))
    return all_urls, errors


def main():
    parser = argparse.ArgumentParser(description="Scrape Artvee seeds for candidate URLs")
    parser.add_argument("--dry-run", action="store_true", help="Only show stats, do not modify manifest/seen")
    parser.add_argument("--pages-per-seed", type=int, default=2, help="Pages to scrape per seed")
    parser.add_argument("--limit", type=int, default=120, help="Max new candidates to output")
    args = parser.parse_args()

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = LOGS_DIR / f"generated_candidates_{now}.csv"

    seeds = load_enabled_seeds()
    print(f"Enabled seeds: {len(seeds)}")

    # 加载现有 URL 用于去重
    seen_urls = load_normalized_urls_from_csv(SEEN_CSV, "normalized_url")
    manifest_urls = load_normalized_urls_from_csv(MANIFEST_CSV, "url")
    index_urls = load_normalized_urls_from_csv(INDEX_CSV, "source_url")

    print(f"Existing in seen_candidates: {len(seen_urls)}")
    print(f"Existing in manifest: {len(manifest_urls)}")
    print(f"Existing in index: {len(index_urls)}")

    seed_stats = []
    all_raw = []
    deduped = {}

    for seed in seeds:
        seed_url = seed["seed_url"]
        category = seed.get("category", "").strip()
        tags = seed.get("tags", "").strip()
        usage = seed.get("usage_note", "").strip()

        urls, errors = fetch_dl_urls(seed_url, args.pages_per_seed)
        raw_count = len(urls)
        all_raw.extend(urls)

        # seed 内部去重
        unique_for_seed = []
        for u in urls:
            if u not in deduped:
                deduped[u] = {
                    "url": u,
                    "category": category,
                    "tags": tags,
                    "usage_note": usage,
                    "source_seed": seed_url,
                }
                unique_for_seed.append(u)

        seed_stats.append({
            "seed_url": seed_url,
            "raw": raw_count,
            "unique": len(unique_for_seed),
            "errors": errors,
        })

        if errors:
            print(f"  WARN {seed_url}: {len(errors)} page(s) failed")
            for e_url, e_msg in errors:
                print(f"    - {e_url}: {e_msg}")

    # 全局去重后的候选
    all_unique_candidates = list(deduped.values())

    # 与现有库去重
    new_candidates = []
    dup_seen = 0
    dup_manifest = 0
    dup_index = 0

    for cand in all_unique_candidates:
        u = cand["url"]
        if u in seen_urls:
            dup_seen += 1
            continue
        if u in manifest_urls:
            dup_manifest += 1
            continue
        if u in index_urls:
            dup_index += 1
            continue
        new_candidates.append(cand)

    # 应用 limit
    limited = new_candidates[:args.limit]

    print("\n=== Scraping Summary ===")
    for stat in seed_stats:
        print(f"  {stat['seed_url']}: raw={stat['raw']}, unique={stat['unique']}")
    print(f"\nTotal raw scraped: {len(all_raw)}")
    print(f"After dedup across seeds: {len(all_unique_candidates)}")
    print(f"Duplicate with seen_candidates: {dup_seen}")
    print(f"Duplicate with manifest: {dup_manifest}")
    print(f"Duplicate with index: {dup_index}")
    print(f"Truly new candidates: {len(new_candidates)}")
    print(f"Output limited to: {len(limited)} (limit={args.limit})")

    # 按 category 统计
    category_counts = Counter(c["category"] for c in limited)
    print("\n=== Candidates by Category ===")
    for cat, cnt in sorted(category_counts.items()):
        print(f"  {cat}: {cnt}")

    # 写入临时 CSV（即使 dry-run 也写，因为这是生成的候选列表，不是修改核心数据）
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "category", "tags", "usage_note", "source_seed"])
        writer.writeheader()
        for cand in limited:
            writer.writerow(cand)

    print(f"\nGenerated CSV: {output_csv.relative_to(BASE_DIR)}")

    if args.dry_run:
        print("\nDRY-RUN: manifest and seen_candidates were NOT modified.")
    else:
        print("\nTo add these candidates, run:")
        print(f"  python scripts/add_artvee_candidates.py --input-file {output_csv.relative_to(BASE_DIR)} --limit {args.limit}")

    # 输出前 30 条可新增候选
    print("\n=== First 30 New Candidates ===")
    for i, cand in enumerate(limited[:30], 1):
        print(f"{i}. {cand['url']},{cand['category']},\"{cand['tags']}\",\"{cand['usage_note']}\",{cand['source_seed']}")


if __name__ == "__main__":
    main()
