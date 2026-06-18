#!/usr/bin/env bash
#
# confirm_demo_refresh.sh · P4D+1
#
# 用途：每天 02:30 (CRON_TZ=Asia/Shanghai) 在 nightly batch 之后，
#      自动构建「public demo refresh 候选包」并做 QA，
#      但 **不** 自动 push GitHub Pages、**不** 触发出下载/refill/batch。
#
# 输出：dist/refresh-candidates/YYYY-MM-DD/{gallery,digest}/
# 日志：logs/confirm_demo_refresh/confirm_demo_refresh_YYYYMMDD_HHMMSS.log
# 报告：logs/confirm_demo_refresh/report_YYYY-MM-DD.md
# 摘要：Telegram (--no-telegram 时跳过)
#
# Local-first invariant:
#   - 不读 / 不写 Pages repo (env PAGES_REPO)
#   - 不 git push
#   - 不发请求到 Artvee 站点
#   - 不修改 runtime data (images / metadata / thumbs / web/data / index)
#   - 不 retry 4 unresolved losers
#
# 用法：
#   bash scripts/confirm_demo_refresh.sh                       # 默认 (今天)
#   bash scripts/confirm_demo_refresh.sh --date 2026-06-12     # 指定日期
#   bash scripts/confirm_demo_refresh.sh --dry-run             # 只打印，不写文件
#   bash scripts/confirm_demo_refresh.sh --no-telegram         # 跑完不发 Telegram
#   bash scripts/confirm_demo_refresh.sh --help                # 帮助
#

set -euo pipefail

# ----------------------------------------------------------------------------
# 参数解析
# ----------------------------------------------------------------------------

DATE="$(date '+%Y-%m-%d')"
DRY_RUN=0
NO_TELEGRAM=0
BASE_DIR=""
PYTHON_BIN="${ARTVEE_PYTHON:-python3}"
# PAGES_REPO: only used in user-facing publish instructions in the report.
# Default is intentionally a placeholder (no path leak) so set -u doesn't
# trip. Users override this with the actual Pages repo path before publish.
PAGES_REPO="${PAGES_REPO:-<pages-repo>}"

print_help() {
    cat <<'USAGE'
用法：bash scripts/confirm_demo_refresh.sh [options]

选项:
  --date YYYY-MM-DD     指定候选日期 (默认今天)
  --dry-run             只打印步骤，不写 dist/logs/，不发 Telegram
  --no-telegram         正常跑流程但跳过 Telegram 通知
  --help                显示此帮助

默认: --date=today, 跑全部步骤, 跑完发 Telegram
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --date)
            DATE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --no-telegram)
            NO_TELEGRAM=1
            shift
            ;;
        --help|-h)
            print_help
            exit 0
            ;;
        *)
            echo "ERROR: unknown arg: $1" >&2
            print_help >&2
            exit 1
            ;;
    esac
done

