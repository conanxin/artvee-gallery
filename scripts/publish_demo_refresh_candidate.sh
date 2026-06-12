#!/usr/bin/env bash
#
# publish_demo_refresh_candidate.sh · P4E
#
# 用途：显式批准后，把 confirm_demo_refresh.sh 生成的候选包
#      发布到 GitHub Pages 的 publish helper。
#
# 安全规则：
#   - 没有 --approve 时：永不 rsync、永不 commit、永不 push
#   - 有 --approve --no-push 时：rsync + commit，但不 push
#   - 有 --approve 时：rsync + commit + push + 在线验证
#   - 任何 QA 失败时：停止，不执行任何写操作
#
# 输出：
#   - dist/refresh-candidates/ 保持不变（只读）
#   - Pages repo 被写入（rsync + git commit + git push）
#   - 报告：logs/confirm_demo_refresh/publish_YYYY-MM-DD.md
#
# 用法：
#   bash scripts/publish_demo_refresh_candidate.sh --dry-run
#   bash scripts/publish_demo_refresh_candidate.sh --date 2026-06-12 --dry-run
#   bash scripts/publish_demo_refresh_candidate.sh --date 2026-06-12 --approve --no-push
#   bash scripts/publish_demo_refresh_candidate.sh --date 2026-06-12 --approve
#   bash scripts/publish_demo_refresh_candidate.sh --pages-repo <pages-repo> --date 2026-06-12 --dry-run
#
# 不变量：
#   - 不触发任何 Artvee 下载 / refill / batch
#   - 不修改 manifest / index / images / metadata / thumbs / web/data
#   - 不提交 runtime data 到 Artvee repo
#   - 不默认推 GitHub Pages
#

set -euo pipefail

# ----------------------------------------------------------------------------
# 参数解析
# ----------------------------------------------------------------------------

DATE="$(date '+%Y-%m-%d')"
DRY_RUN=0
APPROVE=0
NO_PUSH=0
PAGES_REPO=""
BASE_DIR=""
PYTHON_BIN="${ARTVEE_PYTHON:-python3}"

print_help() {
    cat <<'USAGE'
用法：bash scripts/publish_demo_refresh_candidate.sh [options]

选项：
  --date YYYY-MM-DD     指定候选日期（默认今天）
  --dry-run             只打印计划，不 rsync、不 commit、不 push
  --approve             启用真实发布（无此标志时只做 dry-run/验证）
  --no-push             与 --approve 同时使用时：rsync + commit，但不 push
  --pages-repo PATH     指定 Pages repo 路径（默认自动推导）
  --help                显示此帮助

安全规则：
  无 --approve          → 永不 rsync / commit / push
  --approve --no-push   → rsync + commit，不 push
  --approve             → rsync + commit + push + 在线验证
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
        --approve)
            APPROVE=1
            shift
            ;;
        --no-push)
            NO_PUSH=1
            shift
            ;;
        --pages-repo)
            PAGES_REPO="$2"
            shift 2
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

