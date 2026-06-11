#!/usr/bin/env python3
"""
Artvee Nightly Batch Runner
每天凌晨调度执行，自动选择待处理记录并调用下载器。
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 将 scripts 目录加入路径以便 import download_artvee_selected
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import download_artvee_selected as dav

BASE_DIR = Path(__file__).resolve().parent.parent
INBOX_CSV = BASE_DIR / "inbox" / "manifest.csv"
INDEX_CSV = BASE_DIR / "index" / "artworks.csv"
IMAGES_DIR = BASE_DIR / "images"
METADATA_DIR = BASE_DIR / "metadata"
NIGHTLY_LOGS_DIR = BASE_DIR / "logs" / "nightly_runs"
SUMMARY_CSV = BASE_DIR / "logs" / "nightly_summary.csv"
LOCK_FILE = BASE_DIR / "logs" / "artvee_nightly.lock"


def log(msg, fh):
    line = f"[{datetime.now().isoformat()}] {msg}"
    print(line)
    fh.write(line + "\n")
    fh.flush()


def acquire_lock():
    if LOCK_FILE.exists():
        try:
            pid = LOCK_FILE.read_text().strip()
            if pid and os.path.exists(f"/proc/{pid}"):
                return False, pid
        except Exception:
            pass
        # 锁文件陈旧，删除
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass
    try:
        LOCK_FILE.write_text(str(os.getpid()))
        return True, None
    except Exception as e:
        return False, str(e)


def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


def load_manifest():
    records = []
    if not INBOX_CSV.exists():
        return records
    with open(INBOX_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if any(row.values()):
                records.append(row)
    return records


def save_manifest(records):
    fieldnames = ["url", "category", "download_variant", "tags", "usage_note", "status", "last_error"]
    with open(INBOX_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def load_index_existing():
    existing = {}
    if not INDEX_CSV.exists():
        return existing
    with open(INDEX_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("source_url", "").strip()
            path = row.get("local_image_path", "").strip()
            if url:
                existing[url] = path
    return existing


def append_to_index(rows):
    existing = load_index_existing()
    new_rows = []
    for row in rows:
        url = row.get("source_url", "").strip()
        if url and url not in existing:
            new_rows.append(row)

    if not new_rows:
        return 0

    index_exists = INDEX_CSV.exists() and INDEX_CSV.stat().st_size > 0
    with open(INDEX_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "artist", "title", "category", "download_variant",
                "tags", "usage_note", "source_url", "local_image_path", "metadata_path",
            ],
        )
        if not index_exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)
    return len(new_rows)


def select_candidates(records, limit, index_existing, log_fh):
    """选择 status 为空/pending/failed 的记录，pending 优先，failed 其次。"""
    candidates = []
    for idx, row in enumerate(records):
        status = row.get("status", "").strip().lower()
        url = row.get("url", "").strip()

        if status == "downloaded":
            continue

        # 显式排除终态（不再重试）
        if status in ("skipped", "dead", "manual_review"):
            continue

        # 跳过 index 中已存在且本地文件仍存在的
        if url in index_existing:
            img_path = BASE_DIR / index_existing[url]
            if img_path.exists():
                log(f"SKIP (index+file exists): {url}", log_fh)
                continue

        if status in ("", "pending", "failed"):
            candidates.append((idx, row, status))
        else:
            # 未知状态当作 pending 处理
            candidates.append((idx, row, "pending"))

    # 排序：pending > 空 > failed
    def sort_key(item):
        s = item[2]
        if s == "pending":
            return 0
        if s == "":
            return 1
        if s == "failed":
            return 2
        return 3

    candidates.sort(key=sort_key)
    selected = candidates[:limit]
    return selected


def run_batch(dry_run=False, limit=20):
    NIGHTLY_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = NIGHTLY_LOGS_DIR / f"nightly_run_{run_timestamp}.log"
    log_fh = open(log_path, "w", encoding="utf-8")

    log("=== Artvee Nightly Batch Started ===", log_fh)
    log(f"dry_run={dry_run}, limit={limit}", log_fh)

    # 锁
    acquired, lock_info = acquire_lock()
    if not acquired:
        log(f"ABORT: another instance is running (lock pid={lock_info})", log_fh)
        log_fh.close()
        return

    try:
        # 浏览器检查（dry-run 也做，方便提前发现问题）
        if not dav.check_browser_available():
            log("ABORT: browser automation not available", log_fh)
            return

        records = load_manifest()
        log(f"manifest total records: {len(records)}", log_fh)

        index_existing = load_index_existing()
        selected = select_candidates(records, limit, index_existing, log_fh)
        log(f"selected {len(selected)} candidates", log_fh)

        if not selected:
            log("No candidates to process. Exiting.", log_fh)
            _write_summary(run_timestamp, 0, 0, 0, 0, str(log_path.relative_to(BASE_DIR)))
            return

        for i, (idx, row, status) in enumerate(selected, start=1):
            url = row["url"]
            category = row.get("category", "").strip()
            download_variant = row.get("download_variant", "").strip() or "standard"
            tags = row.get("tags", "").strip()
            usage_note = row.get("usage_note", "").strip()

            log(f"[{i}/{len(selected)}] selected: {url} (prior_status={status})", log_fh)

            if dry_run:
                continue

            # 实际下载
            try:
                artist, title, dl_url = dav.fetch_page_with_browser(url, i)
            except Exception as e:
                err_msg = str(e)
                log(f"[{i}/{len(selected)}] FAILED at fetch: {err_msg}", log_fh)
                row["status"] = "failed"
                row["last_error"] = err_msg
                continue

            # 文件名
            norm_artist = dav.normalize_artist_or_title(artist)
            norm_title = dav.normalize_artist_or_title(title)
            norm_cat = dav.normalize_category(category)
            base_name = f"{norm_artist}_{norm_title}_{norm_cat}_{download_variant.lower()}"

            ext = ".jpg"
            if ".png" in dl_url.lower():
                ext = ".png"
            elif ".jpeg" in dl_url.lower():
                ext = ".jpeg"

            image_filename = base_name + ext
            image_path = IMAGES_DIR / category / image_filename
            image_path.parent.mkdir(parents=True, exist_ok=True)

            meta_filename = base_name + ".json"
            meta_path = METADATA_DIR / meta_filename

            try:
                dav.download_image(dl_url, image_path)
            except Exception as e:
                err_msg = str(e)
                log(f"[{i}/{len(selected)}] FAILED at download: {err_msg}", log_fh)
                row["status"] = "failed"
                row["last_error"] = err_msg
                continue

            # metadata
            downloaded_at = datetime.now().isoformat()
            metadata = {
                "source": "artvee.com",
                "url": url,
                "artist": norm_artist,
                "title": norm_title,
                "category": category,
                "download_variant": download_variant,
                "tags": tags,
                "usage_note": usage_note,
                "local_image_path": str(image_path.relative_to(BASE_DIR)),
                "raw_artist": artist,
                "raw_title": title,
                "normalized_artist": norm_artist,
                "normalized_title": norm_title,
                "downloaded_at": downloaded_at,
                "file_exists": True,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            log(f"[{i}/{len(selected)}] saved metadata: {meta_path.relative_to(BASE_DIR)}", log_fh)

            # 更新 manifest
            row["status"] = "downloaded"
            row["last_error"] = ""

            # index 行
            index_row = {
                "artist": artist,
                "title": title,
                "category": category,
                "download_variant": download_variant,
                "tags": tags,
                "usage_note": usage_note,
                "source_url": url,
                "local_image_path": str(image_path.relative_to(BASE_DIR)),
                "metadata_path": str(meta_path.relative_to(BASE_DIR)),
            }
            append_to_index([index_row])
            log(f"[{i}/{len(selected)}] SUCCESS", log_fh)

            if i < len(selected):
                log("sleeping 8s...", log_fh)
                time.sleep(8)

        # 保存 manifest
        if not dry_run:
            save_manifest(records)
            log("manifest saved", log_fh)
            # 同步更新 seen_candidates
            try:
                dav.sync_seen_from_manifest(records)
                log("seen_candidates synced", log_fh)
            except Exception as e:
                log(f"WARN: failed to sync seen_candidates: {e}", log_fh)

        # 统计
        downloaded = sum(1 for r in records if r.get("status") == "downloaded")
        failed = sum(1 for r in records if r.get("status") == "failed")
        pending = sum(1 for r in records if r.get("status", "").strip() in ("", "pending"))
        skipped = len(records) - len(selected) if not dry_run else len(records) - len(selected)

        log(f"stats: downloaded={downloaded}, failed={failed}, pending={pending}, skipped={skipped}", log_fh)
        _write_summary(run_timestamp, len(selected), downloaded, failed, skipped, str(log_path.relative_to(BASE_DIR)))

    finally:
        release_lock()
        log("=== Artvee Nightly Batch Finished ===", log_fh)
        log_fh.close()


def _write_summary(run_at, selected, downloaded, failed, skipped, log_path):
    fieldnames = ["run_at", "selected_count", "downloaded_count", "failed_count", "skipped_count", "log_path"]
    exists = SUMMARY_CSV.exists() and SUMMARY_CSV.stat().st_size > 0
    with open(SUMMARY_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "run_at": run_at,
            "selected_count": selected,
            "downloaded_count": downloaded,
            "failed_count": failed,
            "skipped_count": skipped,
            "log_path": log_path,
        })


def main():
    parser = argparse.ArgumentParser(description="Artvee Nightly Batch Runner")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be processed")
    parser.add_argument("--limit", type=int, default=20, help="Max records to process (default: 20)")
    args = parser.parse_args()

    run_batch(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