# 验证日期格式 (best-effort)
if ! [[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR: --date must be YYYY-MM-DD, got: $DATE" >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# 路径与目录
# ----------------------------------------------------------------------------

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANDIDATE_BASE="$BASE_DIR/dist/refresh-candidates"
LOG_DIR="$BASE_DIR/logs/confirm_demo_refresh"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_LOG="$LOG_DIR/confirm_demo_refresh_${TIMESTAMP}.log"
REPORT="$LOG_DIR/report_${DATE}.md"
TELEGRAM_NOTIFIER="$BASE_DIR/scripts/artvee_telegram_notify.py"

GALLERY_OUT="$CANDIDATE_BASE/$DATE/gallery"
DIGEST_OUT="$CANDIDATE_BASE/$DATE/digest"

# 阈值 (per brief)
GALLERY_RECORD_TARGET=100
GALLERY_THUMB_TARGET=200
GALLERY_SOFT_LIMIT_MB=10
GALLERY_HARD_LIMIT_MB=20
DIGEST_SELECT_TARGET=5
# P8B digest size budgets — page is text-only + 1-5 thumbs; 5MB
# soft / 10MB hard keeps the bundle honest.
DIGEST_SOFT_LIMIT_MB=5
DIGEST_HARD_LIMIT_MB=10
GALLERY_SOFT_LIMIT_BYTES=$((GALLERY_SOFT_LIMIT_MB * 1024 * 1024))
GALLERY_HARD_LIMIT_BYTES=$((GALLERY_HARD_LIMIT_MB * 1024 * 1024))
DIGEST_SOFT_LIMIT_BYTES=$((DIGEST_SOFT_LIMIT_MB * 1024 * 1024))
DIGEST_HARD_LIMIT_BYTES=$((DIGEST_HARD_LIMIT_MB * 1024 * 1024))

# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------

_log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "$msg"
    else
        echo "$msg" | tee -a "$RUN_LOG"
    fi
}

_step() {
    _log "===== STEP: $1 ====="
}

# track current failing step (for telegram failure summary)
CURRENT_STAGE="init"
FAIL_STAGE=""
FAIL_REASON=""

_record_fail() {
    FAIL_STAGE="$CURRENT_STAGE"
    FAIL_REASON="$1"
    _log "FAILED at $CURRENT_STAGE: $1"
}

run_py() {
    # 通用 py_compile + python 包装
    "$PYTHON_BIN" "$@"
}

dir_size_bytes() {
    du -sb "$1" 2>/dev/null | awk '{print $1}' || echo "0"
}

dir_size_human() {
    du -sh "$1" 2>/dev/null | awk '{print $1}' || echo "0"
}

count_thumbs() {
    # count files under assets/thumbs/256 and assets/thumbs/512
    local root="$1"
    local n256=0 n512=0
    if [[ -d "$root/assets/thumbs/256" ]]; then
        n256=$(find "$root/assets/thumbs/256" -type f 2>/dev/null | wc -l)
    fi
    if [[ -d "$root/assets/thumbs/512" ]]; then
        n512=$(find "$root/assets/thumbs/512" -type f 2>/dev/null | wc -l)
    fi
    echo "$n256 $n512"
}

# ----------------------------------------------------------------------------
# 初始化
# ----------------------------------------------------------------------------

if [[ $DRY_RUN -eq 0 ]]; then
    mkdir -p "$LOG_DIR"
    : > "$RUN_LOG"
    _log "confirm_demo_refresh started"
    _log "BASE_DIR: $BASE_DIR"
    _log "DATE: $DATE"
    _log "GALLERY_OUT: $GALLERY_OUT"
    _log "DIGEST_OUT: $DIGEST_OUT"
    _log "RUN_LOG: $RUN_LOG"
fi

# ----------------------------------------------------------------------------
# 1. Preflight · check_open_source_ready
# ----------------------------------------------------------------------------

CURRENT_STAGE="preflight_open_source_ready"
_step "Preflight: check_open_source_ready"
if [[ $DRY_RUN -eq 0 ]]; then
    if ! "$PYTHON_BIN" "$BASE_DIR/scripts/check_open_source_ready.py" >> "$RUN_LOG" 2>&1; then
        _record_fail "check_open_source_ready.py failed; see $RUN_LOG"
        _finalize_and_exit 1
    fi
    _log "  ✅ check_open_source_ready PASS"
else
    _log "  (dry-run) would run: $PYTHON_BIN scripts/check_open_source_ready.py"
fi

# ----------------------------------------------------------------------------
# 2. Preflight · check_gallery_integrity --strict
# ----------------------------------------------------------------------------

CURRENT_STAGE="preflight_integrity"
_step "Preflight: check_gallery_integrity --strict"
if [[ $DRY_RUN -eq 0 ]]; then
    if ! "$PYTHON_BIN" "$BASE_DIR/scripts/check_gallery_integrity.py" --strict >> "$RUN_LOG" 2>&1; then
        _record_fail "check_gallery_integrity.py --strict failed; see $RUN_LOG"
        _finalize_and_exit 1
    fi
    _log "  ✅ check_gallery_integrity --strict PASS"
else
    _log "  (dry-run) would run: $PYTHON_BIN scripts/check_gallery_integrity.py --strict"
fi

# ----------------------------------------------------------------------------
# 3. Build local gallery (deterministic, no network) if needed
# ----------------------------------------------------------------------------

CURRENT_STAGE="build_local_gallery"
_step "Build local gallery (read-only deterministic)"
if [[ $DRY_RUN -eq 0 ]]; then
    if [[ ! -s "$BASE_DIR/web/data/artworks.json" ]]; then
        _log "  web/data/artworks.json missing/empty → running build_artvee_gallery.py --mode local"
        if ! "$PYTHON_BIN" "$BASE_DIR/scripts/build_artvee_gallery.py" --mode local >> "$RUN_LOG" 2>&1; then
            _record_fail "build_artvee_gallery.py --mode local failed; see $RUN_LOG"
            _finalize_and_exit 1
        fi
    else
        _log "  web/data/artworks.json present, skip build (deterministic)"
    fi
    _log "  ✅ local gallery OK"
else
    _log "  (dry-run) would ensure web/data/artworks.json exists"
fi

# ----------------------------------------------------------------------------
# 4. Build local digest (deterministic, no network) if needed
# ----------------------------------------------------------------------------

CURRENT_STAGE="build_local_digest"
_step "Build local digest for $DATE"
if [[ $DRY_RUN -eq 0 ]]; then
    # digest 重新生成是幂等的 (deterministic given same source + date)
    if ! "$PYTHON_BIN" "$BASE_DIR/scripts/build_artvee_daily_digest.py" \
            --strategy diverse --select 5 --candidate-limit 20 \
            --out-dir "$BASE_DIR/digests" >> "$RUN_LOG" 2>&1; then
        _record_fail "build_artvee_daily_digest.py failed; see $RUN_LOG"
        _finalize_and_exit 1
    fi
    _log "  ✅ digest built"
else
    _log "  (dry-run) would run build_artvee_daily_digest.py"
fi

# ----------------------------------------------------------------------------
# 5. Export Gallery public candidate
# ----------------------------------------------------------------------------

CURRENT_STAGE="export_gallery"
_step "Export Gallery public demo candidate"
if [[ $DRY_RUN -eq 0 ]]; then
    rm -rf "$GALLERY_OUT"
    mkdir -p "$GALLERY_OUT"
    if ! "$PYTHON_BIN" "$BASE_DIR/scripts/export_artvee_gallery_public_demo.py" \
            --limit 100 \
            --strategy diverse \
            --base-url . \
            --exclude-duplicate-source-url-groups \
            --require-unique-source-url \
            --exclude-risk high \
            --visual-qa "$BASE_DIR/reports/runtime/p5d-visual-qa-full.json" \
            --out-dir "$GALLERY_OUT" >> "$RUN_LOG" 2>&1; then
        _record_fail "gallery export failed; see $RUN_LOG"
        _finalize_and_exit 1
    fi
    _log "  ✅ gallery candidate at $GALLERY_OUT"
else
    _log "  (dry-run) would run export_artvee_gallery_public_demo.py → $GALLERY_OUT"
fi

# ----------------------------------------------------------------------------
# 6. Export Digest public candidate
# ----------------------------------------------------------------------------

CURRENT_STAGE="export_digest"
_step "Export Daily Digest public candidate"
if [[ $DRY_RUN -eq 0 ]]; then
    rm -rf "$DIGEST_OUT"
    mkdir -p "$DIGEST_OUT"
    if ! "$PYTHON_BIN" "$BASE_DIR/scripts/export_artvee_digest_public_page.py" \
            --base-url . \
            --out-dir "$DIGEST_OUT" >> "$RUN_LOG" 2>&1; then
        _record_fail "digest export failed; see $RUN_LOG"
        _finalize_and_exit 1
    fi
    _log "  ✅ digest candidate at $DIGEST_OUT"
else
    _log "  (dry-run) would run export_artvee_digest_public_page.py → $DIGEST_OUT"
fi

# ----------------------------------------------------------------------------
# 7. QA · Gallery
# ----------------------------------------------------------------------------

CURRENT_STAGE="qa_gallery"
_step "QA: Gallery candidate"

GALLERY_RECORDS=0
GALLERY_THUMB_256=0
GALLERY_THUMB_512=0
GALLERY_DUPE_ID=0
GALLERY_DUPE_SOURCE_URL=0
GALLERY_LE_REVE=0
GALLERY_LEAKS=0
GALLERY_MISSING=0
GALLERY_SIZE_BYTES=0
GALLERY_LARGEST=0
GALLERY_FINAL_STATUS="PASS"

if [[ $DRY_RUN -eq 0 ]]; then
    # 计数
    read -r GALLERY_THUMB_256 GALLERY_THUMB_512 <<<"$(count_thumbs "$GALLERY_OUT")"
    GALLERY_SIZE_BYTES=$(dir_size_bytes "$GALLERY_OUT")
    GALLERY_LARGEST=$(find "$GALLERY_OUT" -type f -printf '%s\n' 2>/dev/null | sort -n | tail -1 || echo 0)
    GALLERY_LARGEST="${GALLERY_LARGEST:-0}"

    # JSON 字段分析
    if [[ -s "$GALLERY_OUT/data/artworks.json" ]]; then
        mapfile -t QA_OUTPUT < <("$PYTHON_BIN" - "$GALLERY_OUT" <<'PY'
import json
import os
import sys
from collections import Counter
from pathlib import Path

base = Path(sys.argv[1])
art_path = base / 'data' / 'artworks.json'
if not art_path.is_file():
    print("NO_JSON")
    sys.exit(0)

try:
    arts = json.loads(art_path.read_text(encoding='utf-8'))
except Exception as e:
    print(f"JSON_PARSE_ERROR:{e}")
    sys.exit(0)

if not isinstance(arts, list):
    print("NOT_A_LIST")
    sys.exit(0)

records = len(arts)
ids = [a.get('id', '') for a in arts]
sus = [a.get('source_url', '') for a in arts]
sus_clean = [s for s in sus if s]
id_counter = Counter(ids)
sus_counter = Counter(sus_clean)

dupe_id_groups = sum(1 for v in id_counter.values() if v > 1)
dupe_sus_groups = sum(1 for v in sus_counter.values() if v > 1)

# local path leak check (forbidden substrings in any string field)
forbidden = ['/home/', '~/', 'hermes-agent', 'metadata/', 'images/']
leaks = 0
for a in arts:
    for k, v in a.items():
        if not isinstance(v, str):
            continue
        # skip fields that are public-aware relative paths (thumbs)
        if k in ('thumb_256', 'thumb_512', 'image_path', 'metadata_path'):
            # these must NOT contain forbidden substrings
            for f in forbidden:
                if f in v:
                    leaks += 1
                    break
        else:
            for f in forbidden:
                if f in v:
                    leaks += 1
                    break

# Le_rêve guard
le_reve = sum(1 for s in sus_clean if 'le-reve' in s)

# missing thumbs: check thumb_256 and thumb_512 files exist
missing = 0
for a in arts:
    for tk in ('thumb_256', 'thumb_512'):
        rel = a.get(tk, '')
        if not rel:
            missing += 1
            continue
        # rel starts with ./ or /assets/ or assets/
        rp = rel.lstrip('./')
        p = base / rp
        if not p.is_file():
            missing += 1

print(f"RECORDS={records}")
print(f"DUPE_ID_GROUPS={dupe_id_groups}")
print(f"DUPE_SOURCE_URL_GROUPS={dupe_sus_groups}")
print(f"LE_REVE={le_reve}")
print(f"LEAKS={leaks}")
print(f"MISSING={missing}")
PY
        )

        for line in "${QA_OUTPUT[@]}"; do
            case "$line" in
                RECORDS=*)            GALLERY_RECORDS="${line#RECORDS=}" ;;
                DUPE_ID_GROUPS=*)     GALLERY_DUPE_ID="${line#DUPE_ID_GROUPS=}" ;;
                DUPE_SOURCE_URL_GROUPS=*) GALLERY_DUPE_SOURCE_URL="${line#DUPE_SOURCE_URL_GROUPS=}" ;;
                LE_REVE=*)            GALLERY_LE_REVE="${line#LE_REVE=}" ;;
                LEAKS=*)              GALLERY_LEAKS="${line#LEAKS=}" ;;
                MISSING=*)            GALLERY_MISSING="${line#MISSING=}" ;;
                NO_JSON|JSON_PARSE_ERROR=*|NOT_A_LIST)
                    _log "  ⚠️ $line"
                    GALLERY_FINAL_STATUS="FAIL"
                    ;;
            esac
        done
    else
        GALLERY_FINAL_STATUS="FAIL"
        _log "  ⚠️ no data/artworks.json in gallery candidate"
    fi

    # QA gates
    if [[ "$GALLERY_RECORDS" -ne "$GALLERY_RECORD_TARGET" ]]; then
        _log "  ⚠️ records=$GALLERY_RECORDS (target=$GALLERY_RECORD_TARGET)"
        GALLERY_FINAL_STATUS="FAIL"
    fi
    if [[ "$GALLERY_THUMB_256" -ne "$GALLERY_RECORD_TARGET" || "$GALLERY_THUMB_512" -ne "$GALLERY_RECORD_TARGET" ]]; then
        _log "  ⚠️ thumbs 256=$GALLERY_THUMB_256 512=$GALLERY_THUMB_512 (target=$GALLERY_RECORD_TARGET each)"
        GALLERY_FINAL_STATUS="FAIL"
    fi
    if [[ "$GALLERY_DUPE_ID" -ne 0 ]]; then
        _log "  ⚠️ dupe id groups=$GALLERY_DUPE_ID"
        GALLERY_FINAL_STATUS="FAIL"
    fi
    if [[ "$GALLERY_DUPE_SOURCE_URL" -ne 0 ]]; then
        _log "  ⚠️ dupe source_url groups=$GALLERY_DUPE_SOURCE_URL"
        GALLERY_FINAL_STATUS="FAIL"
    fi
    if [[ "$GALLERY_LE_REVE" -ne 0 ]]; then
        _log "  ⚠️ Le_rêve guard failed: $GALLERY_LE_REVE records have le-reve source_url"
        GALLERY_FINAL_STATUS="FAIL"
    fi
    if [[ "$GALLERY_LEAKS" -ne 0 ]]; then
        _log "  ⚠️ local path leaks=$GALLERY_LEAKS"
        GALLERY_FINAL_STATUS="FAIL"
    fi
    if [[ "$GALLERY_MISSING" -ne 0 ]]; then
        _log "  ⚠️ missing thumbs=$GALLERY_MISSING"
        GALLERY_FINAL_STATUS="FAIL"
    fi
    if [[ "$GALLERY_SIZE_BYTES" -gt "$GALLERY_HARD_LIMIT_BYTES" ]]; then
        _log "  ⚠️ size=${GALLERY_SIZE_BYTES}B > hard limit ${GALLERY_HARD_LIMIT_BYTES}B"
        GALLERY_FINAL_STATUS="FAIL"
    fi

    if [[ "$GALLERY_FINAL_STATUS" == "PASS" ]]; then
        _log "  ✅ Gallery QA PASS"
    fi