if ! [[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR: --date must be YYYY-MM-DD, got: $DATE" >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# 路径与目录
# ----------------------------------------------------------------------------

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANDIDATE_BASE="$BASE_DIR/dist/refresh-candidates"
GALLERY_CANDIDATE="$CANDIDATE_BASE/$DATE/gallery"
DIGEST_CANDIDATE="$CANDIDATE_BASE/$DATE/digest"

# 自动推导 Pages repo（如果未指定）
if [[ -z "$PAGES_REPO" ]]; then
    # 尝试从 HOME 推导
    if [[ -d "$HOME/conanxin.github.io" ]]; then
        PAGES_REPO="$HOME/conanxin.github.io"
    else
        echo "ERROR: cannot auto-detect Pages repo. Please use --pages-repo PATH" >&2
        exit 1
    fi
fi

PAGES_REPO="$(cd "$PAGES_REPO" && pwd)"
GALLERY_PAGES_DIR="$PAGES_REPO/projects/artvee-gallery-demo"
DIGEST_PAGES_DIR="$PAGES_REPO/projects/artvee-gallery-digest"
DATA_JSON="$PAGES_REPO/projects/data.json"

LOG_DIR="$BASE_DIR/logs/confirm_demo_refresh"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_LOG="$LOG_DIR/publish_${TIMESTAMP}.log"
REPORT="$LOG_DIR/publish_${DATE}.md"

mkdir -p "$LOG_DIR"
: > "$RUN_LOG"

# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------

_log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$RUN_LOG"
}

_step() {
    _log "===== STEP: $1 ====="
}

CURRENT_STAGE="init"
FAIL_STAGE=""
FAIL_REASON=""

_record_fail() {
    FAIL_STAGE="$CURRENT_STAGE"
    FAIL_REASON="$1"
    _log "FAILED at $CURRENT_STAGE: $1"
}

dir_size_human() {
    du -sh "$1" 2>/dev/null | awk '{print $1}' || echo "0"
}

_finalize_and_exit() {
    local exit_code="${1:-1}"
    if [[ -f "$RUN_LOG" ]]; then
        _log "===== publish_demo_refresh_candidate exit $exit_code ====="
    fi
    exit "$exit_code"
}

# 在线验证辅助
_curl_head() {
    local url="$1"
    local max_wait=2
    curl -sI -o /dev/null -w "%{http_code}" --max-time "$max_wait" "$url" 2>/dev/null || echo "000"
}

# 等待 CDN 后重试
wait_and_curl() {
    local url="$1"
    local code
    code="$(_curl_head "$url")"
    if [[ "$code" == "200" ]]; then
        echo "200"
        return 0
    fi
    _log "  CDN not ready (code=$code), wait 60s..."
    sleep 60
    code="$(_curl_head "$url")"
    echo "$code"
}

# ----------------------------------------------------------------------------
# 1. 检查候选目录存在
# ----------------------------------------------------------------------------

CURRENT_STAGE="candidate_exists"
_step "Check candidate directories exist"

if [[ ! -d "$GALLERY_CANDIDATE" ]]; then
    _record_fail "Gallery candidate missing: $GALLERY_CANDIDATE"
    _finalize_and_exit 1
fi
if [[ ! -d "$DIGEST_CANDIDATE" ]]; then
    _record_fail "Digest candidate missing: $DIGEST_CANDIDATE"
    _finalize_and_exit 1
fi

_log "  ✅ Gallery candidate: $GALLERY_CANDIDATE"
_log "  ✅ Digest candidate:  $DIGEST_CANDIDATE"

# ----------------------------------------------------------------------------
# 2. QA Gallery candidate
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
GALLERY_HAS_METADATA_PATH=0

if [[ -s "$GALLERY_CANDIDATE/data/artworks.json" ]]; then
    mapfile -t QA_OUTPUT < <("$PYTHON_BIN" - "$GALLERY_CANDIDATE" <<'PY'
import json, sys, os
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

forbidden = ['/home/', '~/', 'hermes-agent', 'metadata/', 'images/']
leaks = 0
has_metadata_path = 0
for a in arts:
    if a.get('metadata_path'):
        has_metadata_path = 1
    for k, v in a.items():
        if not isinstance(v, str):
            continue
        for f in forbidden:
            if f in v:
                leaks += 1
                break

le_reve = sum(1 for s in sus_clean if 'le-reve' in s)

missing = 0
for a in arts:
    for tk in ('thumb_256', 'thumb_512'):
        rel = a.get(tk, '')
        if not rel:
            missing += 1
            continue
        rp = rel.lstrip('./')
        p = base / rp
        if not p.is_file():
            missing += 1

largest = 0
for f in base.rglob('*'):
    if f.is_file() and f.stat().st_size > largest:
        largest = f.stat().st_size

print(f"RECORDS={records}")
print(f"DUPE_ID_GROUPS={dupe_id_groups}")
print(f"DUPE_SOURCE_URL_GROUPS={dupe_sus_groups}")
print(f"LE_REVE={le_reve}")
print(f"LEAKS={leaks}")
print(f"MISSING={missing}")
print(f"LARGEST={largest}")
print(f"HAS_METADATA_PATH={has_metadata_path}")
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
            LARGEST=*)            GALLERY_LARGEST="${line#LARGEST=}" ;;
            HAS_METADATA_PATH=*)  GALLERY_HAS_METADATA_PATH="${line#HAS_METADATA_PATH=}" ;;
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

