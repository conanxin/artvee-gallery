#!/usr/bin/env python3
"""
Artvee 精选最小下载脚本（硬化版）。
顺序处理 inbox/manifest.csv 的前 3 条记录，不并发，每条间隔 8 秒。
优先使用浏览器自动化；遇到浏览器不可用、403、验证码、页面结构异常、下载按钮缺失等情况时立刻停止并记录原因。

新增硬化特性：
- 跳过 status=downloaded 的记录
- 跳过 index 中已存在且本地文件仍存在的 source_url
- 下载成功后更新 manifest status 并去重写入 index
- 简化文件命名，过滤国籍/年份等冗余信息
- metadata 增加 raw/normalized 字段与下载时间戳
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INBOX_CSV = BASE_DIR / "inbox" / "manifest.csv"
INDEX_CSV = BASE_DIR / "index" / "artworks.csv"
SEEN_CSV = BASE_DIR / "index" / "seen_candidates.csv"
IMAGES_DIR = BASE_DIR / "images"
METADATA_DIR = BASE_DIR / "metadata"
LOGS_DIR = BASE_DIR / "logs"

LOG_FILE = LOGS_DIR / f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def normalize_url(url):
    from urllib.parse import urlparse
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
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return seen
        for row in reader:
            norm = row.get("normalized_url", "").strip()
            if norm:
                seen[norm] = row
    return seen


def save_seen(seen):
    SEEN_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_url", "normalized_url", "slug", "first_seen_at", "last_seen_at", "status"]
    with open(SEEN_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in seen.values():
            writer.writerow(row)


def sync_seen_from_manifest(manifest_records):
    """根据 manifest 状态同步更新 seen_candidates.csv。"""
    seen = load_seen()
    now = datetime.now().isoformat()
    updated = 0
    for row in manifest_records:
        url = row.get("url", "").strip()
        if not url:
            continue
        norm = normalize_url(url)
        if norm not in seen:
            continue
        manifest_status = row.get("status", "").strip().lower()
        seen_status = seen[norm].get("status", "").strip().lower()
        if manifest_status == "downloaded":
            if seen_status != "downloaded":
                seen[norm]["status"] = "downloaded"
                updated += 1
            seen[norm]["last_seen_at"] = now
            updated += 1
        elif manifest_status == "failed":
            if seen_status != "failed":
                seen[norm]["status"] = "failed"
                updated += 1
            seen[norm]["last_seen_at"] = now
            updated += 1
        elif manifest_status in ("", "pending"):
            if seen_status != "pending":
                seen[norm]["status"] = "pending"
                updated += 1
            # pending 保持 pending，但刷新 last_seen_at 可选；这里不强制刷新 pending 的时间
    if updated:
        save_seen(seen)
        log(f"synced {updated} seen_candidates entries")
    return updated


def log(msg):
    line = f"[{datetime.now().isoformat()}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def normalize_artist_or_title(name):
    """清理艺术家/标题中的冗余信息（国籍、年份、括号）。"""
    name = name.strip()
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"\d{2,4}\s*[-–]\s*\d{2,4}", "", name)
    name = re.sub(r",?\s*(Japanese|American|French|British|German|Italian|Dutch|Spanish|Russian|Chinese)\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[\s,]+", "_", name)
    name = re.sub(r"[^\w\-\.]", "", name)
    name = name.strip("_")
    return name


def normalize_category(name):
    """清理 category（不过滤国籍词汇，只做基础清理）。"""
    name = name.strip()
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"\d{2,4}\s*[-–]\s*\d{2,4}", "", name)
    name = re.sub(r"ca\.\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[\s,]+", "_", name)
    name = re.sub(r"[^\w\-\.]", "", name)
    name = name.strip("_")
    return name


def sanitize_filename(name):
    """旧版兼容：现在直接调用 normalize_artist_or_title。"""
    return normalize_artist_or_title(name)


def save_debug_files(page, prefix):
    """保存调试文件到 logs 目录。"""
    html_path = LOGS_DIR / f"debug_{prefix}.html"
    png_path = LOGS_DIR / f"debug_{prefix}.png"
    try:
        content = page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"saved debug HTML to {html_path}")
    except Exception as e:
        log(f"failed to save debug HTML: {e}")
    try:
        page.screenshot(path=str(png_path))
        log(f"saved debug screenshot to {png_path}")
    except Exception as e:
        log(f"failed to save debug screenshot: {e}")
    return html_path, png_path


def check_browser_available():
    """检查浏览器自动化环境是否可用。"""
    try:
        import playwright
        log("playwright found")
    except ImportError as e:
        log(f"ERROR: playwright not installed ({e})")
        return False

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        log("browser launch test: OK")
    except Exception as e:
        log(f"ERROR: browser daemon failed to start ({e})")
        return False

    return True


def extract_title(page):
    """A. 标题提取：优先页面主标题，再 fallback。"""
    for sel in ["h1", "article h1", "header h1", "main h1", ".entry-title", "[class*='title'] h1"]:
        try:
            elem = page.locator(sel).first
            if elem.is_visible(timeout=2000):
                text = elem.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue

    try:
        pt = page.title().strip()
        if " - " in pt:
            pt = pt.rsplit(" - ", 1)[0]
        if pt:
            return pt
    except Exception:
        pass

    try:
        og = page.locator("meta[property='og:title']").first.get_attribute("content")
        if og:
            return og.strip()
    except Exception:
        pass

    return "Unknown"


def extract_artist(page, title_text):
    """B. 艺术家提取：优先从标题下方附近的链接/文本提取。"""
    try:
        sibling = page.locator("h1 + *").first
        if sibling.is_visible(timeout=2000):
            text = sibling.inner_text().strip()
            if text and text != title_text and len(text) < 120:
                return text
    except Exception:
        pass

    try:
        h1 = page.locator("h1").first
        parent = h1.locator("..")
        children = parent.locator("*").all()
        for child in children[1:4]:
            try:
                tag = child.evaluate("el => el.tagName.toLowerCase()")
                text = child.inner_text().strip()
                if text and text != title_text and tag in ("a", "div", "span") and len(text) < 120:
                    lower = text.lower()
                    if not any(x in lower for x in ["facebook", "twitter", "pinterest", "favourite", "collect", "download", "standard", "max size", "browse", "login"]):
                        return text
            except Exception:
                continue
    except Exception:
        pass

    try:
        h1_bbox = page.locator("h1").first.bounding_box()
        h1_y = h1_bbox["y"] if h1_bbox else 0
        links = page.locator("a").all()
        for link in links:
            try:
                if not link.is_visible():
                    continue
                text = link.inner_text().strip()
                if not text or text == title_text or len(text) > 120:
                    continue
                lower = text.lower()
                if any(x in lower for x in ["facebook", "twitter", "pinterest", "favourite", "collect", "download", "standard", "max size", "browse", "login"]):
                    continue
                bbox = link.bounding_box()
                if bbox and 0 < (bbox["y"] - h1_y) < 200:
                    return text
            except Exception:
                continue
    except Exception:
        pass

    try:
        body = page.locator("body").inner_text().replace('\n', ' ').replace('\t', ' ')
        escaped = re.escape(title_text)
        m = re.search(escaped + r"[\s\)]+([^\d\n]{3,60}?)(?:Facebook|Twitter|Pinterest|Favourite|Collect|License|Download|Standard|Max Size)", body)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    return "Unknown"


def extract_standard_download(page, row_idx):
    """C. 下载链接提取：优先查找 href 中包含 mdl.artvee.com 的可见链接。"""
    candidates = []
    try:
        links = page.locator("a[href*='mdl.artvee.com']").all()
        for link in links:
            try:
                if not link.is_visible():
                    continue
                href = link.get_attribute("href")
                text = link.inner_text().strip().lower()
                if not href:
                    continue
                bbox = link.bounding_box()
                y = bbox["y"] if bbox else 999999
                candidates.append({"href": href, "text": text, "y": y})
            except Exception:
                continue
    except Exception:
        pass

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]["href"]

    candidates.sort(key=lambda x: x["y"])
    return candidates[0]["href"]


def fetch_page_with_browser(page_url, row_idx):
    """使用 playwright 访问页面并提取下载链接与元数据。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        log(f"navigating to {page_url}")
        response = page.goto(page_url, timeout=30000)

        if response is None:
            raise RuntimeError("page load returned None")

        status = response.status
        log(f"page status: {status}")

        if status == 403:
            raise RuntimeError("403 Forbidden")
        if status == 429:
            raise RuntimeError("429 Too Many Requests / rate limited")
        if status >= 400:
            raise RuntimeError(f"HTTP {status}")

        body_text = page.content().lower()
        if "captcha" in body_text or "recaptcha" in body_text or "verify you are human" in body_text:
            raise RuntimeError("captcha detected")

        title = extract_title(page)
        log(f"parsed title='{title}'")

        artist = extract_artist(page, title)
        log(f"parsed artist='{artist}'")

        dl_url = extract_standard_download(page, row_idx)
        if dl_url is None:
            log("DEBUG: download link not found, collecting debug info...")
            try:
                log(f"DEBUG page.title() = {page.title()}")
            except Exception as e:
                log(f"DEBUG page.title() error: {e}")
            log(f"DEBUG current_url = {page.url}")
            try:
                body_plain = page.locator("body").inner_text().replace('\n', ' ').replace('\t', ' ')[:2000]
                log(f"DEBUG body_text(2000) = {body_plain}")
            except Exception as e:
                log(f"DEBUG body_text error: {e}")
            try:
                dl_elems = page.locator("a").all()
                for i, elem in enumerate(dl_elems):
                    try:
                        if elem.is_visible() and "download" in elem.inner_text().lower():
                            log(f"DEBUG download_element[{i}] text='{elem.inner_text().strip()[:80]}' href='{(elem.get_attribute('href') or '')[:100]}'")
                    except Exception:
                        pass
            except Exception as e:
                log(f"DEBUG download_elements error: {e}")
            try:
                mdl_links = page.locator("a[href*='mdl.artvee.com']").all()
                for i, link in enumerate(mdl_links):
                    try:
                        log(f"DEBUG mdl_link[{i}] visible={link.is_visible()} text='{link.inner_text().strip()[:40]}' href='{link.get_attribute('href')[:100]}...'")
                    except Exception:
                        pass
            except Exception as e:
                log(f"DEBUG mdl_links error: {e}")

            save_debug_files(page, f"row{row_idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            raise RuntimeError("download button/link not found")

        log(f"found download url: {dl_url[:120]}...")
        browser.close()
        return artist, title, dl_url


def download_image(url, dest_path):
    """直接下载图片到指定路径。"""
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    })
    with urllib.request.urlopen(req, timeout=60) as response:
        if response.status == 403:
            raise RuntimeError("403 Forbidden on image download")
        with open(dest_path, "wb") as f:
            f.write(response.read())
    log(f"saved image to {dest_path}")


