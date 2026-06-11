#!/usr/bin/env python3
"""
Artvee Pending Refill Planner
按类别配额自动补货：检查 manifest pending 数量，若低于阈值则触发补货。
"""

import argparse
import csv
import glob
import re
import subprocess
import sys
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST = BASE_DIR / "inbox" / "manifest.csv"
INDEX_CSV = BASE_DIR / "index" / "artworks.csv"
SEEN_CSV = BASE_DIR / "index" / "seen_candidates.csv"
LOGS_DIR = BASE_DIR / "logs"
SCRAPE_SCRIPT = BASE_DIR / "scripts" / "scrape_artvee_seeds.py"
ADDER_SCRIPT = BASE_DIR / "scripts" / "add_artvee_candidates.py"
PYTHON = Path(sys.executable)


def parse_category_targets(s):
    """解析 'cat1=10,cat2=20' 为字典。"""
    result = {}
    if not s:
        return result
    for part in s.split(","):
        if "=" in part:
            cat, val = part.split("=", 1)
            result[cat.strip()] = int(val.strip())
    return result


def count_pending_by_category():
    """统计 manifest 中各 category 的 pending 数量。"""
    counts = Counter()
    if not MANIFEST.exists():
        return counts
    with open(MANIFEST, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            status = row.get("status", "").strip().lower()
            if status in ("", "pending"):
                cat = row.get("category", "").strip() or "uncategorized"
                counts[cat] += 1
    return counts


def count_total_pending(counts):
    return sum(counts.values())


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
                urls.add(val)
    return urls


from urllib.parse import urlparse

def normalize_url(url):
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") + "/" if parsed.path else "/"
    return f"{parsed.scheme}://{netloc}{path}"


def find_latest_generated_csv(before_globs):
    """找出调用 scrape 后新增的 generated_candidates_*.csv。"""
    after = set(glob.glob(str(LOGS_DIR / "generated_candidates_*.csv")))
    new = after - before_globs
    if not new:
        # 回退：找最新的文件
        candidates = list(after)
        if not candidates:
            return None
        return max(candidates, key=lambda p: Path(p).stat().st_mtime)
    return max(new, key=lambda p: Path(p).stat().st_mtime)


def main():
    parser = argparse.ArgumentParser(description="Category-quota Artvee pending refill")
    parser.add_argument("--min-pending", type=int, default=60, help="Global minimum pending threshold")
    parser.add_argument("--target-pending", type=int, default=120, help="Global target pending count")
    parser.add_argument("--dry-run", action="store_true", help="Only show plan, do not execute")
    parser.add_argument("--execute", action="store_true", help="Actually execute refill by calling add_artvee_candidates.py")
    parser.add_argument("--pages-per-seed", type=int, default=2, help="Pages to scrape per seed")
    parser.add_argument(
        "--per-category-targets",
        type=str,
        default="japanese-prints=36,book-illustrations=30,posters-design=30,botanical-charts=24",
        help='Category quotas, e.g. "cat1=10,cat2=20"',
    )
    args = parser.parse_args()

    cat_targets = parse_category_targets(args.per_category_targets)
    pending_by_cat = count_pending_by_category()
    total_pending = count_total_pending(pending_by_cat)

    print("=== Current Pending by Category ===")
    for cat, cnt in sorted(pending_by_cat.items()):
        print(f"  {cat}: {cnt}")
    print(f"  TOTAL: {total_pending}")

    print(f"\nMin pending threshold: {args.min_pending}")
    print(f"Target pending count:  {args.target_pending}")

    if total_pending >= args.min_pending:
        print(f"\nNo refill needed. Pending ({total_pending}) >= min ({args.min_pending})")
        return

    # 计算每个 category 的缺口
    print("\n=== Category Gaps ===")
    gaps = {}
    for cat, target in cat_targets.items():
        current = pending_by_cat.get(cat, 0)
        gap = max(0, target - current)
        gaps[cat] = gap
        print(f"  {cat}: current={current}, target={target}, gap={gap}")

    total_gap = sum(gaps.values())
    print(f"\nTotal gap across categories: {total_gap}")

    # Step D: 调用 scrape_artvee_seeds.py 生成候选
    print("\n=== Step D: Generate candidates via scrape_artvee_seeds.py ===")
    before_globs = set(glob.glob(str(LOGS_DIR / "generated_candidates_*.csv")))

    # 为了确保所有 category 都能拿到足够候选，scrape limit 设得足够大
    limit_for_scrape = 9999
    cmd = [
        str(PYTHON),
        str(SCRAPE_SCRIPT),
        "--pages-per-seed", str(args.pages_per_seed),
        "--limit", str(limit_for_scrape),
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: scrape_artvee_seeds.py failed with code {result.returncode}")
        print(result.stderr)
        sys.exit(1)

    # 读取生成的 CSV
    generated_csv = find_latest_generated_csv(before_globs)
    if not generated_csv or not Path(generated_csv).exists():
        print("ERROR: No generated_candidates CSV found after scraping.")
        sys.exit(1)
    generated_csv = Path(generated_csv)
    print(f"Using generated CSV: {generated_csv.relative_to(BASE_DIR)}")

    # 读取候选
    candidates = []
    with open(generated_csv, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("url", "").strip():
                candidates.append(row)

    print(f"Total candidates generated: {len(candidates)}")

    # 加载去重集合
    seen_urls = {normalize_url(u) for u in load_normalized_urls_from_csv(SEEN_CSV, "normalized_url")}
    manifest_urls = {normalize_url(u) for u in load_normalized_urls_from_csv(MANIFEST, "url")}
    index_urls = {normalize_url(u) for u in load_normalized_urls_from_csv(INDEX_CSV, "source_url")}

    # Step E & F: 按 category 缺口挑选，去重
    print("\n=== Step E/F: Select by category gap with dedup ===")
    selected_by_cat = Counter()
    shortfalls = {}
    plan_records = []

    # 按 category 分组候选
    cand_by_cat = {}
    for cand in candidates:
        cat = cand.get("category", "").strip() or "uncategorized"
        cand_by_cat.setdefault(cat, []).append(cand)

    for cat, gap in sorted(gaps.items()):
        if gap <= 0:
            continue
        pool = cand_by_cat.get(cat, [])
        picked = 0
        for cand in pool:
            if picked >= gap:
                break
            norm = normalize_url(cand["url"])
            if norm in seen_urls or norm in manifest_urls or norm in index_urls:
                continue
            plan_records.append(cand)
            selected_by_cat[cat] += 1
            picked += 1
            # 标记为已用，防止跨 category 重复（虽然 category 内一般已去重）
            seen_urls.add(norm)

        if picked < gap:
            shortfalls[cat] = gap - picked

    print(f"\nPlanned additions: {len(plan_records)}")
    print("=== Planned additions by category ===")
    for cat, cnt in sorted(selected_by_cat.items()):
        print(f"  {cat}: +{cnt}")
    if shortfalls:
        print("=== Shortfalls (insufficient candidates) ===")
        for cat, short in sorted(shortfalls.items()):
            print(f"  {cat}: short by {short}")
    else:
        print("=== Shortfalls: none ===")

    # Step G/H: dry-run vs execute
    if args.dry_run:
        print("\nDRY-RUN: No manifest or seen_candidates updated.")
        if args.execute:
            print("(Note: --execute is ignored because --dry-run is present)")
        return

    if not args.execute:
        print("\nPlan prepared but NOT executed. To execute, rerun with --execute.")
        return

    # Execute: 写入临时 CSV 并调用 add_artvee_candidates.py
    if not plan_records:
        print("\nNo candidates to add. Nothing executed.")
        return

    temp_csv = LOGS_DIR / f"refill_batch_{generated_csv.stem.replace('generated_candidates_', '')}.csv"
    with open(temp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "category", "tags", "usage_note", "source_seed"])
        writer.writeheader()
        for row in plan_records:
            writer.writerow(row)

    add_cmd = [
        str(PYTHON),
        str(ADDER_SCRIPT),
        "--input-file", str(temp_csv),
        "--limit", str(len(plan_records)),
    ]
    print(f"\nExecuting: {' '.join(add_cmd)}")
    add_result = subprocess.run(add_cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(add_result.stdout)
    if add_result.returncode != 0:
        print(f"ERROR: add_artvee_candidates.py failed with code {add_result.returncode}")
        print(add_result.stderr)
        sys.exit(1)

    print("\nRefill executed successfully.")


if __name__ == "__main__":
    main()