GALLERY_SIZE_BYTES=$(du -sb "$GALLERY_CANDIDATE" 2>/dev/null | awk '{print $1}' || echo 0)
GALLERY_SIZE_HUMAN="$(dir_size_human "$GALLERY_CANDIDATE")"

if [[ "$GALLERY_RECORDS" -le 0 ]]; then
    _log "  ⚠️ records=$GALLERY_RECORDS (must be > 0)"
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
    _log "  ⚠️ Le_rêve guard failed: $GALLERY_LE_REVE records"
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
if [[ "$GALLERY_HAS_METADATA_PATH" -ne 0 ]]; then
    _log "  ⚠️ metadata_path still present in public JSON"
    GALLERY_FINAL_STATUS="FAIL"
fi
if [[ "$GALLERY_SIZE_BYTES" -gt 20971520 ]]; then
    _log "  ⚠️ size=${GALLERY_SIZE_BYTES}B > 20MB hard limit"
    GALLERY_FINAL_STATUS="FAIL"
fi

if [[ "$GALLERY_FINAL_STATUS" == "PASS" ]]; then
    _log "  ✅ Gallery QA PASS"
fi

# ----------------------------------------------------------------------------
# 3. QA Digest candidate
# ----------------------------------------------------------------------------

CURRENT_STAGE="qa_digest"
_step "QA: Digest candidate"

DIGEST_SELECTED=0
DIGEST_THUMB=0
DIGEST_LEAKS=0
DIGEST_MISSING=0
DIGEST_SIZE_BYTES=0
DIGEST_FINAL_STATUS="PASS"

