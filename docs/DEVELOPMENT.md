
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
