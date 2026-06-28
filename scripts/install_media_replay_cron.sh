#!/usr/bin/env bash
#
# Artvee Gallery · Optional Media Replay Cron Installer (P8D)
# ===========================================================
# Idempotent installer for the P8D media-replay cron.
#
# Usage:
#   bash scripts/install_media_replay_cron.sh --install
#   bash scripts/install_media_replay_cron.sh --dry-run
#   bash scripts/install_media_replay_cron.sh --time "10 3 * * *"
#   bash scripts/install_media_replay_cron.sh --timezone "Asia/Shanghai"
#   bash scripts/install_media_replay_cron.sh --remove
#
# Design:
#   - Idempotent: running twice does not add duplicate entries; the
#     existing block is replaced in-place when it exists.
#   - Marker-based: the P8D block is delimited by unique comment markers
#     so --remove only deletes the P8D block and leaves P7B / other
#     blocks untouched.
#   - Safe: backs up crontab before modification, prints preview in
#     dry-run mode without touching crontab.
#   - No secrets: does not print tokens, chat IDs, or paths to secrets.
#
# Default schedule:
#   CRON_TZ=Asia/Shanghai
#   10 3 * * *
#
# Why 10 3 (not 0 3): the P7B daily-health cron already runs at 0 3 and
# does its own MEDIA-fallback scan. P8D runs 10 minutes later to give
# that scan a chance to write a deferred MEDIA before P8D flushes it.
#
# Cron command (default):
#   cd <artvee-repo> && bash scripts/artvee_media_replay_cron.sh \
#     --limit 5 --max-retries 3 \
#     >> logs/media-replay-cron/media_replay_cron.log 2>&1

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER_BEGIN="# >>> Artvee P8D media replay cron BEGIN"
MARKER_END="# <<< Artvee P8D media replay cron END"
CRON_TIME="10 3 * * *"
CRON_TZ="Asia/Shanghai"
DRY_RUN=false
REMOVE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) DRY_RUN=false; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --time) CRON_TIME="$2"; shift 2 ;;
    --timezone) CRON_TZ="$2"; shift 2 ;;
    --remove) REMOVE=true; shift ;;
    -h|--help)
      sed -n '2,40p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Build the cron block. Use ~ for the repo path when possible.
REPO_DIR="${BASE_DIR}"
HOME_DIR="${HOME}"
if [[ "${REPO_DIR}" == "${HOME_DIR}"/* ]]; then
  REPO_DIR="~${REPO_DIR#${HOME_DIR}}"
fi

# P8D+1 fix: CRON_TZ=... must be on its own line above the schedule
# (cron treats any leading "Name=value" as a per-line env var, not a
# schedule column). Prepending it to the schedule produced a 7-field
# line that cron silently rejects → no logs, no summary.
CRON_BLOCK="${MARKER_BEGIN}
# Artvee Optional Media Replay (P8D)
# Runs 10 minutes after the P7B daily-health cron (which runs at 0 3).
# This cron is optional: pending=0 is silent, transport failure is silent.
# It never sends a zero-pending notification, never retries retired URLs,
# and never runs nightly batch / Pages publish / approve.
# It only invokes the staged-only P7B+3 replay flow.
# CRON environment: PATH must include \$HOME/.local/bin so the OpenClaw
# binary used by check_openclaw_transport.py is resolvable. set -a below
# exports all assignments on this line as env vars for the cron job.
CRON_TZ=${CRON_TZ}
PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
${CRON_TIME} cd ${REPO_DIR} && bash scripts/artvee_media_replay_cron.sh --limit 5 --max-retries 3 >> logs/media-replay-cron/media_replay_cron.log 2>&1
${MARKER_END}"

# Read current crontab
CURRENT=$(crontab -l 2>/dev/null || true)

HAS_MARKER=false
if echo "$CURRENT" | grep -qF "$MARKER_BEGIN"; then
  HAS_MARKER=true
fi

if [[ "$REMOVE" == true ]]; then
  if [[ "$HAS_MARKER" == false ]]; then
    echo "[info] P8D marker not found in crontab; nothing to remove."
    exit 0
  fi
  NEW=$(printf '%s\n' "$CURRENT" | sed "/${MARKER_BEGIN}/,/${MARKER_END}/d")
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] Would remove P8D block from crontab."
    echo "--- Preview of new crontab (block removed) ---"
    printf '%s\n' "$NEW"
    exit 0
  fi
  BACKUP="${BASE_DIR}/logs/media-replay-cron/crontab.before_remove.$(date +%Y%m%d%H%M%S).txt"
  mkdir -p "$(dirname "$BACKUP")"
  printf '%s\n' "$CURRENT" > "$BACKUP"
  printf '%s\n' "$NEW" | crontab -
  echo "[✓] P8D block removed. Backup: ${BACKUP}"
  exit 0
fi

# If marker already exists, replace the block
if [[ "$HAS_MARKER" == true ]]; then
  echo "[info] P8D marker found in crontab; replacing existing block."
  CURRENT=$(printf '%s\n' "$CURRENT" | sed "/${MARKER_BEGIN}/,/${MARKER_END}/d")
fi

# Append new block
NEW="${CURRENT}
${CRON_BLOCK}"

if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] Would add/replace P8D block in crontab."
  echo "    Time: ${CRON_TIME} (CRON_TZ=${CRON_TZ})"
  echo "    Command: cd ${REPO_DIR} && bash scripts/artvee_media_replay_cron.sh --limit 5 --max-retries 3"
  echo "    Log: logs/media-replay-cron/media_replay_cron.log"
  echo "--- Preview of new crontab ---"
  printf '%s\n' "$NEW"
  exit 0
fi

# Backup
BACKUP="${BASE_DIR}/logs/media-replay-cron/crontab.before_p8d.$(date +%Y%m%d%H%M%S).txt"
mkdir -p "$(dirname "$BACKUP")"
crontab -l > "$BACKUP" 2>/dev/null || true

# Install
printf '%s\n' "$NEW" | crontab -

echo "[✓] P8D media replay cron installed."
echo "    Time: ${CRON_TIME} (CRON_TZ=${CRON_TZ})"
echo "    Command: cd ${REPO_DIR} && bash scripts/artvee_media_replay_cron.sh --limit 5 --max-retries 3"
echo "    Log: logs/media-replay-cron/media_replay_cron.log"
echo "    Backup: ${BACKUP}"