else
    GALLERY_FINAL_STATUS="SKIP"
    _log "  (dry-run) skipped QA"
fi

# ----------------------------------------------------------------------------
# 8. QA · Digest
# ----------------------------------------------------------------------------

CURRENT_STAGE="qa_digest"
_step "QA: Digest candidate"

DIGEST_SELECTED=0
DIGEST_THUMB=0
DIGEST_LEAKS=0
DIGEST_MISSING=0
DIGEST_SIZE_BYTES=0
DIGEST_HISTORY_ENTRIES=0
DIGEST_ARCHIVE_PRESENT=0
DIGEST_FINAL_STATUS="PASS"

if [[ $DRY_RUN -eq 0 ]]; then
    read -r _ignore1 DIGEST_THUMB <<<"$(count_thumbs "$DIGEST_OUT")"
    DIGEST_SIZE_BYTES=$(dir_size_bytes "$DIGEST_OUT")

    if [[ -s "$DIGEST_OUT/data/digests.json" ]]; then
        # digests.json is a metadata summary (date/title/selected_count/...),
        # not a per-pick record. Real picks live in digest.md.
        # We trust selected_count for the count, then parse digest.md for
        # source_url uniqueness + leak check.
        mapfile -t QA_D_OUT < <("$PYTHON_BIN" - "$DIGEST_OUT" <<'PY'
import json
import re
import sys
from collections import Counter
from pathlib import Path

base = Path(sys.argv[1])
dp = base / 'data' / 'digests.json'
md = base / 'digest.md'

if not dp.is_file():
    print("NO_JSON")
    sys.exit(0)

try:
    dig = json.loads(dp.read_text(encoding='utf-8'))
except Exception as e:
    print(f"JSON_PARSE_ERROR:{e}")
    sys.exit(0)

# selected_count is the authoritative number
if isinstance(dig, list) and dig:
    latest = dig[-1]
    selected = int(latest.get('selected_count', 0) or 0)
else:
    selected = 0

# Parse digest.md for source_urls and pick headers
sus = []
picks_count = 0
if md.is_file():
    text = md.read_text(encoding='utf-8')
    picks_count = len(re.findall(r'^### \d+\. ', text, re.MULTILINE))
    sus = re.findall(r'^- 来源：\s*(\S+)', text, re.MULTILINE)

sus_counter = Counter(sus)
dupe = sum(1 for v in sus_counter.values() if v > 1)

forbidden = ['/home/', '~/', 'hermes-agent', 'metadata/', 'images/']
leaks = 0

def walk(o):
    global leaks
    if isinstance(o, dict):
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
    elif isinstance(o, str):
        for f in forbidden:
            if f in o:
                leaks += 1
                return
walk(dig)

# Also walk digest.md text for forbidden substrings (skip the literal field name)
if md.is_file():
    md_text = md.read_text(encoding='utf-8')
    for f in forbidden:
        if f in md_text:
            leaks += 1
            break

print(f"SELECTED={selected}")
print(f"PICKS_IN_MD={picks_count}")
print(f"DUPE_SOURCE_URL={dupe}")
print(f"LEAKS={leaks}")
PY
        )

        for line in "${QA_D_OUT[@]}"; do
            case "$line" in
                SELECTED=*)         DIGEST_SELECTED="${line#SELECTED=}" ;;
                LEAKS=*)            DIGEST_LEAKS="${line#LEAKS=}" ;;
                NO_JSON|JSON_PARSE_ERROR=*)
                    _log "  ⚠️ $line"
                    DIGEST_FINAL_STATUS="FAIL"
                    ;;
            esac
        done
    else
        DIGEST_FINAL_STATUS="FAIL"
        _log "  ⚠️ no data/digests.json in digest candidate"
    fi

    if [[ "$DIGEST_LEAKS" -ne 0 ]]; then
        _log "  ⚠️ digest local path leaks=$DIGEST_LEAKS"
        DIGEST_FINAL_STATUS="FAIL"
    fi
    if [[ "$DIGEST_MISSING" -ne 0 ]]; then
        _log "  ⚠️ digest missing thumbs=$DIGEST_MISSING"
        DIGEST_FINAL_STATUS="FAIL"
    fi
    if [[ "$DIGEST_THUMB" -ne "$DIGEST_SELECT_TARGET" ]]; then
        _log "  ⚠️ digest thumbs=$DIGEST_THUMB (target=$DIGEST_SELECT_TARGET)"
        # 不是 FAIL — digest build 在 nightly 阶段已经过 integrity，这里只警告
    fi

    if [[ "$DIGEST_FINAL_STATUS" == "PASS" ]]; then
        _log "  ✅ Digest QA PASS"
        # P8B + P8C: verify the archive page + archive.js +
        # digest-history.json are present and that the history has
        # at least one entry. The archive is optional (a fresh
        # clone with no history yet is allowed), but if the files
        # are present they must be parseable and not contain
        # forbidden substrings. P8C adds:
        #   - archive.js presence + sanity (must be > 1KB and
        #     reference filter-* IDs)
        #   - archive.html day-card count vs history entry count
        #   - assets/thumbs/256/ contains a thumb for at least
        #     one archive pick (else cards would all be hidden)
        if [[ -s "$DIGEST_OUT/archive.html" ]]; then
            DIGEST_ARCHIVE_PRESENT=1
            if [[ -s "$DIGEST_OUT/data/digest-history.json" ]]; then
                mapfile -t QA_D_ARCHIVE < <("$PYTHON_BIN" - "$DIGEST_OUT" <<'PY'
import json
import re
import sys
from pathlib import Path
base = Path(sys.argv[1])
hist_p = base / 'data' / 'digest-history.json'
arch_p = base / 'archive.html'
js_p   = base / 'archive.js'
thumbs256_dir = base / 'assets' / 'thumbs' / '256'

if not hist_p.is_file():
    print("MISSING_HISTORY")
    sys.exit(0)
try:
    data = json.loads(hist_p.read_text(encoding='utf-8'))
except Exception as e:
    print(f"PARSE_ERROR:{e}")
    sys.exit(0)

entries = data.get('entries', []) if isinstance(data, dict) else []
print(f"ENTRIES={len(entries)}")
print(f"HISTORY_ENTRIES={data.get('history_entries', '?')}")
print(f"SUMMARY_DAYS={data.get('summary', {}).get('total_days', '?')}")
print(f"SUMMARY_PICKS={data.get('summary', {}).get('total_picks', '?')}")
print(f"SUMMARY_ARTISTS={data.get('summary', {}).get('unique_artists', '?')}")
print(f"AVAIL_RANGE={data.get('available_range', {})}")

# Walk all string values for forbidden substrings.
forbidden = ['/home/', '~/', 'metadata/', 'images/']
leaks = 0
def walk(o):
    global leaks
    if isinstance(o, dict):
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
    elif isinstance(o, str):
        for f in forbidden:
            if f in o:
                leaks += 1
                return
walk(data)
print(f"LEAKS={leaks}")
# Sanity: digest_path must not appear in any entry.
hit_dp = any('digest_path' in (e or {}) for e in entries)
print(f"LEAKED_DIGEST_PATH={'yes' if hit_dp else 'no'}")

# Archive.html day-card count
if arch_p.is_file():
    html = arch_p.read_text(encoding='utf-8', errors='ignore')
    cards = len(re.findall(r'<section class="day-card"', html))
    print(f"DAY_CARDS={cards}")
    # P8C nav sanity
    has_latest = "Latest Digest" in html
    has_gallery = "Gallery Demo" in html
    has_release = "Release" in html or "releases/tag" in html
    has_filter_ids = all(s in html for s in [
        'id="filter-artist"', 'id="filter-category"',
        'id="filter-search"', 'id="filter-clear"',
        'id="jump-latest"',
    ])
    print(f"HAS_NAV_LATEST={'yes' if has_latest else 'no'}")
    print(f"HAS_NAV_GALLERY={'yes' if has_gallery else 'no'}")
    print(f"HAS_NAV_RELEASE={'yes' if has_release else 'no'}")
    print(f"HAS_FILTER_IDS={'yes' if has_filter_ids else 'no'}")
    # 256-thumbs presence
    if thumbs256_dir.is_dir():
        n256 = sum(1 for _ in thumbs256_dir.glob('*.jpg'))
    else:
        n256 = 0
    print(f"THUMBS_256_COUNT={n256}")
else:
    print("DAY_CARDS=0")
    print("HAS_NAV_LATEST=no")
    print("HAS_NAV_GALLERY=no")
    print("HAS_NAV_RELEASE=no")
    print("HAS_FILTER_IDS=no")
    print("THUMBS_256_COUNT=0")

# Archive.js sanity
if js_p.is_file():
    jstxt = js_p.read_text(encoding='utf-8', errors='ignore')
    print(f"ARCHIVE_JS_SIZE={len(jstxt)}")
    print(f"ARCHIVE_JS_HAS_FILTER={'yes' if 'applyFilters' in jstxt and 'populateSelect' in jstxt else 'no'}")
else:
    print("ARCHIVE_JS_SIZE=0")
    print("ARCHIVE_JS_HAS_FILTER=no")
PY
                )
                for line in "${QA_D_ARCHIVE[@]}"; do
                    case "$line" in
                        ENTRIES=*|HISTORY_ENTRIES=*|SUMMARY_*) : ;;
                        MISSING_HISTORY|PARSE_ERROR=*)
                            _log "  ⚠️ archive: $line"
                            DIGEST_FINAL_STATUS="FAIL"
                            ;;
                    esac
                done
                # Local leak in archive data
                ARCHIVE_LEAKS=$(printf '%s\n' "${QA_D_ARCHIVE[@]}" | sed -n 's/^LEAKS=//p' | head -1)
                if [[ "${ARCHIVE_LEAKS:-0}" -ne 0 ]]; then
                    _log "  ⚠️ archive local path leaks=$ARCHIVE_LEAKS"
                    DIGEST_FINAL_STATUS="FAIL"
                fi
                LEAKED_DP=$(printf '%s\n' "${QA_D_ARCHIVE[@]}" | sed -n 's/^LEAKED_DIGEST_PATH=//p' | head -1)
                if [[ "$LEAKED_DP" == "yes" ]]; then
                    _log "  ⚠️ archive still contains digest_path (should be stripped)"
                    DIGEST_FINAL_STATUS="FAIL"
                fi
                DIGEST_HISTORY_ENTRIES=$(printf '%s\n' "${QA_D_ARCHIVE[@]}" | sed -n 's/^ENTRIES=//p' | head -1)
                if [[ -z "${DIGEST_HISTORY_ENTRIES:-}" ]]; then
                    DIGEST_HISTORY_ENTRIES=0
                fi
                if [[ "$DIGEST_HISTORY_ENTRIES" -lt 1 ]]; then
                    # Empty history is allowed (fresh clone) but warn.
                    _log "  ℹ️ archive history has 0 entries (fresh clone or just enabled)"
                fi
                # P8C: day-card count vs history count
                DAY_CARDS=$(printf '%s\n' "${QA_D_ARCHIVE[@]}" | sed -n 's/^DAY_CARDS=//p' | head -1)
                if [[ "${DAY_CARDS:-0}" -ne "${DIGEST_HISTORY_ENTRIES:-0}" ]]; then
                    _log "  ⚠️ archive day-cards ($DAY_CARDS) != history entries ($DIGEST_HISTORY_ENTRIES)"
                    DIGEST_FINAL_STATUS="FAIL"
                fi
                # P8C: nav sanity
                for k in HAS_NAV_LATEST HAS_NAV_GALLERY HAS_NAV_RELEASE HAS_FILTER_IDS ARCHIVE_JS_HAS_FILTER; do
                    v=$(printf '%s\n' "${QA_D_ARCHIVE[@]}" | sed -n "s/^${k}=//p" | head -1)
                    if [[ "$v" != "yes" ]]; then
                        _log "  ⚠️ P8C archive QA missing: $k=$v"
                        DIGEST_FINAL_STATUS="FAIL"
                    fi
                done
                # P8C: archive.js size
                JS_SIZE=$(printf '%s\n' "${QA_D_ARCHIVE[@]}" | sed -n 's/^ARCHIVE_JS_SIZE=//p' | head -1)
                if [[ "${JS_SIZE:-0}" -lt 1024 ]]; then
                    _log "  ⚠️ archive.js too small: $JS_SIZE bytes"
                    DIGEST_FINAL_STATUS="FAIL"
                fi
                # P8C: 256 thumbs present
                T256=$(printf '%s\n' "${QA_D_ARCHIVE[@]}" | sed -n 's/^THUMBS_256_COUNT=//p' | head -1)
                if [[ "${T256:-0}" -lt 1 ]]; then
                    _log "  ℹ️ archive 256-thumbs=0 (all cards will hide image — check digest picks have 256 variants)"
                else
                    _log "  ℹ️ archive 256-thumbs=$T256"
                fi
            else
                _log "  ℹ️ archive.html present but no data/digest-history.json"
            fi
        else
            _log "  ℹ️ archive.html not present (P8B archive disabled or no history yet)"
        fi
    fi