if [[ -s "$DIGEST_CANDIDATE/data/digests.json" ]]; then
    mapfile -t QA_D_OUT < <("$PYTHON_BIN" - "$DIGEST_CANDIDATE" <<'PY'
import json, re, sys
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

if isinstance(dig, list) and dig:
    latest = dig[-1]
    selected = int(latest.get('selected_count', 0) or 0)
else:
    selected = 0

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

DIGEST_SIZE_BYTES=$(du -sb "$DIGEST_CANDIDATE" 2>/dev/null | awk '{print $1}' || echo 0)
DIGEST_SIZE_HUMAN="$(dir_size_human "$DIGEST_CANDIDATE")"

if [[ "$DIGEST_LEAKS" -ne 0 ]]; then
    _log "  ⚠️ digest local path leaks=$DIGEST_LEAKS"
    DIGEST_FINAL_STATUS="FAIL"
fi
if [[ "$DIGEST_SIZE_BYTES" -gt 5242880 ]]; then
    _log "  ⚠️ digest size=${DIGEST_SIZE_BYTES}B > 5MB soft limit"
    DIGEST_FINAL_STATUS="FAIL"
fi

if [[ "$DIGEST_FINAL_STATUS" == "PASS" ]]; then
    _log "  ✅ Digest QA PASS"
fi

# ----------------------------------------------------------------------------
# 4. 检查 Pages repo 干净
# ----------------------------------------------------------------------------

CURRENT_STAGE="pages_repo_check"
_step "Check Pages repo state"

if [[ ! -d "$PAGES_REPO/.git" ]]; then
    _record_fail "Pages repo is not a git repo: $PAGES_REPO"
    _finalize_and_exit 1
fi

PAGES_BRANCH="$(cd "$PAGES_REPO" && git branch --show-current 2>/dev/null)"
PAGES_DIRTY="$(cd "$PAGES_REPO" && git status --short 2>/dev/null)"

_log "  Pages repo: $PAGES_REPO"
_log "  Branch: $PAGES_BRANCH"
if [[ -n "$PAGES_DIRTY" ]]; then
    _log "  ⚠️ Pages repo has uncommitted changes:"
    echo "$PAGES_DIRTY" | while read -r line; do _log "    $line"; done
else
    _log "  ✅ Pages repo clean"
fi

# ----------------------------------------------------------------------------
# 5. data.json 检查（只读）
# ----------------------------------------------------------------------------

CURRENT_STAGE="data_json_check"
_step "Check projects/data.json"

DATA_JSON_HAS_ENTRIES=0
DATA_JSON_OK=1

if [[ -f "$DATA_JSON" ]]; then
    mapfile -t DJ_OUT < <("$PYTHON_BIN" - "$DATA_JSON" <<'PY'
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
if not p.is_file():
    print("MISSING")
    sys.exit(0)

try:
    data = json.loads(p.read_text(encoding='utf-8'))
except Exception as e:
    print(f"PARSE_ERROR:{e}")
    sys.exit(0)

if not isinstance(data, list):
    print("NOT_A_LIST")
    sys.exit(0)

has_gallery = any('artvee-gallery-demo' in str(e.get('slug','')) for e in data)
has_digest = any('artvee-gallery-digest' in str(e.get('slug','')) for e in data)
print(f"HAS_GALLERY={int(has_gallery)}")
print(f"HAS_DIGEST={int(has_digest)}")
print(f"ENTRIES={len(data)}")
PY
    )

    for line in "${DJ_OUT[@]}"; do
        case "$line" in
            HAS_GALLERY=*) DATA_JSON_HAS_GALLERY="${line#HAS_GALLERY=}" ;;
            HAS_DIGEST=*)  DATA_JSON_HAS_DIGEST="${line#HAS_DIGEST=}" ;;
            MISSING|PARSE_ERROR=*|NOT_A_LIST)
                _log "  ⚠️ $line"
                DATA_JSON_OK=0
                ;;
        esac
    done
else
    _log "  ⚠️ data.json missing at $DATA_JSON"
    DATA_JSON_OK=0
fi

if [[ "$DATA_JSON_OK" == 1 ]]; then
    _log "  ✅ data.json has gallery=$DATA_JSON_HAS_GALLERY digest=$DATA_JSON_HAS_DIGEST"
fi

# ----------------------------------------------------------------------------
# 6. 计算计划操作
# ----------------------------------------------------------------------------

CURRENT_STAGE="plan"
_step "Plan operations"

OVERALL="PASS"
if [[ "$GALLERY_FINAL_STATUS" != "PASS" ]]; then
    OVERALL="FAIL"
fi
if [[ "$DIGEST_FINAL_STATUS" != "PASS" ]]; then
    OVERALL="FAIL"
fi
if [[ "$DATA_JSON_OK" == 0 ]]; then
    OVERALL="FAIL"
    _record_fail "data.json validation failed"
fi

_log "  Overall QA status: $OVERALL"

if [[ "$OVERALL" != "PASS" ]]; then
    _log "  ❌ Publish blocked: QA failed. No files touched."
    _finalize_and_exit 1
fi

# 安全门：没有 --approve 时只做 dry-run
if [[ "$APPROVE" -eq 0 ]]; then
    DRY_RUN=1
    _log "  ⏸️  No --approve: operating in dry-run mode (no rsync / commit / push)"
fi

# 计算 git diff 预览（仅 dry-run / approve 前）
PLAN_GALLERY_DIFF=""
PLAN_DIGEST_DIFF=""
if command -v diff >/dev/null 2>&1 && [[ -d "$GALLERY_PAGES_DIR" ]]; then
    PLAN_GALLERY_DIFF="$(diff -rq "$GALLERY_CANDIDATE" "$GALLERY_PAGES_DIR" 2>/dev/null | head -20 || true)"
