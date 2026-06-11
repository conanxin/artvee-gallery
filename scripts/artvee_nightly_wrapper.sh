#!/usr/bin/env bash
set -euo pipefail

# Artvee Nightly Wrapper
# 支持三种模式: refill | batch | test
# 执行后自动发送 Telegram 汇报（通过 OpenClaw Gateway 后台发送）

BASE_DIR="$HOME/hermes-agent/project/artvee-library"
PYTHON="$HOME/hermes-agent/.venv/bin/python"
NOTIFIER="$BASE_DIR/scripts/artvee_telegram_notify.py"
RUN_TYPE="${1:-batch}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

LOG_DIR="$BASE_DIR/logs"
WRAPPER_LOG_DIR="$LOG_DIR/wrapper_runs"
mkdir -p "$WRAPPER_LOG_DIR"

RUN_LOG="$WRAPPER_LOG_DIR/wrapper_${RUN_TYPE}_${TIMESTAMP}.log"

# 辅助函数
log_wrapper() {
    local line="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$line"
    echo "$line" >> "$RUN_LOG"
}

count_images() {
    find "$BASE_DIR/images" -type f 2>/dev/null | wc -l
}

count_metadata() {
    find "$BASE_DIR/metadata" -type f -iname '*.json' 2>/dev/null | wc -l
}

dir_size() {
    du -sh "$BASE_DIR" 2>/dev/null | cut -f1
}

send_telegram() {
    local msg="$1"
    log_wrapper "Sending Telegram notification (background via OpenClaw Gateway)..."
    if "$NOTIFIER" --text "$msg" >> "$RUN_LOG" 2>&1; then
        log_wrapper "Telegram background send started OK"
    else
        log_wrapper "WARN: Telegram notifier failed to start (code=$?)"
    fi
}

# === 统计执行前 ===
log_wrapper "=== Artvee Nightly Wrapper Started ==="
log_wrapper "RUN_TYPE=$RUN_TYPE"
log_wrapper "TIMESTAMP=$TIMESTAMP"

IMAGES_BEFORE=$(count_images)
META_BEFORE=$(count_metadata)
SIZE_BEFORE=$(dir_size)

log_wrapper "BEFORE: images=$IMAGES_BEFORE metadata=$META_BEFORE size=$SIZE_BEFORE"

# === 执行原 Artvee 命令 ===
if [ "$RUN_TYPE" = "test" ]; then
    log_wrapper "TEST MODE: skipping Artvee execution, sending test message only"
    TEST_MSG="🧪 *Artvee Wrapper Test*
时间: $(date '+%Y-%m-%d %H:%M:%S')
状态: test mode
当前图片: $IMAGES_BEFORE
当前 metadata: $META_BEFORE
当前占用: $SIZE_BEFORE"
    send_telegram "$TEST_MSG"
    log_wrapper "=== Wrapper Finished (test) ==="
    exit 0
fi

EXIT_CODE=0
OUTPUT=""

if [ "$RUN_TYPE" = "refill" ]; then
    log_wrapper "Running refill_artvee_pending.py..."
    OUTPUT=$(cd "$BASE_DIR" && \
        "$PYTHON" scripts/refill_artvee_pending.py \
        --min-pending 60 --target-pending 120 --pages-per-seed 2 \
        --per-category-targets "japanese-prints=36,book-illustrations=30,posters-design=30,botanical-charts=24" \
        --execute 2>&1) || EXIT_CODE=$?
elif [ "$RUN_TYPE" = "batch" ]; then
    log_wrapper "Running run_artvee_nightly_batch.py..."
    OUTPUT=$(cd "$BASE_DIR" && \
        "$PYTHON" scripts/run_artvee_nightly_batch.py --limit 20 2>&1) || EXIT_CODE=$?
else
    log_wrapper "ERROR: unknown RUN_TYPE=$RUN_TYPE"
    exit 1
fi

# 写入运行日志
echo "$OUTPUT" >> "$RUN_LOG"

# === 统计执行后 ===
IMAGES_AFTER=$(count_images)
META_AFTER=$(count_metadata)
SIZE_AFTER=$(dir_size)

NEW_IMAGES=$((IMAGES_AFTER - IMAGES_BEFORE))
NEW_META=$((META_AFTER - META_BEFORE))

log_wrapper "AFTER: images=$IMAGES_AFTER metadata=$META_AFTER size=$SIZE_AFTER"
log_wrapper "NEW: images=+$NEW_IMAGES metadata=+$NEW_META"
log_wrapper "EXIT_CODE=$EXIT_CODE"

# === 检测错误关键字 ===
NETWORK_ERROR="no"
ERROR_SNIPPET=""
STATS_SNIPPET=""

if echo "$OUTPUT" | grep -qiE 'ERR_CONNECTION_CLOSED|ERR_CONNECTION_REFUSED|Timed out|ConnectTimeout|ConnectionResetError'; then
    NETWORK_ERROR="yes"
fi

# 单独提取 batch.py 的 stats: 汇总行（不是错误），展示层重命名 skipped -> not_selected
RAW_STATS=$(echo "$OUTPUT" | grep -E '^\[?[0-9T:.\-]+Z?\]? stats: downloaded=' | tail -n 1 || true)
if [ -n "$RAW_STATS" ]; then
    # 去掉前缀时间戳和中括号，保留 "stats: downloaded=..., failed=..., pending=..., skipped=..."
    # 然后把 skipped 重命名为 not_selected（仅展示层），manifest 状态字段保持不变
    STATS_SNIPPET=$(echo "$RAW_STATS" | sed -E 's/skipped=/not_selected=/g')
fi