else
    DIGEST_FINAL_STATUS="SKIP"
    _log "  (dry-run) skipped QA"
fi

# ----------------------------------------------------------------------------
# 9. Overall status & report
# ----------------------------------------------------------------------------

CURRENT_STAGE="finalize"
OVERALL="PASS"
if [[ "$GALLERY_FINAL_STATUS" != "PASS" && "$GALLERY_FINAL_STATUS" != "SKIP" ]]; then
    OVERALL="FAIL"
fi
# P8B: digest size budget (5MB soft / 10MB hard). A digest bundle
# is text + 1-5 thumbs; if it ever grows past 10MB something has
# gone wrong (a full image slipped in, or 1000 picks were exported
# by mistake). Soft is a warning, hard is a FAIL.
if [[ $DRY_RUN -eq 0 ]]; then
    if [[ "$DIGEST_SIZE_BYTES" -gt "$DIGEST_HARD_LIMIT_BYTES" ]]; then
        _log "  ⚠️ digest size=${DIGEST_SIZE_BYTES}B > hard limit ${DIGEST_HARD_LIMIT_BYTES}B"
        DIGEST_FINAL_STATUS="FAIL"
    elif [[ "$DIGEST_SIZE_BYTES" -gt "$DIGEST_SOFT_LIMIT_BYTES" ]]; then
        _log "  ⚠️ digest size=${DIGEST_SIZE_BYTES}B > soft limit ${DIGEST_SOFT_LIMIT_BYTES}B"
    fi