fi
if command -v diff >/dev/null 2>&1 && [[ -d "$DIGEST_PAGES_DIR" ]]; then
    PLAN_DIGEST_DIFF="$(diff -rq "$DIGEST_CANDIDATE" "$DIGEST_PAGES_DIR" 2>/dev/null | head -20 || true)"
fi

_log "  Plan:"
_log "    Gallery candidate  → $GALLERY_PAGES_DIR"
_log "    Digest candidate   → $DIGEST_PAGES_DIR"
_log "    data.json          → update 'updated' + summary"
_log "    Pages commit msg   → Refresh Artvee public demos from approved candidate $DATE"

# ----------------------------------------------------------------------------
# 7. 执行 rsync（如果 approve）
# ----------------------------------------------------------------------------

CURRENT_STAGE="rsync"
_step "Rsync candidates to Pages repo"

if [[ "$DRY_RUN" -eq 1 ]]; then
    _log "  (dry-run) would rsync:"
    _log "    rsync -a --delete $GALLERY_CANDIDATE/ $GALLERY_PAGES_DIR/"
    _log "    rsync -a --delete $DIGEST_CANDIDATE/ $DIGEST_PAGES_DIR/"
else
    mkdir -p "$GALLERY_PAGES_DIR" "$DIGEST_PAGES_DIR"
    rsync -a --delete "$GALLERY_CANDIDATE/" "$GALLERY_PAGES_DIR/"
    _log "  ✅ Gallery rsync done"
    rsync -a --delete "$DIGEST_CANDIDATE/" "$DIGEST_PAGES_DIR/"
    _log "  ✅ Digest rsync done"
fi

# ----------------------------------------------------------------------------
# 8. 更新 data.json（如果 approve）
# ----------------------------------------------------------------------------

CURRENT_STAGE="data_json_update"
_step "Update data.json"

if [[ "$DRY_RUN" -eq 1 ]]; then
    _log "  (dry-run) would update $DATA_JSON"
else
    "$PYTHON_BIN" - "$DATA_JSON" "$DATE" <<'PY'
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
date = sys.argv[2]

try:
    data = json.loads(p.read_text(encoding='utf-8'))
except Exception:
    data = []

if not isinstance(data, list):
    data = []

# find gallery + digest entries
found_gallery = False
found_digest = False
for e in data:
    slug = e.get('slug', '') or e.get('title', '')
    if 'artvee-gallery-demo' in str(slug):
        e['updated'] = date
        e['status'] = 'active'
        e['summary'] = f'Artvee Gallery demo · refreshed {date}'
        found_gallery = True
    if 'artvee-gallery-digest' in str(slug):
        e['updated'] = date
        e['status'] = 'active'
        e['summary'] = f'Artvee daily digest · refreshed {date}'
        found_digest = True

# 如果条目不存在，不自动添加（避免 schema 不匹配）
if not found_gallery:
    print("WARN: gallery entry not found in data.json", file=sys.stderr)
if not found_digest:
    print("WARN: digest entry not found in data.json", file=sys.stderr)

p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
PY
    _log "  ✅ data.json updated"
fi

# ----------------------------------------------------------------------------
# 9. Git commit（如果 approve）
# ----------------------------------------------------------------------------

CURRENT_STAGE="git_commit"
_step "Git commit in Pages repo"

COMMIT_MSG="Refresh Artvee public demos from approved candidate $DATE"

if [[ "$DRY_RUN" -eq 1 ]]; then
    _log "  (dry-run) would commit:"
    _log "    cd $PAGES_REPO"
    _log "    git add projects/artvee-gallery-demo projects/artvee-gallery-digest projects/data.json"
    _log "    git commit -m '$COMMIT_MSG'"
