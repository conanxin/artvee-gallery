#!/usr/bin/env bash
#
# Artvee Gallery · Daily Health Cron Installer (P7B)
# ==================================================
# Idempotent installer for the P7B daily health Telegram cron.
#
# Usage:
#   bash scripts/install_daily_health_cron.sh --install
#   bash scripts/install_daily_health_cron.sh --dry-run
#   bash scripts/install_daily_health_cron.sh --time "0 3 * * *"
#   bash scripts/install_daily_health_cron.sh --remove
#
# Design:
#   - Idempotent: running twice does not add duplicate entries.
#   - Marker-based: the P7B block is delimited by unique comment markers.
#   - Safe: backs up crontab before modification, prints preview in dry-run.
#   - No secrets: does not print tokens, chat IDs, or paths to secrets.

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER_BEGIN="# >>> Artvee P7B daily health check BEGIN"
MARKER_END="# <<< Artvee P7B daily health check END"
CRON_TIME="0 3 * * *"
DRY_RUN=false
REMOVE=false

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) DRY_RUN=false; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --time) CRON_TIME="$2"; shift 2 ;;
    --remove) REMOVE=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Build the cron block (use absolute path from script location, or $HOME if user prefers)
REPO_DIR="${BASE_DIR}"
# Use tilde expansion if the path is under HOME, for brevity
HOME_DIR="${HOME}"
if [[ "${REPO_DIR}" == "${HOME_DIR}"* ]]; then
  REPO_DIR="~${REPO_DIR#${HOME_DIR}}"
fi

CRON_BLOCK="${MARKER_BEGIN}
# Artvee Daily Health Check (P7B)
# Runs after nightly batch (02:00) + confirm_demo_refresh (02:30)
# CRON_TZ=Asia/Shanghai is set by the existing Artvee block above
${CRON_TIME} cd ${REPO_DIR} && bash scripts/artvee_daily_health_check.sh --online --media >> logs/daily-health-cron/daily_health_\$(date +\%Y\%m\%d)_030000.log 2>&1
${MARKER_END}"

# Read current crontab
CURRENT=$(crontab -l 2>/dev/null || true)

# Check if marker exists
HAS_MARKER=false
if echo "$CURRENT" | grep -qF "$MARKER_BEGIN"; then
  HAS_MARKER=true
fi

if [[ "$REMOVE" == true ]]; then
  if [[ "$HAS_MARKER" == false ]]; then
    echo "[info] P7B marker not found in crontab; nothing to remove."
    exit 0
  fi
  NEW=$(echo "$CURRENT" | sed "/${MARKER_BEGIN}/,/${MARKER_END}/d")
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] Would remove P7B block from crontab."
    echo "--- Preview of new crontab (block removed) ---"
    echo "$NEW"
    exit 0
  fi
  # Backup and install
  BACKUP="${BASE_DIR}/logs/daily-health-cron/crontab.before_remove.$(date +%Y%m%d%H%M%S).txt"
  mkdir -p "$(dirname "$BACKUP")"
  echo "$CURRENT" > "$BACKUP"
  echo "$NEW" | crontab -
  echo "[✓] P7B block removed. Backup: ${BACKUP}"
  exit 0
fi

# If marker already exists, replace the block
if [[ "$HAS_MARKER" == true ]]; then
  echo "[info] P7B marker found in crontab; replacing existing block."
  # Remove old block
  CURRENT=$(echo "$CURRENT" | sed "/${MARKER_BEGIN}/,/${MARKER_END}/d")
fi

# Append new block
NEW="${CURRENT}
${CRON_BLOCK}"

if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] Would add/replace P7B block in crontab."
  echo "--- Preview of new crontab ---"
  echo "$NEW"
  exit 0
fi

# Backup
BACKUP="${BASE_DIR}/logs/daily-health-cron/crontab.before_p7b.$(date +%Y%m%d%H%M%S).txt"
mkdir -p "$(dirname "$BACKUP")"
crontab -l > "$BACKUP" 2>/dev/null || true

# Install
echo "$NEW" | crontab -

echo "[✓] P7B daily health cron installed."
echo "    Time: ${CRON_TIME}"
echo "    Command: cd ${REPO_DIR} && bash scripts/artvee_daily_health_check.sh --online --media"
echo "    Log: logs/daily-health-cron/daily_health_YYYYMMDD_030000.log"
echo "    Backup: ${BACKUP}"
