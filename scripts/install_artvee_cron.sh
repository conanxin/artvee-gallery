#!/usr/bin/env bash
#
# Artvee Gallery · Unified Cron Installer (P8D+1)
# =================================================
# Single source of truth for the four legacy Artvee cron lines that
# were not managed by an installer before P8D+1:
#
#   01:30  refill          (artvee_nightly_wrapper.sh refill)
#   02:00  nightly batch   (artvee_nightly_wrapper.sh batch)
#   02:30  confirm refresh (confirm_demo_refresh.sh --no-telegram)
#
# Plus the P7B daily-health and P8D media-replay installers handle
# their own blocks. This script does NOT touch those markers.
#
# What it fixes (P8D+1):
#   - Exports PATH so OpenClaw at $HOME/.local/bin is resolvable under
#     the minimal cron PATH (/usr/bin:/bin). Without this, the
#     artvee_telegram_notify notifier logs NOTIFY_FAIL on every run.
#   - Bakes CRON_TZ=Asia/Shanghai on its own line (cron parses it as a
#     per-line env var; prepending it to the schedule produced a 7-field
#     line that cron silently rejected — see install_media_replay_cron.sh
#     for the same fix).
#   - Idempotent: each block is delimited by unique markers and re-running
#     replaces the existing block in place.
#
# Usage:
#   bash scripts/install_artvee_cron.sh --dry-run
#   bash scripts/install_artvee_cron.sh --install
#   bash scripts/install_artvee_cron.sh --remove
#
# Safety:
#   - Backups crontab to logs/artvee-cron/crontab.before_p8d1.*.txt
#   - Never prints tokens / chat IDs / env values
#   - --dry-run prints the new crontab and exits without touching it

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DRY_RUN=false
REMOVE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) DRY_RUN=false; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --remove) REMOVE=true; shift ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# P8D+2: Chat-id resolution for cron environments
# The notifier reads chat id from (in order):
#   1. CLI --chat-id
#   2. ARTVEE_TELEGRAM_CHAT_ID env var
#   3. ~/.config/artvee-gallery/telegram.env (private, chmod 600, not in git)
#   4. ~/.openclaw/openclaw.json channels.telegram.defaultChatId
#   5. ~/.openclaw/openclaw.json channels.telegram.targets[0]
# We set ARTVEE_TELEGRAM_ENV_FILE as a cron env var so the notifier can
# read it; we do NOT bake the actual chat id into the cron line (secret hygiene).

# tilde-compress the repo path for readability in the crontab
HOME_DIR="${HOME}"
REPO_DIR="${BASE_DIR}"
if [[ "${REPO_DIR}" == "${HOME_DIR}"/* ]]; then
  REPO_DIR="~${REPO_DIR#${HOME_DIR}}"
fi

# Marker block for the three legacy Artvee cron lines. Anything we add
# in P8D+1 lives inside this single block so the --remove / --install
# operations stay atomic.
LEGACY_MARKER_BEGIN="# >>> Artvee P8D+1 unified cron BEGIN"
LEGACY_MARKER_END="# <<< Artvee P8D+1 unified cron END"

LEGACY_BLOCK="${LEGACY_MARKER_BEGIN}
# Artvee Gallery · Refill / Batch / Confirm refresh (P8D+1)
# Single source of truth for the three pre-P7B Artvee cron lines.
# CRON_TZ is set on its own line (cron parses it as a per-line env var).
# PATH is exported so the OpenClaw binary at \$HOME/.local/bin is
# resolvable for the Telegram notifier — cron otherwise has no entry
# for that bin dir and the notifier silently logs NOTIFY_FAIL.
# P8D+2: ARTVEE_TELEGRAM_ENV_FILE points to a private env file
# (chmod 600, not in git) so the notifier can resolve the chat id.
# We do NOT bake the actual chat id into the cron line.
CRON_TZ=Asia/Shanghai
PATH=\$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
ARTVEE_TELEGRAM_ENV_FILE=\$HOME/.config/artvee-gallery/telegram.env
30 1 * * * cd ${REPO_DIR} && bash scripts/artvee_nightly_wrapper.sh refill >> logs/wrapper_refill.log 2>&1
0 2 * * * cd ${REPO_DIR} && bash scripts/artvee_nightly_wrapper.sh batch >> logs/wrapper_batch.log 2>&1
30 2 * * * cd ${REPO_DIR} && bash scripts/confirm_demo_refresh.sh --no-telegram >> logs/confirm_demo_refresh/cron_stderr.log 2>&1
${LEGACY_MARKER_END}"

CURRENT="$(crontab -l 2>/dev/null || true)"
HAS_MARKER=false
if printf '%s\n' "$CURRENT" | grep -qF "$LEGACY_MARKER_BEGIN"; then
  HAS_MARKER=true
fi

if [[ "$REMOVE" == true ]]; then
  if [[ "$HAS_MARKER" == false ]]; then
    echo "[info] P8D+1 legacy marker not found; nothing to remove."
    exit 0
  fi
  NEW="$(printf '%s\n' "$CURRENT" | sed "/${LEGACY_MARKER_BEGIN}/,/${LEGACY_MARKER_END}/d")"
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] Would remove P8D+1 legacy block from crontab."
    echo "--- Preview of new crontab (block removed) ---"
    printf '%s\n' "$NEW"
    exit 0
  fi
  BACKUP_DIR="${BASE_DIR}/logs/artvee-cron"
  mkdir -p "$BACKUP_DIR"
  BACKUP="${BACKUP_DIR}/crontab.before_remove.$(date +%Y%m%d%H%M%S).txt"
  printf '%s\n' "$CURRENT" > "$BACKUP"
  printf '%s\n' "$NEW" | crontab -
  echo "[OK] P8D+1 legacy block removed. Backup: ${BACKUP}"
  exit 0
fi

# Replace existing block in place if present.
if [[ "$HAS_MARKER" == true ]]; then
  echo "[info] P8D+1 legacy marker found; replacing existing block."
  CURRENT="$(printf '%s\n' "$CURRENT" | sed "/${LEGACY_MARKER_BEGIN}/,/${LEGACY_MARKER_END}/d")"
fi
NEW="${CURRENT}
${LEGACY_BLOCK}"

if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] Would add/replace P8D+1 legacy block in crontab."
  echo "    Schedule: 01:30 refill · 02:00 batch · 02:30 confirm refresh"
  echo "    CRON_TZ:  Asia/Shanghai"
  echo "    PATH:     \$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
  echo "    Repo:     ${REPO_DIR}"
  echo "--- Preview of new crontab ---"
  printf '%s\n' "$NEW"
  exit 0
fi

BACKUP_DIR="${BASE_DIR}/logs/artvee-cron"
mkdir -p "$BACKUP_DIR"
BACKUP="${BACKUP_DIR}/crontab.before_p8d1.$(date +%Y%m%d%H%M%S).txt"
crontab -l > "$BACKUP" 2>/dev/null || true
printf '%s\n' "$NEW" | crontab -
echo "[OK] P8D+1 legacy block installed."
echo "    Schedule: 01:30 refill · 02:00 batch · 02:30 confirm refresh"
echo "    CRON_TZ:  Asia/Shanghai"
echo "    PATH:     \$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
echo "    Backup:   ${BACKUP}"
