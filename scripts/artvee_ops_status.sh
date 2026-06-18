#!/usr/bin/env bash
# Artvee Gallery · Post-stable ops status (P8A)
#
# Single read-only command operators run after the v0.2.0 stable
# release. Aggregates repo state, records, integrity, readiness,
# candidate readiness, pending MEDIA, OpenClaw transport health,
# pages guard, online status into one JSON+MD report. Optionally
# sends the report via Telegram with a staged MEDIA attachment.
#
# This script:
#   * Does NOT trigger Artvee download / refill / nightly batch
#   * Does NOT push GitHub Pages
#   * Does NOT execute --approve
#   * Does NOT auto-replay pending media (only reports counts)
#   * Does NOT install new cron
#   * Does NOT print token / secret / chat_id
#
# Usage:
#   bash scripts/artvee_ops_status.sh
#   bash scripts/artvee_ops_status.sh --online
#   bash scripts/artvee_ops_status.sh --include-pages
#   bash scripts/artvee_ops_status.sh --media
#   bash scripts/artvee_ops_status.sh --no-telegram
#   bash scripts/artvee_ops_status.sh --date 2026-06-18
#
# Default: no telegram, no online, no pages-repo touch.

set -euo pipefail

# Resolve repo root from this script's location (works whether the
# script is invoked from cron or interactively).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Pick a Python interpreter. Prefer the project's venv if present.
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif [[ -x "$HOME/.hermes-agent/.venv/bin/python" ]]; then
    PYTHON="$HOME/.hermes-agent/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
else
    echo "[FATAL] no python3 interpreter found" >&2
    exit 127
fi

cd "$REPO_ROOT"

# Add scripts to PYTHONPATH so the ops status script can import the
# notifier and the daily health helper directly.
export PYTHONPATH="$REPO_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON" "$REPO_ROOT/scripts/artvee_ops_status.py" "$@"