fi
if [[ "$DIGEST_FINAL_STATUS" != "PASS" && "$DIGEST_FINAL_STATUS" != "SKIP" ]]; then
    OVERALL="FAIL"
fi

# 格式化尺寸
fmt_bytes() {
    local b="$1"
    if [[ -z "$b" || "$b" -eq 0 ]]; then
        echo "0"
        return
    fi
    awk -v b="$b" 'BEGIN {
        if (b >= 1048576) printf "%.1fM", b/1048576
        else if (b >= 1024) printf "%.0fK", b/1024
        else printf "%dB", b
    }'
}

GALLERY_SIZE_HUMAN="$(fmt_bytes "$GALLERY_SIZE_BYTES")"
DIGEST_SIZE_HUMAN="$(fmt_bytes "$DIGEST_SIZE_BYTES")"
GALLERY_LARGEST_HUMAN="$(fmt_bytes "${GALLERY_LARGEST:-0}")"

if [[ $DRY_RUN -eq 0 ]]; then
    {
        echo "# Artvee Demo Refresh Candidate · $DATE"
        echo
        echo "**Overall status:** $OVERALL"
        echo
        echo "## Gallery candidate"
        echo
        echo "| Field | Value |"
        echo "| --- | --- |"
        echo "| Path | \`$GALLERY_OUT\` |"
        echo "| Records | $GALLERY_RECORDS (target: $GALLERY_RECORD_TARGET) |"
        echo "| Thumbs (256) | $GALLERY_THUMB_256 |"
        echo "| Thumbs (512) | $GALLERY_THUMB_512 |"
        echo "| Size | $GALLERY_SIZE_HUMAN ($GALLERY_SIZE_BYTES bytes) |"
        echo "| Largest file | $GALLERY_LARGEST_HUMAN |"
        echo "| Duplicate id groups | $GALLERY_DUPE_ID |"
        echo "| Duplicate source_url groups | $GALLERY_DUPE_SOURCE_URL |"
        echo "| Le_rêve records | $GALLERY_LE_REVE (guard: =0) |"
        echo "| Local path leaks | $GALLERY_LEAKS |"
        echo "| Missing thumbs | $GALLERY_MISSING |"
        echo "| Final status | $GALLERY_FINAL_STATUS |"
        echo
        echo "## Digest candidate"
        echo
        echo "| Field | Value |"
        echo "| --- | --- |"
        echo "| Path | \`$DIGEST_OUT\` |"
        echo "| Selected | $DIGEST_SELECTED (target: $DIGEST_SELECT_TARGET) |"
        echo "| Thumbs | $DIGEST_THUMB |"
        echo "| Size | $DIGEST_SIZE_HUMAN ($DIGEST_SIZE_BYTES bytes) |"
        echo "| Archive (P8B+P8C) | archive.html=$([ "$DIGEST_ARCHIVE_PRESENT" = "1" ] && echo "yes" || echo "no"), history_entries=$DIGEST_HISTORY_ENTRIES, day_cards=$DAY_CARDS, thumbs_256=$T256 |"
        echo "| Local path leaks | $DIGEST_LEAKS |"
        echo "| Missing thumbs | $DIGEST_MISSING |"
        echo "| Final status | $DIGEST_FINAL_STATUS |"
        echo
        echo "## Publish status"
        echo
        echo "**Publish: NOT PUSHED, manual approval required.**"
        echo
        echo "To publish this candidate, run manually:"
        echo
        echo '```bash'
        echo "rsync -a --delete $GALLERY_OUT/ \\"
        echo "    $PAGES_REPO/projects/artvee-gallery-demo/"
        echo "rsync -a --delete $DIGEST_OUT/ \\"
        echo "    $PAGES_REPO/projects/artvee-gallery-digest/"
        echo "cd \"\\\$PAGES_REPO\" && \\"
        echo "    git add projects/artvee-gallery-{demo,digest} projects/data.json && \\"
        echo "    git commit -m 'Refresh artvee public demo for $DATE' && \\"
        echo "    git push"
        echo '```'
        echo
        echo "## Run log"
        echo
        echo "\`$RUN_LOG\`"
        echo
        echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    } > "$REPORT"
    _log "  ✅ report written: $REPORT"
