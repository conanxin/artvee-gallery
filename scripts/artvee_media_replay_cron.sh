#!/usr/bin/env bash
#
# Artvee Gallery · Optional Media Replay Cron Wrapper (P8D)
# =========================================================
# Cron entry point for flushing deferred MEDIA after OpenClaw transport
# recovers. Reads-only by default; only invokes the existing P7B+3
# ``replay_pending_media.py --apply`` flow (which itself uses the
# P7B+2 staged-only MEDIA path). Never sends a "0 pending" notification.
#
# Usage (all flags optional; sensible defaults):
#   bash scripts/artvee_media_replay_cron.sh
#   bash scripts/artvee_media_replay_cron.sh --dry-run
#   bash scripts/artvee_media_replay_cron.sh --limit 5
#   bash scripts/artvee_media_replay_cron.sh --max-retries 3
#   bash scripts/artvee_media_replay_cron.sh --no-transport-check
#   bash scripts/artvee_media_replay_cron.sh --date YYYY-MM-DD
#
# Defaults: --limit 5, --max-retries 3, transport check enabled,
# dry-run off, today as the run date.
#
# Safety:
#   - flock -n prevents overlapping runs if a previous run is still flushing.
#   - Transport timeout/error: log a warning + write summary + exit 0.
#     The cron must not spam fallback text on transport failure.
#   - pending=0: silent success, only writes a local summary JSON.
#   - pending>0: hands off to ``replay_pending_media.py --apply`` which
#     sends via the staged-only MEDIA path; the cron wrapper itself
#     does not call the Telegram notifier.

set -uo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DATE="${DATE:-$(date +%Y-%m-%d)}"
SUMMARY_DIR="${BASE_DIR}/reports/runtime/media-replay"
LOCK_FILE="${SUMMARY_DIR}/.media-replay.lock"
SUMMARY_JSON="${SUMMARY_DIR}/cron-${RUN_DATE}.json"
LOG_DIR="${BASE_DIR}/logs/media-replay-cron"

# Defaults
LIMIT=5
MAX_RETRIES=3
DRY_RUN=false
TRANSPORT_CHECK=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) RUN_DATE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --max-retries) MAX_RETRIES="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --no-transport-check) TRANSPORT_CHECK=false; shift ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0
      ;;
    *) echo "[artvee-media-replay-cron] Unknown arg: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "${SUMMARY_DIR}" "${LOG_DIR}"

# Concurrency guard. flock -n returns failure if the lock is held.
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  # Don't spam; another cron run is still flushing. Exit 0 so cron
  # doesn't email/pager a false-positive.
  TS="$(date -Iseconds)"
  printf '{"date":"%s","started_at":"%s","outcome":"skipped_locked","reason":"another run is still flushing"}\n' \
    "${RUN_DATE}" "${TS}" > "${SUMMARY_JSON}"
  echo "[artvee-media-replay-cron] lock held by another run; skipping."
  exit 0
fi

START_TS="$(date -Iseconds)"

# Count pending before we decide what to do. Reuses the same helper
# the daily health check uses so the count never drifts.
PENDING_COUNT=$(BASE_DIR="${BASE_DIR}" python3 - <<'PY' 2>/dev/null || echo -1
import sys, os
from pathlib import Path
base = os.environ.get("BASE_DIR", ".")
sys.path.insert(0, os.path.join(base, "scripts"))
try:
    from artvee_daily_health_check import _scan_pending_media
except Exception:
    print(-1); sys.exit(0)
result = _scan_pending_media(Path(os.path.join(base, "reports")))
print(result.get("pending", 0))
PY
)

