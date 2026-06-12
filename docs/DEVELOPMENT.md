
---

## 20. P7A+1 OpenClaw binary resolution

P7A+1 normalizes how the health check (and any other script) finds
the OpenClaw binary for Telegram notification. The goal is to make
Telegram notify work in both cron and interactive shell contexts
without hardcoding paths.

### Resolution order

The `scripts/artvee_telegram_notify.py` resolver tries, in order:

1. **CLI argument** `--openclaw-bin <path-or-command>`
2. **Environment variable** `ARTVEE_OPENCLAW_BIN`
3. **Environment variable** `OPENCLAW_BIN`
4. **PATH lookup** for `openclaw` (via `shutil.which`)
5. **None** — graceful skip, health check continues

### Why this matters

- Interactive shells (e.g., OpenClaw agent sessions) may have
different `PATH` than cron. The resolver tries both env vars and PATH.
- The default `'openclaw'` string is not treated as a valid resolved
path until `shutil.which('openclaw')` confirms it exists in PATH.
- If the binary is missing, the health check **still generates its report**
and exits 0. Telegram notify is skipped with a clear message.

### Usage examples

```bash
# Default: let resolver find openclaw in PATH
bash scripts/artvee_daily_health_check.sh

# Explicit binary path (useful in Docker, CI, or non-standard install)
bash scripts/artvee_daily_health_check.sh --openclaw-bin /usr/local/bin/openclaw

# No Telegram (report only)
bash scripts/artvee_daily_health_check.sh --no-telegram

# With online + media + explicit binary
bash scripts/artvee_daily_health_check.sh --online --media --openclaw-bin <openclaw-bin>
```

### Health check report field

The JSON report now includes a `telegram_notify` object:

```json
{
  "telegram_notify": {
    "enabled": true,
    "media_requested": true,
    "openclaw_status": "resolved",
    "sent": true,
    "message_id": null
  }
}
```

- `openclaw_status`: `resolved` | `missing` | `skipped`
- `sent`: `true` if the message was dispatched, `false` otherwise
- `message_id`: reserved for future enhancement (OpenClaw CLI currently
returns it in stdout, not structured JSON)

### Safety

- No hardcoded absolute paths in source code.
- No token or secret printed in error messages.
- Graceful degradation: missing binary ≠ failed health check.
- The `--openclaw-bin` argument is forwarded through the shell wrapper
to the Python script to the notifier, keeping the resolution logic in
one place (`artvee_telegram_notify.py`).

---

## 21. P7B Daily health cron

P7B installs the daily health check as a cron job that runs at 03:00
Asia/Shanghai, after the nightly batch (02:00) and candidate refresh
(02:30). The cron is idempotent and marker-based.

### Install the cron

```bash
bash scripts/install_daily_health_cron.sh --install
```

This adds a marker-delimited block to the user's crontab:

```
# >>> Artvee P7B daily health check BEGIN
# Artvee Daily Health Check (P7B)
0 3 * * * cd <repo-dir> && bash scripts/artvee_daily_health_check.sh --online --media >> logs/daily-health-cron/daily_health_$(date +\%Y\%m\%d)_030000.log 2>&1
# <<< Artvee P7B daily health check END
```

### Remove or modify the cron

```bash
# Remove the P7B block
bash scripts/install_daily_health_cron.sh --remove

# Change the time (e.g., to 09:00)
bash scripts/install_daily_health_cron.sh --install --time "0 9 * * *"
```

### Idempotency

Running `--install` twice replaces the existing block rather than
adding a duplicate. The script uses `sed` to remove the old block
before appending the new one.

### Safety

- The installer does not modify the Artvee repo (no data changes).
- It does not trigger downloads, refills, or batches.
- It backs up the crontab before modification (`logs/daily-health-cron/crontab.before_p7b.*.txt`).
- It does not print tokens, secrets, or chat IDs.

---

## 22. P7B+1 Telegram delivery state model + failure-only fallback

P7B+1 refactors the daily health check's Telegram reporting so that
**text summary**, **MEDIA attachment**, and **fallback** are independent
tracks. A MEDIA failure is observable but no longer silent.

### State model (JSON, in `reports/runtime/daily-health/*.json`)

```json
{
  "telegram": {
    "requested": true,
    "openclaw_status": "resolved | missing | skipped",
    "text_summary": {"attempted": true, "sent": true, "message_id": "22811", "error": null},
    "media": {
      "requested": true,
      "staged": true,
      "staged_path": "$HOME/.openclaw/media/artvee-reports/...",
      "sent": true,
      "message_id": "22813",
      "error": null,
      "simulated_failure": false
    },
    "fallback": {"attempted": false, "sent": false, "message_id": null, "reason": null}
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `telegram.openclaw_status` | enum | `resolved` if notifier could start; `missing` if binary absent; `skipped` if `--no-telegram`. |
| `telegram.text_summary.sent` | bool | Whether the short ✅/❌ block was delivered. |
| `telegram.text_summary.message_id` | str | Telegram message id parsed from the notifier's log. |
| `telegram.media.staged_path` | str | Absolute path inside the OpenClaw allowlist (default root `$HOME/.openclaw/media/`). |
| `telegram.media.simulated_failure` | bool | True only when `--simulate-media-failure` was used (testing). |
| `telegram.fallback.reason` | enum | Currently only `media_failed`. |

### Failure-only fallback

When all of the following hold:

- `checks.integrity.status == "PASS"`
- `checks.readiness.status == "PASS"`
- `telegram.text_summary.sent == true`
- `telegram.media.sent == false` and `telegram.media.error != null`

…a single short text fallback is sent:

```
⚠️ Artvee Daily Health MEDIA failed
Date: YYYY-MM-DD
Health: PASS
Text summary: sent
MEDIA: failed
Report: <report-md-path>
Action: no data issue; check media delivery
```

Guarantees:

- Sent at most **once** per run.
- Never recurses (the fallback path does not call the health check).
- Does not change the script's exit code unless health itself failed.

### `--simulate-media-failure` (testing only)

To verify the fallback chain without breaking the real MEDIA allowlist:

```bash
cd <artvee-repo>
bash scripts/artvee_daily_health_check.sh --online --media --simulate-media-failure
```

This forces `media.sent=false` with `error=simulated_failure` and triggers
the fallback. **Do not** use this in cron; it is for one-off testing.

### How to inspect any day's Telegram status

```bash
# After a run:
python3 -c "
import json
d = json.load(open('reports/runtime/daily-health/artvee-daily-health-2026-06-13.json'))
print(json.dumps(d['telegram'], indent=2, ensure_ascii=False))
"
```

### Chat id resolution (P7B+1: no hardcoded ids in the repo)

`scripts/artvee_telegram_notify.py` resolves the chat id in this order:

1. `--chat-id` CLI argument
2. `ARTVEE_TELEGRAM_CHAT_ID` environment variable
3. `channels.telegram.defaultChatId` in `$HOME/.openclaw/openclaw.json`
4. `channels.telegram.targets[0]` in the same file
5. Hard error (no fallback to a literal id in source)

The cron installer bakes `ARTVEE_TELEGRAM_CHAT_ID` into the cron block
when the installer is run with that env var set. To re-install with a
new chat id, simply re-export and re-run the installer.

```bash
ARTVEE_TELEGRAM_CHAT_ID="<telegram-chat-id>" \
  bash scripts/install_daily_health_cron.sh --install
```