else
    _log "  (dry-run) would write report to $REPORT"
fi

# ----------------------------------------------------------------------------
# 10. Telegram summary
# ----------------------------------------------------------------------------

if [[ $DRY_RUN -eq 0 ]]; then
    if [[ $NO_TELEGRAM -eq 1 ]]; then
        _log "  ⏭️  Telegram skipped (--no-telegram)"
    else
        if [[ -f "$TELEGRAM_NOTIFIER" ]]; then
            TELEGRAM_MSG=""
            # P6G: compute known_retired / blocking_unresolved split
            # from the runtime manifest if present, else fallback.
            KNOWN_RETIRED_COUNT=0
            BLOCKING_UNRESOLVED=0
            if [[ -f "$BASE_DIR/reports/runtime/p6b-known-retired-urls.json" ]]; then
                KNOWN_RETIRED_COUNT="$("$PYTHON_BIN" -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("records", [])))' "$BASE_DIR/reports/runtime/p6b-known-retired-urls.json" 2>/dev/null || echo 0)"
            else
                UNRESOLVED_FILE="$BASE_DIR/reports/runtime/p5a-unresolved-losers.json"
                [[ ! -f "$UNRESOLVED_FILE" ]] && UNRESOLVED_FILE="$BASE_DIR/reports/runtime/p4b-unresolved-losers.json"
                if [[ -f "$UNRESOLVED_FILE" ]]; then
                    BLOCKING_UNRESOLVED="$("$PYTHON_BIN" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d) if isinstance(d, list) else len(d.get("records", [])))' "$UNRESOLVED_FILE" 2>/dev/null || echo 0)"
                fi
            fi
            RETIRED_LINE="Retired sources: $KNOWN_RETIRED_COUNT known_retired, blocking_unresolved=$BLOCKING_UNRESOLVED"
            if [[ "$OVERALL" == "PASS" ]]; then
                TELEGRAM_MSG="✅ Artvee Demo Refresh Candidate