# Optional transport pre-flight. We never want to call replay when the
# gateway is down: the replay path would just immediately fall back and
# burn attempts. --no-transport-check is honored (default: enabled).
TRANSPORT_STATUS="not_checked"
TRANSPORT_LATENCY_MS=""
TRANSPORT_ERROR=""
if [[ "${TRANSPORT_CHECK}" == true ]]; then
  TRANSPORT_OUT=$(BASE_DIR="${BASE_DIR}" python3 "${BASE_DIR}/scripts/check_openclaw_transport.py" 2>&1 || true)
  TRANSPORT_STATUS=$(printf '%s' "${TRANSPORT_OUT}" | python3 -c "
import json,sys
try:
  d=json.loads(sys.stdin.read())
  print(d.get('status','unknown'))
except Exception:
  print('parse_error')
" 2>/dev/null || echo "parse_error")
  TRANSPORT_LATENCY_MS=$(printf '%s' "${TRANSPORT_OUT}" | python3 -c "
import json,sys
try:
  d=json.loads(sys.stdin.read())
  print((d.get('probes') or {}).get('version',{}).get('elapsed_ms',''))
except Exception:
  pass
" 2>/dev/null || true)
fi

# Decide outcome.
OUTCOME="noop_zero_pending"
REPLAY_RESULT_JSON=""
REPLAY_MESSAGE_IDS=""
REPLAY_QUARANTINED=0
REPLAY_PLANNED=0

if [[ "${PENDING_COUNT}" == "-1" ]]; then
  OUTCOME="error_helper_import"
elif [[ "${PENDING_COUNT}" -gt 0 ]]; then
  if [[ "${TRANSPORT_CHECK}" == true && "${TRANSPORT_STATUS}" != "ok" ]]; then
    # Don't burn attempts on a dead transport; pending stays for next run.
    OUTCOME="skipped_transport_unavailable"
  else
    # Hand off to the existing P7B+3 replay. That script:
    #  - Validates each staged_report path is a real file under <openclaw-media-root>
    #  - Sends text + staged MEDIA via artvee_telegram_notify.send_text
    #  - On success: moves .fallback-pending-*.json to reports/runtime/.../replayed/
    #  - On quarantine_max_retries: moves to reports/runtime/.../quarantine/
    REPLAY_OUT_BASE="${SUMMARY_DIR}/replay-${RUN_DATE}-$(date +%H%M%S)"
    if [[ "${DRY_RUN}" == true ]]; then
      BASE_DIR="${BASE_DIR}" python3 "${BASE_DIR}/scripts/replay_pending_media.py" \
        --limit "${LIMIT}" --max-retries "${MAX_RETRIES}" --dry-run \
        2>&1 | tee "${REPLAY_OUT_BASE}.dryrun.txt" || true
      OUTCOME="dry_run_completed"
    else
      BASE_DIR="${BASE_DIR}" python3 "${BASE_DIR}/scripts/replay_pending_media.py" \
        --limit "${LIMIT}" --max-retries "${MAX_RETRIES}" --apply \
        > "${REPLAY_OUT_BASE}.log" 2>&1 || true
      # Look for the .replay-result-* json written next to the pending file.
      LATEST_RESULT=$(ls -1t "${BASE_DIR}"/reports/runtime/**/.replay-result-*.json 2>/dev/null | head -1 || true)
      if [[ -n "${LATEST_RESULT}" && -f "${LATEST_RESULT}" ]]; then
        REPLAY_RESULT_JSON="${LATEST_RESULT}"
        # Best-effort: extract message_ids + quarantine count for the summary.
        REPLAY_MESSAGE_IDS=$(python3 -c "
import json,sys
try:
  d=json.loads(open('${LATEST_RESULT}').read())
  mids=[]
  for r in (d.get('results') or []):
    if r.get('message_id'):
      mids.append(str(r.get('message_id')))
  print(','.join(mids))
except Exception:
  pass
" 2>/dev/null || true)
        REPLAY_QUARANTINED=$(python3 -c "
import json,sys
try:
  d=json.loads(open('${LATEST_RESULT}').read())
  print(sum(1 for r in (d.get('results') or []) if r.get('outcome')=='quarantined'))
except Exception:
  print(0)
" 2>/dev/null || echo 0)
      fi
      OUTCOME="replayed_pending"
    fi
  fi
fi

END_TS="$(date -Iseconds)"

# Always write a summary JSON. This is the on-disk source-of-truth
# for ops status to read in P8A's replay_cron_last_run.
PENDING_INT=-1
if [[ "${PENDING_COUNT}" =~ ^-?[0-9]+$ ]]; then
  PENDING_INT="${PENDING_COUNT}"
fi
TRANSPORT_CHECK_LC="false"
if [[ "${TRANSPORT_CHECK}" == true ]]; then TRANSPORT_CHECK_LC="true"; fi
DRY_RUN_LC="false"
if [[ "${DRY_RUN}" == true ]]; then DRY_RUN_LC="true"; fi
SUMMARY_OUT=$(python3 - <<PY
import json
out = {
    "date": "${RUN_DATE}",
    "started_at": "${START_TS}",
    "ended_at": "${END_TS}",
    "outcome": "${OUTCOME}",
    "pending_before": ${PENDING_INT},
    "transport_check": ("${TRANSPORT_CHECK_LC}" == "true"),
    "transport_status": "${TRANSPORT_STATUS}",
    "transport_latency_ms": "${TRANSPORT_LATENCY_MS}",
    "limit": ${LIMIT},
    "max_retries": ${MAX_RETRIES},
    "dry_run": ("${DRY_RUN_LC}" == "true"),
    "replay_result_json": "${REPLAY_RESULT_JSON}",
    "replay_message_ids": "${REPLAY_MESSAGE_IDS}",
    "replay_quarantined": ${REPLAY_QUARANTINED:-0},
    "lock_file": "${LOCK_FILE}",
}
print(json.dumps(out, indent=2, ensure_ascii=False))
PY
)
printf '%s\n' "${SUMMARY_OUT}" > "${SUMMARY_JSON}"

# Print a single one-line summary for the cron log.
echo "[artvee-media-replay-cron] date=${RUN_DATE} pending=${PENDING_COUNT} transport=${TRANSPORT_STATUS} outcome=${OUTCOME} summary=${SUMMARY_JSON}"