else
    cd "$PAGES_REPO"
    # 检查是否有变化
    if git diff --cached --quiet && git diff --quiet; then
        _log "  ⏭️  No changes to publish (candidate identical to current Pages)"
        COMMIT_RESULT="no-changes"
    else
        git add projects/artvee-gallery-demo projects/artvee-gallery-digest projects/data.json
        if git diff --cached --quiet; then
            _log "  ⏭️  No staged changes after add (already identical)"
            COMMIT_RESULT="no-changes"
        else
            git commit -m "$COMMIT_MSG"
            COMMIT_HASH="$(git rev-parse --short HEAD)"
            _log "  ✅ Pages commit: $COMMIT_HASH"
            COMMIT_RESULT="committed"
        fi
    fi
fi

# ----------------------------------------------------------------------------
# 10. Git push（如果 approve 且不是 --no-push）
# ----------------------------------------------------------------------------

CURRENT_STAGE="git_push"
_step "Git push to Pages repo"

if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ "$NO_PUSH" -eq 1 ]]; then
        _log "  (dry-run) --no-push: commit only, no push"
    else
        _log "  (dry-run) would push: git push origin $PAGES_BRANCH"
    fi
    PUSH_RESULT="dry-run"
elif [[ "$NO_PUSH" -eq 1 ]]; then
    _log "  ⏭️  --no-push: commit done, push skipped"
    PUSH_RESULT="no-push"
else
    if [[ "${COMMIT_RESULT:-}" == "no-changes" ]]; then
        _log "  ⏭️  No changes, push skipped"
        PUSH_RESULT="no-changes"
    else
        cd "$PAGES_REPO"
        git push
        PUSH_RESULT="pushed"
        _log "  ✅ Pushed to Pages repo"
    fi
fi

# ----------------------------------------------------------------------------
# 11. 在线验证（如果 approve 且已 push）
# ----------------------------------------------------------------------------

CURRENT_STAGE="online_verify"
_step "Online verification"

ONLINE_STATUS="skipped"
ENDPOINTS_OK=0
ENDPOINTS_TOTAL=0

if [[ "$DRY_RUN" -eq 1 || "$NO_PUSH" -eq 1 || "${COMMIT_RESULT:-}" == "no-changes" ]]; then
    _log "  ⏭️  Online verification skipped (dry-run / no-push / no-changes)"