# 提取真正的错误关键字（排除 stats 行），最多 300 字符
ERROR_SNIPPET=$(echo "$OUTPUT" | grep -iE 'FAILED|Error|Exception|Traceback|ERR_' | grep -vE '^\[?[0-9T:.\-]+Z?\]? stats:' | tail -n 1 | cut -c1-300 || true)

# === 构建 Telegram 消息 ===
if [ "$EXIT_CODE" -eq 0 ] && [ "$NEW_IMAGES" -gt 0 ]; then
    STATUS_EMOJI="✅"
    STATUS_TEXT="success"
elif [ "$EXIT_CODE" -eq 0 ]; then
    STATUS_EMOJI="⏸️"
    STATUS_TEXT="success (no new downloads)"
else
    STATUS_EMOJI="❌"
    STATUS_TEXT="failed"
fi

MSG="${STATUS_EMOJI} *Artvee Nightly* [${RUN_TYPE}]
时间: $(date '+%Y-%m-%d %H:%M:%S')
状态: ${STATUS_TEXT} exit=${EXIT_CODE}
新增图片: ${NEW_IMAGES}
新增 metadata: ${NEW_META}
当前占用: ${SIZE_AFTER}
网络错误: ${NETWORK_ERROR}"

if [ -n "$STATS_SNIPPET" ]; then
    MSG="${MSG}
统计: \`${STATS_SNIPPET}\`"
fi

if [ -n "$ERROR_SNIPPET" ]; then
    MSG="${MSG}
错误: \`${ERROR_SNIPPET}\`"
fi

# === 仅在 batch 模式、主任务成功时尝试轻量重建 gallery ===
# 失败用 || true 隔离，不影响主 batch 退出码；图库字段单独追加。
GALLERY_LINE=""
if [ "$RUN_TYPE" = "batch" ] && [ "$EXIT_CODE" -eq 0 ]; then
    log_wrapper "Building gallery (lightweight, post-batch)..."
    GALLERY_OUT=$("$PYTHON" "$BASE_DIR/scripts/build_artvee_gallery.py" --mode local 2>&1) || GALLERY_RC=$?
    GALLERY_RC=${GALLERY_RC:-0}
    if [ "$GALLERY_RC" -eq 0 ]; then
        # 解析末行 '[✓] wrote web/data/... (N records)' 拿数量
        GALLERY_COUNT=$(echo "$GALLERY_OUT" | grep -oE '\([0-9]+ records\)' | tail -n 1 | grep -oE '[0-9]+' || echo "?")
        # 解析 thumbs 新增数 '256 +X skipped Y' 和 '512 +X skipped Y'
        NEW_256=$(echo "$GALLERY_OUT" | grep -oE '256 \+[0-9]+ skipped [0-9]+' | head -n 1 | grep -oE '\+[0-9]+' | tr -d '+')
        NEW_256=${NEW_256:-0}
        NEW_512=$(echo "$GALLERY_OUT" | grep -oE '512 \+[0-9]+ skipped [0-9]+' | head -n 1 | grep -oE '\+[0-9]+' | tr -d '+')
        NEW_512=${NEW_512:-0}
        GALLERY_LINE="图库: updated, records=${GALLERY_COUNT}, thumbs +${NEW_256}/+${NEW_512}"
        log_wrapper "Gallery build OK: $GALLERY_LINE"
    else
        GALLERY_LINE="图库: update failed (rc=${GALLERY_RC}), see log"
        log_wrapper "Gallery build FAILED rc=$GALLERY_RC; continuing wrapper."
    fi
    # 把 stdout 留痕到 wrapper log，但不进 MSG（避免 grep 误判）
    echo "$GALLERY_OUT" >> "$RUN_LOG"
fi

if [ -n "$GALLERY_LINE" ]; then
    MSG="${MSG}
${GALLERY_LINE}"
fi

# === 仅在 batch 模式、主任务成功时尝试轻量构建 daily digest ===
# 失败用 || true 隔离，不影响主 batch 退出码；digest 行单独追加。
DIGEST_LINE=""
if [ "$RUN_TYPE" = "batch" ] && [ "$EXIT_CODE" -eq 0 ]; then
    log_wrapper "Building daily digest (lightweight, post-gallery)..."
    DIGEST_OUT=$("$PYTHON" "$BASE_DIR/scripts/build_artvee_daily_digest.py" \
        --strategy diverse --select 5 --candidate-limit 20 2>&1) || DIGEST_RC=$?
    DIGEST_RC=${DIGEST_RC:-0}
    if [ "$DIGEST_RC" -eq 0 ]; then
        # 解析 '[✓] digest generated: <mdname> + <htmlname>' 拿文件名
        DIGEST_NAME=$(echo "$DIGEST_OUT" | grep -oE 'artvee-digest-[0-9-]+\.md' | head -n 1 || echo "")
        DIGEST_SEL=$(echo "$DIGEST_OUT" | grep -oE 'selected=[0-9]+' | head -n 1 | grep -oE '[0-9]+' || echo "?")
        DIGEST_LINE="灵感: digest generated, selected=${DIGEST_SEL}, path=digests/${DIGEST_NAME}"
        log_wrapper "Digest build OK: $DIGEST_LINE"
    else
        DIGEST_LINE="灵感: digest failed, see log (rc=${DIGEST_RC})"
        log_wrapper "Digest build FAILED rc=$DIGEST_RC; continuing wrapper."
    fi
    echo "$DIGEST_OUT" >> "$RUN_LOG"
fi

if [ -n "$DIGEST_LINE" ]; then
    MSG="${MSG}
${DIGEST_LINE}"
fi

MSG="${MSG}
日志: \`logs/wrapper_runs/wrapper_${RUN_TYPE}_${TIMESTAMP}.log\`"

# === 发送 Telegram ===
send_telegram "$MSG"

log_wrapper "=== Wrapper Finished ==="
exit "$EXIT_CODE"