日期: $DATE
Gallery: PASS, records=$GALLERY_RECORDS, thumbs=$((GALLERY_THUMB_256+GALLERY_THUMB_512)), size=$GALLERY_SIZE_HUMAN
Digest: PASS, selected=$DIGEST_SELECTED, thumbs=$DIGEST_THUMB, size=$DIGEST_SIZE_HUMAN, archive_entries=$DIGEST_HISTORY_ENTRIES
Guards: duplicate_source_url=$GALLERY_DUPE_SOURCE_URL, Le_rêve=$GALLERY_LE_REVE, leaks=$((GALLERY_LEAKS+DIGEST_LEAKS)), missing=$((GALLERY_MISSING+DIGEST_MISSING))
$RETIRED_LINE
Publish: not pushed, manual approval required
Path: dist/refresh-candidates/$DATE/"
            else
                TELEGRAM_MSG="❌ Artvee Demo Refresh Candidate
日期: $DATE
失败阶段: ${FAIL_STAGE:-qa}
原因: ${FAIL_REASON:-gallery=$GALLERY_FINAL_STATUS digest=$DIGEST_FINAL_STATUS}
Publish: skipped"
            fi
            # notifier 自己处理后台 / 错误
            if "$PYTHON_BIN" "$TELEGRAM_NOTIFIER" --text "$TELEGRAM_MSG" >> "$RUN_LOG" 2>&1; then
                _log "  ✅ telegram sent"
            else
                _log "  ⚠️ telegram notify failed (continuing); see $RUN_LOG"
            fi
        else
            _log "  ⚠️ telegram notifier missing at $TELEGRAM_NOTIFIER (continuing)"
        fi
    fi
else
    _log "  (dry-run) telegram skipped"
fi

# ----------------------------------------------------------------------------
# 11. Exit
# ----------------------------------------------------------------------------

if [[ "$OVERALL" == "PASS" ]]; then
    _log "===== confirm_demo_refresh PASS ====="
    exit 0
else
    _log "===== confirm_demo_refresh FAIL ====="
    exit 1
fi
