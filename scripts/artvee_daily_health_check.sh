#!/usr/bin/env bash
#
# Artvee Gallery · Daily Health Check (P7A)
# ==========================================
# A single-command daily health check that reports the current state
# of the Artvee gallery without modifying any data.
#
# Usage:
#   bash scripts/artvee_daily_health_check.sh
#   bash scripts/artvee_daily_health_check.sh --date YYYY-MM-DD
#   bash scripts/artvee_daily_health_check.sh --no-telegram
#   bash scripts/artvee_daily_health_check.sh --online
#   bash scripts/artvee_daily_health_check.sh --media
#   bash scripts/artvee_daily_health_check.sh --simulate-media-failure
#     (P7B+1; for testing the MEDIA-failure fallback chain; not for cron)
#
# Design principles:
#   - Read-only: never modifies source data, images, or candidates.
#   - Deterministic: same date gives same report (no network calls in default mode).
#   - Safe: exits 0 even if some checks fail (reports failure, does not crash pipeline).
#   - Consolidated: one command covers all previous phase-specific checks.

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DATE="${DATE:-$(date +%Y-%m-%d)}"
REPORT_DIR="${BASE_DIR}/reports/runtime/daily-health"
REPORT_JSON="${REPORT_DIR}/artvee-daily-health-${RUN_DATE}.json"
REPORT_MD="${REPORT_DIR}/artvee-daily-health-${RUN_DATE}.md"

# Parse flags
ONLINE=false
MEDIA=false
TELEGRAM=true
OPENCLAW_BIN=""
SIMULATE_MEDIA_FAILURE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) RUN_DATE="$2"; shift 2 ;;
    --no-telegram) TELEGRAM=false; shift ;;
    --online) ONLINE=true; shift ;;
    --media) MEDIA=true; shift ;;
    --openclaw-bin) OPENCLAW_BIN="$2"; shift 2 ;;
    --simulate-media-failure) SIMULATE_MEDIA_FAILURE=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

mkdir -p "${REPORT_DIR}"

# Run the Python check script
python3 "${BASE_DIR}/scripts/artvee_daily_health_check.py" \
  --date "${RUN_DATE}" \
  --base-dir "${BASE_DIR}" \
  --output-json "${REPORT_JSON}" \
  --output-md "${REPORT_MD}" \
  $([[ "${ONLINE}" == true ]] && echo "--online") \
  $([[ "${TELEGRAM}" == false ]] && echo "--no-telegram") \
  $([[ "${MEDIA}" == true ]] && echo "--media") \
  $([[ -n "${OPENCLAW_BIN}" ]] && echo "--openclaw-bin ${OPENCLAW_BIN}") \
  $([[ "${SIMULATE_MEDIA_FAILURE}" == true ]] && echo "--simulate-media-failure")

echo "[✓] Health check report: ${REPORT_JSON} + ${REPORT_MD}"
echo "===== Daily health check complete ====="