def load_index_urls():
    """加载 index 中已有的 source_url 集合以及 url->local_image_path 映射。"""
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


def update_manifest(records):
    """将更新后的 manifest 写回 CSV。"""
    fieldnames = ["url", "category", "download_variant", "tags", "usage_note", "status", "last_error"]
    with open(INBOX_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    log("manifest.csv updated")


def append_to_index(rows):
    """向 index/artworks.csv 追加记录，不重复写入同一个 source_url。"""
    existing = load_index_urls()
    new_rows = []
    for row in rows:
        url = row.get("source_url", "").strip()
        if url and url not in existing:
            new_rows.append(row)
        elif url in existing:
            log(f"SKIP index append: {url} already exists")

    if not new_rows:
        return

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
    log(f"appended {len(new_rows)} rows to index")


def main():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    log("=== Artvee Download Test Started ===")

    if not check_browser_available():
        log("ABORT: browser automation is not available")
        sys.exit(1)

    if not INBOX_CSV.exists():
        log(f"ABORT: manifest not found at {INBOX_CSV}")
        sys.exit(1)

    # 加载 manifest
    manifest_records = []
    with open(INBOX_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if any(row.values()):
                manifest_records.append(row)

    log(f"manifest records found: {len(manifest_records)}")

    # 加载 index 去重信息
    index_existing = load_index_urls()

    target_records = manifest_records[:3]
    log(f"will process first {len(target_records)} records")

    results = []
    index_rows = []

    for idx, row in enumerate(target_records, start=1):
        url = row.get("url", "").strip()
        category = row.get("category", "").strip()
        download_variant = row.get("download_variant", "").strip() or "standard"
        tags = row.get("tags", "").strip()
        usage_note = row.get("usage_note", "").strip()
        status = row.get("status", "").strip()

        log(f"[{idx}/3] processing: {url} | category={category}")

        # 跳过已下载
        if status == "downloaded":
            log(f"[{idx}/3] SKIP: status=downloaded in manifest")
            row["last_error"] = ""
            results.append({
                "idx": idx,
                "url": url,
                "status": "skipped",
                "reason": "already downloaded",
                "local_image_path": "",
                "metadata_path": "",
            })
            continue

        # 跳过 index 中已存在且文件仍然存在的记录
        if url in index_existing:
            existing_path = BASE_DIR / index_existing[url]
            if existing_path.exists():
                log(f"[{idx}/3] SKIP: image already exists at {existing_path}")
                row["status"] = "downloaded"
                row["last_error"] = ""
                results.append({
                    "idx": idx,
                    "url": url,
                    "status": "skipped",
                    "reason": "index exists and local file present",
                    "local_image_path": str(existing_path.relative_to(BASE_DIR)),
                    "metadata_path": "",
                })
                continue
            else:
                log(f"[{idx}/3] WARN: index exists but local file missing, will re-download")

        try:
            artist, title, dl_url = fetch_page_with_browser(url, idx)
        except RuntimeError as e:
            log(f"[{idx}/3] FAILED at page fetch: {e}")
            row["status"] = "failed"
            row["last_error"] = str(e)
            results.append({
                "idx": idx,
                "url": url,
                "status": "failed",
                "reason": str(e),
                "local_image_path": "",
                "metadata_path": "",
            })
            log("HALT: stopping due to fetch failure")
            break
        except Exception as e:
            log(f"[{idx}/3] FAILED with exception: {e}")
            row["status"] = "failed"
            row["last_error"] = str(e)
            results.append({
                "idx": idx,
                "url": url,
                "status": "failed",
                "reason": str(e),
                "local_image_path": "",
                "metadata_path": "",
            })
            log("HALT: stopping due to unexpected exception")
            break

        # 准备文件名（简化版）
        norm_artist = normalize_artist_or_title(artist)
        norm_title = normalize_artist_or_title(title)
        norm_category = normalize_category(category)
        base_name = f"{norm_artist}_{norm_title}_{norm_category}_{download_variant.lower()}"

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

        # 下载图片
        try:
            download_image(dl_url, image_path)
        except RuntimeError as e:
            log(f"[{idx}/3] FAILED at image download: {e}")
            row["status"] = "failed"
            row["last_error"] = str(e)
            results.append({
                "idx": idx,
                "url": url,
                "status": "failed",
                "reason": str(e),
                "local_image_path": "",
                "metadata_path": "",
            })
            log("HALT: stopping due to image download failure")
            break
        except Exception as e:
            log(f"[{idx}/3] FAILED at image download: {e}")
            row["status"] = "failed"
            row["last_error"] = str(e)
            results.append({
                "idx": idx,
                "url": url,
                "status": "failed",
                "reason": str(e),
                "local_image_path": "",
                "metadata_path": "",
            })
            log("HALT: stopping due to image download exception")
            break

        # 写 metadata
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
        log(f"saved metadata to {meta_path}")

        # 更新 manifest
        row["status"] = "downloaded"
        row["last_error"] = ""

        # 准备 index 行
        index_rows.append({
            "artist": artist,
            "title": title,
            "category": category,
            "download_variant": download_variant,
            "tags": tags,
            "usage_note": usage_note,
            "source_url": url,
            "local_image_path": str(image_path.relative_to(BASE_DIR)),
            "metadata_path": str(meta_path.relative_to(BASE_DIR)),
        })

        results.append({
            "idx": idx,
            "url": url,
            "status": "success",
            "reason": "",
            "local_image_path": str(image_path.relative_to(BASE_DIR)),
            "metadata_path": str(meta_path.relative_to(BASE_DIR)),
            "artist": artist,
            "title": title,
            "category": category,
            "download_variant": download_variant,
            "tags": tags,
            "usage_note": usage_note,
        })

        log(f"[{idx}/3] SUCCESS")

        if idx < len(target_records):
            log("sleeping 8s before next record...")
            time.sleep(8)

    # 更新 manifest 和 index
    update_manifest(manifest_records)
    append_to_index(index_rows)

    # 同步更新 seen_candidates
    sync_seen_from_manifest(manifest_records)

    log("=== Artvee Download Test Finished ===")

    print("\n--- SUMMARY ---")
    for r in results:
        print(f"[{r['idx']}/3] {r['status'].upper()}: {r['url']}")
        if r["status"] == "failed":
            print(f"    reason: {r['reason']}")
        elif r["status"] == "success":
            print(f"    image : {r['local_image_path']}")
            print(f"    meta  : {r['metadata_path']}")
        else:
            print(f"    reason: {r['reason']}")


if __name__ == "__main__":
    main()