else
    # 等待 CDN
    _log "  Wait 60s for CDN..."
    sleep 60

    ENDPOINTS=(
        "https://conanxin.github.io/projects/artvee-gallery-demo/"
        "https://conanxin.github.io/projects/artvee-gallery-demo/data/artworks.json"
        "https://conanxin.github.io/projects/artvee-gallery-demo/data/gallery_stats.json"
        "https://conanxin.github.io/projects/artvee-gallery-demo/app.js"
        "https://conanxin.github.io/projects/artvee-gallery-demo/style.css"
        "https://conanxin.github.io/projects/artvee-gallery-digest/"
        "https://conanxin.github.io/projects/artvee-gallery-digest/digest.html"
        "https://conanxin.github.io/projects/artvee-gallery-digest/digest.md"
        "https://conanxin.github.io/projects/artvee-gallery-digest/data/digests.json"
    )

    ENDPOINTS_OK=0
    ENDPOINTS_TOTAL=${#ENDPOINTS[@]}
    for url in "${ENDPOINTS[@]}"; do
        code="$(wait_and_curl "$url")"
        if [[ "$code" == "200" ]]; then
            _log "  ✅ $url → 200"
            ((ENDPOINTS_OK++))
        else
            _log "  ❌ $url → $code"
        fi
    done

    # 抽查 thumbs
    # 从 candidate JSON 中读取随机 thumb 路径进行测试
    SAMPLE_THUMB=""
    if [[ -s "$GALLERY_CANDIDATE/data/artworks.json" ]]; then
        SAMPLE_THUMB="$("$PYTHON_BIN" -c "
import json, random
arts = json.load(open('$GALLERY_CANDIDATE/data/artworks.json'))
if arts:
    a = random.choice(arts)
    print('https://conanxin.github.io/projects/artvee-gallery-demo/' + a.get('thumb_256','').lstrip('./'))
")"
    fi
    if [[ -n "$SAMPLE_THUMB" ]]; then
        code="$(wait_and_curl "$SAMPLE_THUMB")"
        if [[ "$code" == "200" ]]; then
            _log "  ✅ Sample thumb 256 → 200"
            ((ENDPOINTS_OK++))
        else
            _log "  ❌ Sample thumb 256 → $code"
        fi
        ((ENDPOINTS_TOTAL++))
    fi

    if [[ "$ENDPOINTS_OK" -eq "$ENDPOINTS_TOTAL" ]]; then
        ONLINE_STATUS="PASS"
        _log "  ✅ All $ENDPOINTS_TOTAL endpoints online"
    else
        ONLINE_STATUS="FAIL"
        _log "  ⚠️ $ENDPOINTS_OK / $ENDPOINTS_TOTAL endpoints OK"
    fi
fi

# ----------------------------------------------------------------------------
# 12. 报告
# ----------------------------------------------------------------------------

CURRENT_STAGE="write_report"
_step "Write report"

{
    echo "# Artvee Demo Publish Report · $DATE"
    echo
    echo "**Overall status:** $OVERALL"
    echo
    echo "## Candidate"
    echo
    echo "| Field | Value |"
    echo "| --- | --- |"
    echo "| Gallery candidate | \`$GALLERY_CANDIDATE\` |"
    echo "| Digest candidate  | \`$DIGEST_CANDIDATE\` |"
    echo "| Gallery records   | $GALLERY_RECORDS |"
    echo "| Gallery size      | $GALLERY_SIZE_HUMAN |"
    echo "| Digest selected   | $DIGEST_SELECTED |"
    echo "| Digest size       | $DIGEST_SIZE_HUMAN |"
    echo
    echo "## QA"
    echo
    echo "| Check | Status |"
    echo "| --- | --- |"
    echo "| Gallery QA | $GALLERY_FINAL_STATUS |"
    echo "| Digest QA  | $DIGEST_FINAL_STATUS |"
    echo "| data.json  | $([[ \$DATA_JSON_OK == 1 ]] && echo OK || echo FAIL) |"
    echo
    echo "## Publish action"
    echo
    echo "| Step | Status |"
    echo "| --- | --- |"
    echo "| --approve | $([[ \$APPROVE == 1 ]] && echo yes || echo no) |"
    echo "| --no-push | $([[ \$NO_PUSH == 1 ]] && echo yes || echo no) |"
    echo "| rsync     | $([[ \$DRY_RUN == 0 && \$APPROVE == 1 ]] && echo done || echo skipped) |"
    echo "| commit    | ${COMMIT_RESULT:-skipped} |"
    echo "| push      | ${PUSH_RESULT:-skipped} |"
    echo "| online    | ${ONLINE_STATUS:-skipped} |"
    echo
    if [[ "$APPROVE" -eq 0 ]]; then
        echo "## To publish this candidate"
        echo
        echo '```bash'
        echo "bash scripts/publish_demo_refresh_candidate.sh --date $DATE --approve"
        echo '```'
        echo
        echo "Or with --no-push to commit only:"
        echo
        echo '```bash'
        echo "bash scripts/publish_demo_refresh_candidate.sh --date $DATE --approve --no-push"
        echo '```'
    fi
    echo
    echo "## Run log"
    echo
    echo "\`$RUN_LOG\`"
    echo
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
} > "$REPORT"

_log "  ✅ Report written: $REPORT"

# ----------------------------------------------------------------------------
# 13. Exit
# ----------------------------------------------------------------------------

if [[ "$OVERALL" == "PASS" ]]; then
    _log "===== publish_demo_refresh_candidate PASS ====="
    exit 0
else
    _log "===== publish_demo_refresh_candidate FAIL ====="
    exit 1
fi
